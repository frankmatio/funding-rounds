"""
SEC EDGAR Form D Collector V2 with Multiple User Agent Rotation
Rotates between multiple SEC accounts to avoid rate limits
"""

import logging
import time
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)


class SECUserAgent:
    """Individual SEC user agent with rate limiting"""

    def __init__(self, name: str, user_agent: str):
        self.name = name
        self.user_agent = user_agent
        self.calls_made = 0
        self.last_call_time = 0
        self.lock = Lock()

        # SEC rate limit: 10 requests per second
        self.min_delay_seconds = 0.1  # 100ms between requests

    def can_make_request(self) -> bool:
        """Check if enough time has passed since last request"""
        with self.lock:
            current_time = time.time()
            time_since_last_call = current_time - self.last_call_time
            return time_since_last_call >= self.min_delay_seconds

    def wait_if_needed(self):
        """Wait if necessary to respect rate limit"""
        with self.lock:
            current_time = time.time()
            time_since_last_call = current_time - self.last_call_time

            if time_since_last_call < self.min_delay_seconds:
                wait_time = self.min_delay_seconds - time_since_last_call
                time.sleep(wait_time)

            self.last_call_time = time.time()
            self.calls_made += 1

    def get_headers(self) -> Dict[str, str]:
        """Get request headers with User-Agent"""
        return {
            'User-Agent': self.user_agent,
            'Accept-Encoding': 'gzip, deflate',
            'Host': 'www.sec.gov'
        }


