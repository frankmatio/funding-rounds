#!/usr/bin/env python3
"""
Funding Round Data Collection Engine V2 - Main Pipeline
With parallel processing, database storage, and multiple LLM/SEC accounts
"""

import argparse
import csv
import logging
import os
import sys
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock

from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database import DatabaseManager
from src.deduplicator_v2 import DeduplicatorV2
from src.exporter_v2 import ExporterV2
from src.llm_router_v2 import LLMRouterV2
from src.search_extractor_v2 import SearchExtractorV2
from src.sec_collector_v2 import SECCollectorV2

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Global lock for database writes
db_write_lock = Lock()


def load_config():
    """Load configuration from YAML file"""
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def load_companies_from_csv(csv_path: str, limit: int = None) -> list:
    """Load companies from CSV file"""
    companies = []

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            company_name = row.get('Companies') or row.get('company') or row.get('Company')
            if company_name:
                companies.append(company_name.strip())

    return companies[:limit] if limit else companies


def run_stage1(db_manager: DatabaseManager, companies: list):
    """Stage 1: Load companies into database"""
    logger.info("=" * 100)
    logger.info("STAGE 1: COMPANY LOADING")
    logger.info("=" * 100)

    with db_manager.session_scope() as session:
        for company_name in companies:
            db_manager.get_or_create_company(session, company_name)

        logger.info(f"✓ Loaded {len(companies)} companies into database")


def process_company_stage2(company_id: int, db_manager: DatabaseManager, sec_collector: SECCollectorV2):
    """Process a single company in Stage 2 (SEC)"""
    with db_manager.session_scope() as session:
        company = session.query(db_manager.engine).get(company_id)
        if company:
            return sec_collector.process_company(session, company)
    return 0


def process_company_stage2_worker(company_id: int, company_name: str, db_manager: DatabaseManager, sec_collector: SECCollectorV2):
    """Worker function for Stage 2 - processes a single company in its own session"""
    with db_manager.session_scope() as session:
        from src.database.models import Company
        company = session.query(Company).filter(Company.id == company_id).first()
        if company:
            return sec_collector.process_company(session, company)
        return 0


def run_stage2_parallel(db_manager: DatabaseManager, sec_collector: SECCollectorV2, workers: int):
    """Stage 2: SEC EDGAR Form D collection (parallel)"""
    logger.info("")
    logger.info("=" * 100)
    logger.info(f"STAGE 2: SEC EDGAR FORM D COLLECTION ({workers} workers)")
    logger.info("=" * 100)

    # Get company IDs and names that need Stage 2 (avoid detached instances)
    with db_manager.session_scope() as session:
        from src.database.models import Company, ProcessingStatus
        company_data = session.query(Company.id, Company.name).join(ProcessingStatus).filter(
            ~ProcessingStatus.stage2_sec_collected
        ).all()

    if not company_data:
        logger.info("All companies already processed for Stage 2")
        return

    logger.info(f"Processing {len(company_data)} companies...")

    total_rounds = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}

        for company_id, company_name in company_data:
            future = executor.submit(process_company_stage2_worker, company_id, company_name, db_manager, sec_collector)
            futures[future] = company_name

        completed = 0
        for future in as_completed(futures):
            company_name = futures[future]
            try:
                rounds_found = future.result()
                total_rounds += rounds_found
                completed += 1

                if completed % 10 == 0:
                    logger.info(f"  Progress: {completed}/{len(company_data)} ({completed/len(company_data)*100:.1f}%)")

            except Exception as e:
                logger.error(f"  Error processing {company_name}: {str(e)}")
                completed += 1

    logger.info(f"✓ Stage 2 complete: {total_rounds} rounds from SEC")


def process_company_stage3_worker(company_id: int, company_name: str, db_manager: DatabaseManager, search_extractor: SearchExtractorV2):
    """Worker function for Stage 3 - processes a single company in its own session"""
    with db_manager.session_scope() as session:
        from src.database.models import Company
        company = session.query(Company).filter(Company.id == company_id).first()
        if company:
            return search_extractor.process_company(session, company)
        return 0


def run_stage3_parallel(db_manager: DatabaseManager, search_extractor: SearchExtractorV2, workers: int):
    """Stage 3: Search-based extraction (parallel)"""
    logger.info("")
    logger.info("=" * 100)
    logger.info(f"STAGE 3: SEARCH-BASED EXTRACTION ({workers} workers)")
    logger.info("=" * 100)

    # Get company IDs and names that need Stage 3 (avoid detached instances)
    with db_manager.session_scope() as session:
        from src.database.models import Company, ProcessingStatus
        company_data = session.query(Company.id, Company.name).join(ProcessingStatus).filter(
            ~ProcessingStatus.stage3_search_extracted
        ).all()

    if not company_data:
        logger.info("All companies already processed for Stage 3")
        return

    logger.info(f"Processing {len(company_data)} companies...")

    total_rounds = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {}

        for company_id, company_name in company_data:
            future = executor.submit(process_company_stage3_worker, company_id, company_name, db_manager, search_extractor)
            futures[future] = company_name

        completed = 0
        for future in as_completed(futures):
            company_name = futures[future]
            try:
                rounds_found = future.result()
                total_rounds += rounds_found
                completed += 1

                if completed % 10 == 0:
                    logger.info(f"  Progress: {completed}/{len(company_data)} ({completed/len(company_data)*100:.1f}%)")

            except Exception as e:
                logger.error(f"  Error processing {company_name}: {str(e)}")
                completed += 1

    logger.info(f"✓ Stage 3 complete: {total_rounds} rounds from search")


