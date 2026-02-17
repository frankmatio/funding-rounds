"""
Search-Based Funding Round Extractor V2 with Database Storage
Uses DuckDuckGo search + LLM extraction, stores directly in database
"""

import json
import logging
import time
from typing import Dict, List, Optional

from ddgs import DDGS

from .llm_router_v2 import LLMRouterV2

logger = logging.getLogger(__name__)


class SearchExtractorV2:
    """Extract funding data using web search and LLM analysis with database storage"""

    def __init__(self, config: dict, llm_router: LLMRouterV2, db_manager=None):
        """Initialize search extractor"""
        self.config = config
        self.llm_router = llm_router
        self.db_manager = db_manager

        search_config = config.get('search', {})
        self.max_results_per_query = search_config.get('max_results_per_query', 4)
        self.queries_per_company = search_config.get('queries_per_company', 8)
        self.politeness_delay = search_config.get('politeness_delay_seconds', 1)
        self.authoritative_sources = search_config.get('authoritative_sources', [])

        logger.info(f"✓ Search Extractor initialized")
        logger.info(f"  Max results per query: {self.max_results_per_query}")
        logger.info(f"  Queries per company: {self.queries_per_company}")
        logger.info(f"  Politeness delay: {self.politeness_delay}s")

    def generate_search_queries(self, company_name: str) -> List[str]:
        """Generate targeted search queries for a company"""
        return [
            f'site:techcrunch.com "{company_name}" funding raised Series',
            f'site:crunchbase.com "{company_name}" funding rounds',
            f'site:reuters.com OR site:bloomberg.com "{company_name}" raises funding',
            f'site:pitchbook.com OR site:cbinsights.com "{company_name}" venture capital',
            f'site:theinformation.com OR site:axios.com "{company_name}" funding',
            f'site:venturebeat.com OR site:geekwire.com "{company_name}" raises',
            f'site:wsj.com OR site:ft.com OR site:forbes.com "{company_name}" investment',
            f'"{company_name}" funding history seed series valuation investors'
        ]

    def perform_search(self, query: str) -> List[Dict[str, str]]:
        """Perform DuckDuckGo search and return results"""
        try:
            ddgs = DDGS()
            results = ddgs.text(query, max_results=self.max_results_per_query)

            search_results = []
            for result in results:
                search_results.append({
                    'title': result.get('title', ''),
                    'url': result.get('href', ''),
                    'snippet': result.get('body', '')
                })

            return search_results

        except Exception as e:
            logger.error(f"Search error for query '{query}': {str(e)}")
            return []

    def extract_funding_rounds_from_search(self, company_name: str, search_results: List[Dict]) -> List[Dict]:
        """Use LLM to extract funding rounds from search results"""
        if not search_results:
            return []

        # Build search results text for LLM
        search_text = ""
        for i, result in enumerate(search_results, 1):
            search_text += f"\n\n--- Result {i} ---\n"
            search_text += f"Title: {result['title']}\n"
            search_text += f"URL: {result['url']}\n"
            search_text += f"Snippet: {result['snippet']}\n"

        # LLM prompt
        prompt = f"""You are a financial data analyst extracting funding round information from web search results.

Company: {company_name}

Search Results:
{search_text}

Extract ALL funding rounds mentioned for {company_name}. For each round, extract:
- round_name (e.g., "Seed", "Series A", "Series B", "Series C", etc.)
- date (YYYY-MM-DD or YYYY-MM or YYYY)
- amount_raised_usd (number only, in USD)
- pre_money_valuation_usd (if mentioned, number only)
- post_money_valuation_usd (if mentioned, number only)
- lead_investor (primary investor if mentioned)
- all_investors (list of all investors mentioned)
- source_url (which URL this data came from)

Return ONLY a valid JSON array of funding rounds. If no funding rounds are found, return an empty array [].

Example format:
[
  {{{{
    "round_name": "Series A",
    "date": "2020-05-15",
    "amount_raised_usd": 50000000,
    "pre_money_valuation_usd": null,
    "post_money_valuation_usd": 250000000,
    "lead_investor": "Sequoia Capital",
    "all_investors": ["Sequoia Capital", "Andreessen Horowitz"],
    "source_url": "https://techcrunch.com/..."
  }}}}
]

JSON array:"""

        try:
            response = self.llm_router.generate(prompt, max_tokens=4000, temperature=0.0)

            if not response:
                logger.warning(f"No LLM response for {company_name}")
                return []

            # Extract JSON from response
            response = response.strip()

            # Try to find JSON array in response
            start_idx = response.find('[')
            end_idx = response.rfind(']')

            if start_idx == -1 or end_idx == -1:
                logger.warning(f"No JSON array found in LLM response for {company_name}")
                return []

            json_str = response[start_idx:end_idx + 1]
            rounds = json.loads(json_str)

            if not isinstance(rounds, list):
                logger.warning(f"LLM response is not a list for {company_name}")
                return []

            # Add company name to each round
            for round_data in rounds:
                round_data['company_name'] = company_name

            logger.debug(f"Extracted {len(rounds)} rounds for {company_name} from LLM")
            return rounds

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {company_name}: {str(e)}")
            logger.debug(f"Raw response: {response[:500]}")
            return []

        except Exception as e:
            logger.error(f"LLM extraction error for {company_name}: {str(e)}")
            return []

    def process_company(self, session, company) -> int:
        """
        Process a single company: search the web and extract funding rounds.
        Returns number of rounds found.
        """
        company_name = company.name

        # Check if already processed
        status = self.db_manager.get_processing_status(session, company.id)
        if status.stage3_search_extracted:
            logger.debug(f"[Stage 3] {company_name} already processed, skipping")
            return status.stage3_rounds_found

        logger.info(f"[Stage 3] Processing {company_name}...")

        # Stage 3.1: Generate search queries
        queries = self.generate_search_queries(company_name)

        # Stage 3.2: Perform searches
        all_search_results = []

        for query in queries:
            logger.debug(f"  Searching: {query[:80]}...")
            results = self.perform_search(query)

            if results:
                all_search_results.extend(results)
                logger.debug(f"    Found {len(results)} results")

            # Politeness delay
            time.sleep(self.politeness_delay)

        if not all_search_results:
            logger.warning(f"  ✗ {company_name} → No search results found")
            self.db_manager.update_stage3_status(session, company.id, rounds_found=0)
            return 0

        logger.info(f"  Found {len(all_search_results)} total search results")

        # Stage 3.3: Extract funding rounds using LLM
        rounds = self.extract_funding_rounds_from_search(company_name, all_search_results)

        if not rounds:
            logger.warning(f"  ✗ {company_name} → No funding rounds extracted")
            self.db_manager.update_stage3_status(session, company.id, rounds_found=0)
            return 0

        # Stage 3.4: Save to database
        for round_data in rounds:
            funding_round = self.db_manager.add_funding_round(
                session=session,
                company_id=company.id,
                round_data=round_data,
                source_type='WEB_SEARCH',
                confidence_score='MEDIUM',
                source_urls=[round_data.get('source_url')] if round_data.get('source_url') else None
            )

            # Add source
            source_url = round_data.get('source_url')
            if source_url:
                # Find the search result that matches this URL
                matching_result = next(
                    (r for r in all_search_results if r.get('url') == source_url),
                    None
                )

                self.db_manager.add_source(
                    session=session,
                    round_id=funding_round.id,
                    source_type='WEB_SEARCH',
                    url=source_url,
                    title=matching_result.get('title') if matching_result else None,
                    snippet=matching_result.get('snippet') if matching_result else None,
                    llm_provider=self.llm_router.rotation_strategy,
                    extraction_confidence='MEDIUM'
                )

        # Mark stage as complete
        self.db_manager.update_stage3_status(session, company.id, rounds_found=len(rounds))

        logger.info(f"  ✓ {company_name} → {len(rounds)} rounds extracted")

        return len(rounds)