class SECCollectorV2:
    """SEC EDGAR Form D collector with user agent rotation"""

    def __init__(self, config: dict, db_manager=None):
        """Initialize SEC collector with configuration"""
        import os
        self.config = config
        self.db_manager = db_manager

        # Initialize user agents from environment variables (preferred) or config
        self.user_agents = []

        # Try to load from environment variables first (SEC_USER_AGENT_1 through SEC_USER_AGENT_10)
        for i in range(1, 11):
            env_key = f'SEC_USER_AGENT_{i}'
            user_agent = os.getenv(env_key)
            if user_agent and user_agent.strip():
                agent = SECUserAgent(
                    name=f"Account {i}",
                    user_agent=user_agent.strip()
                )
                self.user_agents.append(agent)

        # If no env variables, fall back to config.yaml
        if not self.user_agents:
            for ua_config in config.get('sec_user_agents', []):
                agent = SECUserAgent(
                    name=ua_config['name'],
                    user_agent=ua_config['user_agent']
                )
                self.user_agents.append(agent)

        # Final fallback to single default user agent
        if not self.user_agents:
            default_ua = SECUserAgent(
                name="Default",
                user_agent=os.getenv('SEC_USER_AGENT', 'Joe B joe.malambo@mail.com')
            )
            self.user_agents.append(default_ua)
            logger.warning("No SEC user agents configured, using default")

        logger.info(f"✓ SEC Collector initialized with {len(self.user_agents)} user agents")

        # Round-robin counter
        self.current_agent_index = 0
        self.rotation_lock = Lock()

    def get_next_user_agent(self) -> SECUserAgent:
        """Get next user agent using round-robin"""
        with self.rotation_lock:
            agent = self.user_agents[self.current_agent_index]
            self.current_agent_index = (self.current_agent_index + 1) % len(self.user_agents)
            return agent

    def resolve_cik(self, company_name: str) -> Optional[Dict[str, str]]:
        """
        Resolve company name to CIK using SEC EDGAR API.
        Returns dict with 'cik' and 'official_name' or None if not found.
        """
        agent = self.get_next_user_agent()
        agent.wait_if_needed()

        try:
            # Use SEC's company tickers JSON endpoint
            url = "https://www.sec.gov/files/company_tickers.json"

            response = requests.get(url, headers=agent.get_headers(), timeout=10)
            response.raise_for_status()

            companies = response.json()

            # Search for company name
            company_lower = company_name.lower()

            for entry in companies.values():
                title_lower = entry['title'].lower()

                # Match if company name is in the title
                if company_lower in title_lower or title_lower in company_lower:
                    cik = str(entry['cik_str']).zfill(10)  # Pad to 10 digits
                    official_name = entry['title']

                    logger.info(f"  ✓ {company_name} → CIK: {cik} ({official_name})")

                    return {
                        'cik': cik,
                        'official_name': official_name
                    }

            logger.warning(f"  ✗ {company_name} → Not found in SEC database")
            return None

        except Exception as e:
            logger.error(f"  ✗ {company_name} → Error resolving CIK: {str(e)}")
            return None

    def fetch_form_d_filings(self, cik: str, company_name: str) -> List[Dict]:
        """
        Fetch Form D filings for a company.
        Returns list of funding rounds extracted from Form D filings.
        """
        agent = self.get_next_user_agent()
        agent.wait_if_needed()

        try:
            # Get recent filings
            url = f"https://data.sec.gov/submissions/CIK{cik}.json"

            response = requests.get(url, headers=agent.get_headers(), timeout=10)
            response.raise_for_status()

            data = response.json()
            recent_filings = data.get('filings', {}).get('recent', {})

            forms = recent_filings.get('form', [])
            filing_dates = recent_filings.get('filingDate', [])
            accession_numbers = recent_filings.get('accessionNumber', [])

            rounds = []

            # Find Form D filings
            for i, form in enumerate(forms):
                if form == 'D':
                    filing_date = filing_dates[i] if i < len(filing_dates) else None
                    accession_number = accession_numbers[i] if i < len(accession_numbers) else None

                    if accession_number:
                        # Fetch Form D details
                        round_data = self._parse_form_d(cik, accession_number, filing_date, company_name, agent)
                        if round_data:
                            rounds.append(round_data)

            if rounds:
                logger.info(f"  ✓ {company_name} → Found {len(rounds)} Form D filings")
            else:
                logger.info(f"  ○ {company_name} → No Form D filings found")

            return rounds

        except Exception as e:
            logger.error(f"  ✗ {company_name} → Error fetching Form D filings: {str(e)}")
            return []

    def _parse_form_d(self, cik: str, accession_number: str, filing_date: str,
                      company_name: str, agent: SECUserAgent) -> Optional[Dict]:
        """Parse a single Form D filing"""
        agent.wait_if_needed()

        try:
            # Construct Form D document URL
            accession_clean = accession_number.replace('-', '')
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_clean}/primary_doc.xml"

            response = requests.get(url, headers=agent.get_headers(), timeout=10)
            response.raise_for_status()

            # Parse XML
            root = ET.fromstring(response.content)

            # Define XML namespace
            ns = {'edgarSubmission': 'http://www.sec.gov/edgar/document/thirtypartyfiler/formsubmission'}

            # Extract offering data
            offering_data = root.find('.//edgarSubmission:offeringData', ns)

            if offering_data is None:
                return None

            # Extract amount
            total_offering_amount = offering_data.find('.//edgarSubmission:totalOfferingAmount', ns)
            amount_usd = None

            if total_offering_amount is not None and total_offering_amount.text:
                try:
                    amount_usd = float(total_offering_amount.text)
                except (ValueError, TypeError):
                    pass

            # Extract investors (if available)
            investors = []
            issuer_info = root.find('.//edgarSubmission:issuer', ns)

            round_data = {
                'company_name': company_name,
                'round_name': 'Form D Filing',
                'date': filing_date,
                'amount_raised_usd': amount_usd,
                'pre_money_valuation_usd': None,
                'post_money_valuation_usd': None,
                'lead_investor': None,
                'all_investors': investors,
                'source_type': 'SEC_FORM_D',
                'confidence_score': 'HIGH',
                'source_url': url,
                'notes': f'SEC Form D filing (Accession: {accession_number})'
            }

            return round_data

        except Exception as e:
            logger.debug(f"  Error parsing Form D {accession_number}: {str(e)}")
            return None

    def process_company(self, session, company) -> int:
        """
        Process a single company: resolve CIK and fetch Form D filings.
        Returns number of rounds found.
        """
        company_name = company.name

        # Check if already processed
        status = self.db_manager.get_processing_status(session, company.id)
        if status.stage2_sec_collected:
            logger.debug(f"[Stage 2] {company_name} already processed, skipping")
            return status.stage2_rounds_found

        logger.info(f"[Stage 2] Processing {company_name}...")

        # Stage 2.1: Resolve CIK if not already done
        if not company.cik:
            cik_data = self.resolve_cik(company_name)
            if cik_data:
                company.cik = cik_data['cik']
                company.official_name = cik_data['official_name']
            else:
                # Mark as processed even if CIK not found
                self.db_manager.update_stage2_status(session, company.id, rounds_found=0)
                return 0

        # Stage 2.2: Fetch Form D filings
        rounds = self.fetch_form_d_filings(company.cik, company_name)

        # Stage 2.3: Save to database
        for round_data in rounds:
            funding_round = self.db_manager.add_funding_round(
                session=session,
                company_id=company.id,
                round_data=round_data,
                source_type='SEC_FORM_D',
                confidence_score='HIGH',
                source_urls=[round_data.get('source_url')]
            )

            # Add source
            self.db_manager.add_source(
                session=session,
                round_id=funding_round.id,
                source_type='SEC_FORM_D',
                url=round_data.get('source_url'),
                title=f"SEC Form D - {round_data.get('date')}",
                snippet=round_data.get('notes')
            )

        # Mark stage as complete
        self.db_manager.update_stage2_status(session, company.id, rounds_found=len(rounds))

        return len(rounds)

    def get_user_agent_stats(self) -> List[Dict]:
        """Get statistics for all user agents"""
        return [
            {
                'name': agent.name,
                'calls_made': agent.calls_made,
                'user_agent': agent.user_agent
            }
            for agent in self.user_agents
        ]