def run_stage4(db_manager: DatabaseManager, deduplicator: DeduplicatorV2):
    """Stage 4: Deduplication"""
    logger.info("")
    logger.info("=" * 100)
    logger.info("STAGE 4: DEDUPLICATION")
    logger.info("=" * 100)

    with db_manager.session_scope() as session:
        stats = deduplicator.deduplicate_all(session)

    logger.info(f"✓ Stage 4 complete: {stats['unique_rounds']} unique rounds")


def main():
    """Run the V2 parallel pipeline"""
    parser = argparse.ArgumentParser(description='Funding Round Data Collection Engine V2')
    parser.add_argument('--full', action='store_true', help='Process ALL companies from CSV')
    parser.add_argument('--limit', type=int, help='Process first N companies from CSV')
    parser.add_argument('--csv', type=str, default='docs/growth_companies_to_scrap.csv',
                       help='Path to CSV file with company names')
    parser.add_argument('--workers', type=int, default=4,
                       help='Number of parallel workers (default: 4)')
    args = parser.parse_args()

    # Load environment and configuration
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
    config = load_config()

    # Override workers from config if specified
    if 'parallel' in config and 'max_workers' in config['parallel']:
        args.workers = config['parallel']['max_workers']

    # Determine run mode
    if args.full:
        run_mode = f"FULL RUN ({args.workers} workers)"
        limit = None
    elif args.limit:
        run_mode = f"LIMITED RUN ({args.limit} companies, {args.workers} workers)"
        limit = args.limit
    else:
        run_mode = f"MVP TEST (20 companies, {args.workers} workers)"
        limit = 20

    logger.info("=" * 100)
    logger.info(f"FUNDING ROUND DATA COLLECTION ENGINE V2 - {run_mode}")
    logger.info(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 100)

    # Load companies
    logger.info("")
    logger.info("Loading company list...")

    try:
        companies = load_companies_from_csv(args.csv, limit=limit)
        logger.info(f"✓ Loaded {len(companies)} companies from CSV")
        logger.info(f"First 10: {', '.join(companies[:10])}")
    except FileNotFoundError as e:
        logger.error(f"❌ {e}")
        sys.exit(1)

    # Initialize components
    logger.info("")
    logger.info("Initializing components...")

    db_manager = DatabaseManager(config)
    llm_router = LLMRouterV2(config, db_manager)
    sec_collector = SECCollectorV2(config, db_manager)
    search_extractor = SearchExtractorV2(config, llm_router, db_manager)
    deduplicator = DeduplicatorV2(config, db_manager)
    exporter = ExporterV2(config, db_manager)

    logger.info(f"✓ All components initialized")
    logger.info(f"✓ Parallel workers: {args.workers}")

    start_time = datetime.now()

    try:
        # Stage 1: Load companies
        stage1_start = datetime.now()
        run_stage1(db_manager, companies)
        stage1_elapsed = datetime.now() - stage1_start
        logger.info(f"Stage 1 complete in {stage1_elapsed}")

        # Stage 2: SEC collection (parallel)
        stage2_start = datetime.now()
        run_stage2_parallel(db_manager, sec_collector, args.workers)
        stage2_elapsed = datetime.now() - stage2_start
        logger.info(f"Stage 2 complete in {stage2_elapsed}")

        # Stage 3: Search extraction (parallel)
        stage3_start = datetime.now()
        run_stage3_parallel(db_manager, search_extractor, args.workers)
        stage3_elapsed = datetime.now() - stage3_start
        logger.info(f"Stage 3 complete in {stage3_elapsed}")

        # Stage 4: Deduplication
        stage4_start = datetime.now()
        run_stage4(db_manager, deduplicator)
        stage4_elapsed = datetime.now() - stage4_start
        logger.info(f"Stage 4 complete in {stage4_elapsed}")

        # Export results
        export_start = datetime.now()
        with db_manager.session_scope() as session:
            export_files = exporter.export_all_formats(session)
        export_elapsed = datetime.now() - export_start

        # Get final statistics
        stats = db_manager.get_statistics()
        progress = db_manager.get_processing_progress()

        elapsed = datetime.now() - start_time
        end_time = datetime.now()

        logger.info("")
        logger.info("=" * 100)
        logger.info("✅ PIPELINE V2 COMPLETE!")
        logger.info("=" * 100)
        logger.info(f"Total elapsed time:    {elapsed}")
        logger.info(f"Companies processed:   {stats['companies']}")
        logger.info(f"Unique funding rounds: {stats['funding_rounds']}")
        logger.info(f"Total investors:       {stats['investors']}")
        logger.info(f"Duplicates removed:    {stats['duplicates_found']}")
        logger.info(f"Parallel workers used: {args.workers}")
        logger.info("")
        logger.info("Stage timings:")
        logger.info(f"  Stage 1 (Loading):       {stage1_elapsed}")
        logger.info(f"  Stage 2 (SEC):           {stage2_elapsed}")
        logger.info(f"  Stage 3 (Search):        {stage3_elapsed}")
        logger.info(f"  Stage 4 (Deduplication): {stage4_elapsed}")
        logger.info(f"  Export:                  {export_elapsed}")
        logger.info("")
        logger.info("Output files:")
        for format_type, filename in export_files.items():
            if filename:
                logger.info(f"  {format_type.upper():8} {filename}")
        logger.info("")

        # LLM stats
        llm_router.log_stats()

    except KeyboardInterrupt:
        logger.warning("\n\n⚠️  Pipeline interrupted by user")
        logger.info("Progress has been saved in database. Re-run to resume.")
        sys.exit(1)

    except Exception as e:
        logger.error(f"\n\n❌ Pipeline failed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
