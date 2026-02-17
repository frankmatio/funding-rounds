"""
Database Manager for Funding Round Collection Engine V2
Provides CRUD operations and transaction management
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (
    Company, FundingRound, Investor, LLMUsage, ProcessingStatus, Source,
    create_db_engine, get_session, init_database, round_investors
)

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manage database operations with transaction support"""

    def __init__(self, config: dict):
        """Initialize database connection"""
        self.config = config
        self.engine = create_db_engine(config['database'])
        init_database(self.engine)
        logger.info(f"✓ Database initialized: {config['database']['type']}")

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope for database operations"""
        session = get_session(self.engine)
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database transaction failed: {str(e)}")
            raise
        finally:
            session.close()

    # ===== COMPANY OPERATIONS =====

    def get_or_create_company(self, session: Session, name: str, cik: Optional[str] = None,
                               official_name: Optional[str] = None) -> Company:
        """Get existing company or create new one"""
        company = session.query(Company).filter_by(name=name).first()

        if not company:
            company = Company(name=name, cik=cik, official_name=official_name)
            session.add(company)
            session.flush()  # Get ID without committing

            # Create processing status
            status = ProcessingStatus(company_id=company.id)
            session.add(status)
            session.flush()

            logger.debug(f"Created new company: {name} (CIK: {cik})")
        else:
            # Update if new info available
            if cik and not company.cik:
                company.cik = cik
            if official_name and not company.official_name:
                company.official_name = official_name

        return company

    def get_company_by_name(self, name: str) -> Optional[Company]:
        """Get company by name"""
        with self.session_scope() as session:
            return session.query(Company).filter_by(name=name).first()

    def get_all_companies(self) -> List[Company]:
        """Get all companies"""
        with self.session_scope() as session:
            return session.query(Company).all()

    # ===== PROCESSING STATUS OPERATIONS =====

    def get_processing_status(self, session: Session, company_id: int) -> ProcessingStatus:
        """Get processing status for a company"""
        status = session.query(ProcessingStatus).filter_by(company_id=company_id).first()
        if not status:
            status = ProcessingStatus(company_id=company_id)
            session.add(status)
            session.flush()
        return status

    def update_stage1_status(self, session: Session, company_id: int, completed: bool = True):
        """Update Stage 1 (Resolution) status"""
        status = self.get_processing_status(session, company_id)
        status.stage1_resolved = completed
        status.stage1_completed_at = datetime.utcnow() if completed else None

    def update_stage2_status(self, session: Session, company_id: int, rounds_found: int,
                             completed: bool = True):
        """Update Stage 2 (SEC) status"""
        status = self.get_processing_status(session, company_id)
        status.stage2_sec_collected = completed
        status.stage2_completed_at = datetime.utcnow() if completed else None
        status.stage2_rounds_found = rounds_found

    def update_stage3_status(self, session: Session, company_id: int, rounds_found: int,
                             completed: bool = True):
        """Update Stage 3 (Search) status"""
        status = self.get_processing_status(session, company_id)
        status.stage3_search_extracted = completed
        status.stage3_completed_at = datetime.utcnow() if completed else None
        status.stage3_rounds_found = rounds_found

    def update_stage4_status(self, session: Session, company_id: int, unique_rounds: int,
                             completed: bool = True):
        """Update Stage 4 (Merge) status"""
        status = self.get_processing_status(session, company_id)
        status.stage4_merged = completed
        status.stage4_completed_at = datetime.utcnow() if completed else None
        status.stage4_unique_rounds = unique_rounds

    def reset_processing_status(self, stages: List[int] = None):
        """Reset processing status flags so companies get reprocessed.
        stages: list of stage numbers to reset (2, 3, 4). Defaults to all."""
        if stages is None:
            stages = [2, 3, 4]
        with self.session_scope() as session:
            records = session.query(ProcessingStatus).all()
            for status in records:
                if 2 in stages:
                    status.stage2_sec_collected = False
                    status.stage2_completed_at = None
                    status.stage2_rounds_found = 0
                if 3 in stages:
                    status.stage3_search_extracted = False
                    status.stage3_completed_at = None
                    status.stage3_rounds_found = 0
                if 4 in stages:
                    status.stage4_merged = False
                    status.stage4_completed_at = None
                    status.stage4_unique_rounds = 0
            logger.info(f"✓ Reset processing status for {len(records)} companies (stages {stages})")

    def get_companies_needing_stage(self, stage: int) -> List[Company]:
        """Get companies that haven't completed a specific stage"""
        with self.session_scope() as session:
            query = session.query(Company).join(ProcessingStatus)

            if stage == 1:
                query = query.filter(ProcessingStatus.stage1_resolved == False)
            elif stage == 2:
                query = query.filter(ProcessingStatus.stage2_sec_collected == False)
            elif stage == 3:
                query = query.filter(ProcessingStatus.stage3_search_extracted == False)
            elif stage == 4:
                query = query.filter(ProcessingStatus.stage4_merged == False)

            return query.all()

    def get_processing_progress(self) -> Dict:
        """Get overall processing progress statistics"""
        with self.session_scope() as session:
            total = session.query(Company).count()

            stage1_done = session.query(ProcessingStatus).filter_by(stage1_resolved=True).count()
            stage2_done = session.query(ProcessingStatus).filter_by(stage2_sec_collected=True).count()
            stage3_done = session.query(ProcessingStatus).filter_by(stage3_search_extracted=True).count()
            stage4_done = session.query(ProcessingStatus).filter_by(stage4_merged=True).count()

            return {
                'total_companies': total,
                'stage1_completed': stage1_done,
                'stage2_completed': stage2_done,
                'stage3_completed': stage3_done,
                'stage4_completed': stage4_done,
                'stage1_percent': (stage1_done / total * 100) if total > 0 else 0,
                'stage2_percent': (stage2_done / total * 100) if total > 0 else 0,
                'stage3_percent': (stage3_done / total * 100) if total > 0 else 0,
                'stage4_percent': (stage4_done / total * 100) if total > 0 else 0,
            }

    # ===== FUNDING ROUND OPERATIONS =====

    def add_funding_round(self, session: Session, company_id: int, round_data: dict,
                          source_type: str, confidence_score: str,
                          source_urls: Optional[List[str]] = None) -> FundingRound:
        """Add a new funding round"""
        funding_round = FundingRound(
            company_id=company_id,
            round_name=round_data.get('round_name'),
            date=round_data.get('date'),
            amount_raised_usd=round_data.get('amount_raised_usd'),
            pre_money_valuation_usd=round_data.get('pre_money_valuation_usd'),
            post_money_valuation_usd=round_data.get('post_money_valuation_usd'),
            lead_investor=round_data.get('lead_investor'),
            source_type=source_type,
            confidence_score=confidence_score,
            source_urls=source_urls,
            notes=round_data.get('notes'),
            raw_data=round_data
        )

        session.add(funding_round)
        session.flush()

        # Add investors if provided
        if 'all_investors' in round_data and round_data['all_investors']:
            for investor_name in round_data['all_investors']:
                if investor_name and investor_name.strip():
                    investor = self.get_or_create_investor(session, investor_name.strip())
                    funding_round.investors.append(investor)

        return funding_round

    def get_rounds_for_company(self, company_id: int, exclude_duplicates: bool = True) -> List[FundingRound]:
        """Get all funding rounds for a company"""
        with self.session_scope() as session:
            query = session.query(FundingRound).filter_by(company_id=company_id)
            if exclude_duplicates:
                query = query.filter_by(is_duplicate=False)
            return query.all()

    def get_all_rounds(self, exclude_duplicates: bool = True) -> List[FundingRound]:
        """Get all funding rounds"""
        with self.session_scope() as session:
            query = session.query(FundingRound)
            if exclude_duplicates:
                query = query.filter_by(is_duplicate=False)
            return query.all()

    def mark_as_duplicate(self, session: Session, duplicate_round_id: int, original_round_id: int):
        """Mark a round as duplicate of another"""
        duplicate_round = session.query(FundingRound).get(duplicate_round_id)
        if duplicate_round:
            duplicate_round.is_duplicate = True
            duplicate_round.duplicate_of_id = original_round_id

    # ===== INVESTOR OPERATIONS =====

    def get_or_create_investor(self, session: Session, name: str,
                                investor_type: Optional[str] = None) -> Investor:
        """Get existing investor or create new one"""
        investor = session.query(Investor).filter_by(name=name).first()

        if not investor:
            investor = Investor(name=name, investor_type=investor_type)
            session.add(investor)
            session.flush()
            logger.debug(f"Created new investor: {name}")

        return investor

    # ===== SOURCE OPERATIONS =====

    def add_source(self, session: Session, round_id: int, source_type: str,
                   url: Optional[str] = None, title: Optional[str] = None,
                   snippet: Optional[str] = None, llm_provider: Optional[str] = None,
                   llm_model: Optional[str] = None, extraction_confidence: Optional[str] = None) -> Source:
        """Add a data source for a funding round"""
        # Truncate to fit VARCHAR(500) column limits
        if title and len(title) > 490:
            title = title[:490] + '...'
        source = Source(
            round_id=round_id,
            source_type=source_type,
            url=url,
            title=title,
            snippet=snippet,
            llm_provider=llm_provider,
            llm_model=llm_model,
            extraction_confidence=extraction_confidence
        )

        session.add(source)
        session.flush()
        return source

    # ===== LLM USAGE TRACKING =====

    def log_llm_usage(self, provider_name: str, model_name: str, success: bool,
                      rate_limited: bool = False, latency_ms: Optional[float] = None,
                      input_tokens: int = 0, output_tokens: int = 0):
        """Log LLM API usage"""
        with self.session_scope() as session:
            today = datetime.utcnow().strftime('%Y-%m-%d')

            # Get or create usage record for today
            usage = session.query(LLMUsage).filter_by(
                provider_name=provider_name,
                model_name=model_name,
                date=today
            ).first()

            if not usage:
                usage = LLMUsage(
                    provider_name=provider_name,
                    model_name=model_name,
                    date=today
                )
                # Explicitly initialize integer fields to 0
                # SQLAlchemy Column(default=0) doesn't apply to Python objects immediately
                usage.total_calls = 0
                usage.successful_calls = 0
                usage.failed_calls = 0
                usage.rate_limited_calls = 0
                usage.total_input_tokens = 0
                usage.total_output_tokens = 0
                session.add(usage)

            # Update metrics
            usage.total_calls += 1
            if success:
                usage.successful_calls += 1
            else:
                usage.failed_calls += 1

            if rate_limited:
                usage.rate_limited_calls += 1

            usage.total_input_tokens += input_tokens
            usage.total_output_tokens += output_tokens

            # Update latency
            if latency_ms is not None:
                if usage.average_latency_ms is None:
                    usage.average_latency_ms = latency_ms
                else:
                    # Running average
                    total_latency = usage.average_latency_ms * (usage.total_calls - 1) + latency_ms
                    usage.average_latency_ms = total_latency / usage.total_calls

                usage.min_latency_ms = min(usage.min_latency_ms or float('inf'), latency_ms)
                usage.max_latency_ms = max(usage.max_latency_ms or 0, latency_ms)

    def get_llm_usage_stats(self, provider_name: Optional[str] = None) -> List[LLMUsage]:
        """Get LLM usage statistics"""
        with self.session_scope() as session:
            query = session.query(LLMUsage)
            if provider_name:
                query = query.filter_by(provider_name=provider_name)
            return query.order_by(LLMUsage.date.desc()).all()

    # ===== STATISTICS =====

    def get_statistics(self) -> Dict:
        """Get comprehensive database statistics"""
        with self.session_scope() as session:
            stats = {
                'companies': session.query(Company).count(),
                'funding_rounds': session.query(FundingRound).filter_by(is_duplicate=False).count(),
                'total_rounds_including_duplicates': session.query(FundingRound).count(),
                'investors': session.query(Investor).count(),
                'sources': session.query(Source).count(),
                'duplicates_found': session.query(FundingRound).filter_by(is_duplicate=True).count(),
            }

            # Rounds by source type
            source_counts = session.query(
                FundingRound.source_type,
                func.count(FundingRound.id)
            ).filter_by(is_duplicate=False).group_by(FundingRound.source_type).all()

            stats['rounds_by_source'] = {source: count for source, count in source_counts}

            # Total amount raised
            total_amount = session.query(
                func.sum(FundingRound.amount_raised_usd)
            ).filter_by(is_duplicate=False).scalar()

            stats['total_amount_raised_usd'] = float(total_amount) if total_amount else 0

            return stats
