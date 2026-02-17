"""
Database-Based Funding Round Deduplicator V2
Identifies and marks duplicate rounds using smart matching
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from .database.models import FundingRound

logger = logging.getLogger(__name__)


class DeduplicatorV2:
    """Deduplicate funding rounds in the database"""

    def __init__(self, config: dict, db_manager=None):
        """Initialize deduplicator"""
        self.config = config
        self.db_manager = db_manager

        dedup_config = config.get('deduplication', {})
        self.date_proximity_days = dedup_config.get('date_proximity_days', 90)
        self.amount_similarity_threshold = dedup_config.get('amount_similarity_threshold', 0.10)
        self.enable_fuzzy_matching = dedup_config.get('enable_fuzzy_matching', True)

        logger.info(f"✓ Deduplicator initialized")
        logger.info(f"  Date proximity: {self.date_proximity_days} days")
        logger.info(f"  Amount similarity threshold: {self.amount_similarity_threshold * 100}%")
        logger.info(f"  Fuzzy matching: {self.enable_fuzzy_matching}")

    def parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object"""
        if not date_str:
            return None

        # Try different date formats
        formats = [
            '%Y-%m-%d',
            '%Y-%m',
            '%Y',
            '%m/%d/%Y',
            '%d/%m/%Y',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except (ValueError, TypeError):
                continue

        return None

    def dates_are_close(self, date1: Optional[str], date2: Optional[str]) -> bool:
        """Check if two dates are within proximity threshold"""
        dt1 = self.parse_date(date1)
        dt2 = self.parse_date(date2)

        if not dt1 or not dt2:
            return False

        diff_days = abs((dt1 - dt2).days)
        return diff_days <= self.date_proximity_days

    def amounts_are_similar(self, amount1: Optional[float], amount2: Optional[float]) -> bool:
        """Check if two amounts are similar within threshold"""
        if not amount1 or not amount2:
            return False

        larger = max(amount1, amount2)
        smaller = min(amount1, amount2)

        if larger == 0:
            return smaller == 0

        diff_percent = abs(larger - smaller) / larger
        return diff_percent <= self.amount_similarity_threshold

    def round_names_match(self, name1: Optional[str], name2: Optional[str]) -> bool:
        """Check if round names match"""
        if not name1 or not name2:
            return False

        # Normalize round names
        name1_norm = name1.lower().strip()
        name2_norm = name2.lower().strip()

        # Exact match
        if name1_norm == name2_norm:
            return True

        # Extract series letter/number
        series_keywords = ['seed', 'series a', 'series b', 'series c', 'series d',
                          'series e', 'series f', 'series g', 'series h']

        for keyword in series_keywords:
            if keyword in name1_norm and keyword in name2_norm:
                return True

        return False

    def are_duplicates(self, round1: FundingRound, round2: FundingRound) -> bool:
        """
        Check if two funding rounds are duplicates.
        Duplicates if:
        1. Same company AND
        2. Dates within proximity threshold AND
        3. (Amounts are similar OR Round names match)
        """
        # Must be same company
        if round1.company_id != round2.company_id:
            return False

        # Check date proximity
        dates_close = self.dates_are_close(round1.date, round2.date)

        if not dates_close:
            return False

        # Check amount similarity or round name match
        amounts_similar = self.amounts_are_similar(round1.amount_raised_usd, round2.amount_raised_usd)
        names_match = self.round_names_match(round1.round_name, round2.round_name)

        return amounts_similar or names_match

    def deduplicate_company(self, session, company) -> int:
        """
        Deduplicate rounds for a single company.
        Returns number of duplicates found.
        """
        company_name = company.name

        # Check if already processed
        status = self.db_manager.get_processing_status(session, company.id)
        if status.stage4_merged:
            logger.debug(f"[Stage 4] {company_name} already deduplicated, skipping")
            return 0

        logger.info(f"[Stage 4] Deduplicating {company_name}...")

        # Get all rounds for this company
        rounds = session.query(FundingRound).filter_by(
            company_id=company.id,
            is_duplicate=False
        ).all()

        if len(rounds) <= 1:
            logger.info(f"  ○ {company_name} → {len(rounds)} rounds (no duplicates possible)")
            self.db_manager.update_stage4_status(session, company.id, unique_rounds=len(rounds))
            return 0

        duplicates_found = 0

        # Compare each pair of rounds
        for i in range(len(rounds)):
            for j in range(i + 1, len(rounds)):
                round1 = rounds[i]
                round2 = rounds[j]

                if self.are_duplicates(round1, round2):
                    # Keep the higher confidence one
                    if round1.confidence_score == 'HIGH' and round2.confidence_score != 'HIGH':
                        # Keep round1, mark round2 as duplicate
                        self.db_manager.mark_as_duplicate(session, round2.id, round1.id)
                        duplicates_found += 1
                        logger.debug(f"    Duplicate: {round2.round_name} ({round2.date}) -> kept {round1.round_name} ({round1.date})")

                    elif round2.confidence_score == 'HIGH' and round1.confidence_score != 'HIGH':
                        # Keep round2, mark round1 as duplicate
                        self.db_manager.mark_as_duplicate(session, round1.id, round2.id)
                        duplicates_found += 1
                        logger.debug(f"    Duplicate: {round1.round_name} ({round1.date}) -> kept {round2.round_name} ({round2.date})")

                    else:
                        # Same confidence, keep the one with more complete data
                        round1_completeness = sum([
                            bool(round1.amount_raised_usd),
                            bool(round1.pre_money_valuation_usd),
                            bool(round1.post_money_valuation_usd),
                            bool(round1.lead_investor),
                        ])

                        round2_completeness = sum([
                            bool(round2.amount_raised_usd),
                            bool(round2.pre_money_valuation_usd),
                            bool(round2.post_money_valuation_usd),
                            bool(round2.lead_investor),
                        ])

                        if round1_completeness >= round2_completeness:
                            self.db_manager.mark_as_duplicate(session, round2.id, round1.id)
                            duplicates_found += 1
                            logger.debug(f"    Duplicate: {round2.round_name} ({round2.date}) -> kept {round1.round_name} ({round1.date})")
                        else:
                            self.db_manager.mark_as_duplicate(session, round1.id, round2.id)
                            duplicates_found += 1
                            logger.debug(f"    Duplicate: {round1.round_name} ({round1.date}) -> kept {round2.round_name} ({round2.date})")

        # Count unique rounds (non-duplicates)
        unique_rounds = session.query(FundingRound).filter_by(
            company_id=company.id,
            is_duplicate=False
        ).count()

        # Mark stage as complete
        self.db_manager.update_stage4_status(session, company.id, unique_rounds=unique_rounds)

        if duplicates_found > 0:
            logger.info(f"  ✓ {company_name} → {duplicates_found} duplicates removed, {unique_rounds} unique rounds")
        else:
            logger.info(f"  ○ {company_name} → {unique_rounds} unique rounds (no duplicates)")

        return duplicates_found

    def deduplicate_all(self, session) -> dict:
        """
        Deduplicate all companies.
        Returns statistics.
        """
        logger.info("=" * 80)
        logger.info("STAGE 4: DEDUPLICATION")
        logger.info("=" * 80)

        companies = session.query(FundingRound.company_id).distinct().all()
        total_companies = len(companies)

        total_duplicates = 0

        for i, (company_id,) in enumerate(companies, 1):
            company = session.query(FundingRound).filter_by(company_id=company_id).first().company
            duplicates = self.deduplicate_company(session, company)
            total_duplicates += duplicates

            if i % 100 == 0:
                logger.info(f"  Progress: {i}/{total_companies} companies ({i/total_companies*100:.1f}%)")

        # Get final statistics
        total_rounds = session.query(FundingRound).count()
        unique_rounds = session.query(FundingRound).filter_by(is_duplicate=False).count()

        stats = {
            'total_companies': total_companies,
            'total_rounds': total_rounds,
            'unique_rounds': unique_rounds,
            'duplicates_removed': total_duplicates,
            'deduplication_rate': (total_duplicates / total_rounds * 100) if total_rounds > 0 else 0
        }

        logger.info("")
        logger.info(f"Deduplication complete:")
        logger.info(f"  Total rounds: {total_rounds}")
        logger.info(f"  Unique rounds: {unique_rounds}")
        logger.info(f"  Duplicates removed: {total_duplicates}")
        logger.info(f"  Deduplication rate: {stats['deduplication_rate']:.1f}%")
        logger.info("")

        return stats
