"""
Enhanced LLM Router V2 with Multiple Rotation Strategies
Supports: round_robin, priority, load_balanced
"""

import json
import logging
import os
import time
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when a rate limit is hit"""
    pass


class LLMProvider:
    """Individual LLM provider with rate limiting and tracking"""

    def __init__(self, name: str, config: dict, db_manager=None):
        self.name = name
        self.config = config
        self.db_manager = db_manager

        self.endpoint = config.get('endpoint', '')
        self.model = config.get('model', '')
        self.priority = config.get('priority', 999)
        self.rate_limit_rpm = config.get('rate_limit_rpm', 60)
        self.enabled = config.get('enabled', True)

        # Get API key from environment
        # Handle special cases for multiple accounts
        if name == 'openrouter_2':
            api_key_env = 'OPENROUTER_API_KEY_2'
        elif name == 'qwen':
            api_key_env = 'QWEN_API_KEY'
        else:
            api_key_env = config.get('api_key_env', f'{name.upper()}_API_KEY')

        self.api_key = os.getenv(api_key_env)

        # Rate limiting
        self.calls_this_minute = 0
        self.last_minute_reset = time.time()
        self.lock = Lock()

        # Statistics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.rate_limited_calls = 0
        self.total_latency_ms = 0

    def can_make_request(self) -> bool:
        """Check if we can make a request without hitting rate limit"""
        if not self.enabled or not self.api_key:
            return False

        with self.lock:
            current_time = time.time()

            # Reset counter every minute
            if current_time - self.last_minute_reset >= 60:
                self.calls_this_minute = 0
                self.last_minute_reset = current_time

            return self.calls_this_minute < self.rate_limit_rpm

    def increment_call_count(self):
        """Increment call counter"""
        with self.lock:
            self.calls_this_minute += 1
            self.total_calls += 1

    def call_llm(self, prompt: str, max_tokens: int = 4000, temperature: float = 0.0) -> Optional[str]:
        """Call the LLM provider"""
        if not self.can_make_request():
            raise RateLimitError(f"{self.name} rate limit exceeded ({self.rate_limit_rpm} RPM)")

        self.increment_call_count()
        start_time = time.time()

        try:
            if self.name == 'gemini':
                response = self._call_gemini(prompt, max_tokens, temperature)
            else:
                response = self._call_openai_compatible(prompt, max_tokens, temperature)

            latency_ms = (time.time() - start_time) * 1000
            self.successful_calls += 1
            self.total_latency_ms += latency_ms

            # Log to database if available
            if self.db_manager:
                self.db_manager.log_llm_usage(
                    provider_name=self.name,
                    model_name=self.model,
                    success=True,
                    latency_ms=latency_ms
                )

            logger.debug(f"✓ {self.name} call successful ({latency_ms:.0f}ms)")
            return response

        except RateLimitError:
            self.rate_limited_calls += 1
            raise

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.failed_calls += 1

            # Log to database if available
            if self.db_manager:
                self.db_manager.log_llm_usage(
                    provider_name=self.name,
                    model_name=self.model,
                    success=False,
                    latency_ms=latency_ms
                )

            logger.error(f"✗ {self.name} call failed: {str(e)}")
            raise

    def _call_gemini(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Call Google Gemini API"""
        url = f"{self.endpoint}?key={self.api_key}"

        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens
            }
        }

        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()

        if 'candidates' not in data or len(data['candidates']) == 0:
            raise ValueError("No response from Gemini")

        return data['candidates'][0]['content']['parts'][0]['text']

    def _call_openai_compatible(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Call OpenAI-compatible APIs (Groq, Mistral, Fireworks, etc.)"""
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'model': self.model,
            'messages': [
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': max_tokens,
            'temperature': temperature
        }

        response = requests.post(self.endpoint, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        data = response.json()
        return data['choices'][0]['message']['content']

    def get_stats(self) -> Dict:
        """Get provider statistics"""
        avg_latency = self.total_latency_ms / self.successful_calls if self.successful_calls > 0 else 0

        return {
            'name': self.name,
            'total_calls': self.total_calls,
            'successful_calls': self.successful_calls,
            'failed_calls': self.failed_calls,
            'rate_limited_calls': self.rate_limited_calls,
            'success_rate': (self.successful_calls / self.total_calls * 100) if self.total_calls > 0 else 0,
            'average_latency_ms': avg_latency,
            'enabled': self.enabled,
            'has_api_key': bool(self.api_key)
        }


class LLMRouterV2:
    """Enhanced LLM router with multiple rotation strategies"""

    def __init__(self, config: dict, db_manager=None):
        """Initialize router with configuration"""
        self.config = config
        self.db_manager = db_manager

        llm_config = config.get('llm_providers', {})
        self.rotation_strategy = llm_config.get('rotation_strategy', 'round_robin')
        self.max_retries = llm_config.get('max_retries', 3)
        self.timeout_seconds = llm_config.get('timeout_seconds', 30)

        # Initialize providers
        self.providers = []
        for provider_config in llm_config.get('providers', []):
            provider = LLMProvider(
                name=provider_config['name'],
                config=provider_config,
                db_manager=db_manager
            )
            self.providers.append(provider)

        # Filter to enabled providers with API keys
        self.active_providers = [p for p in self.providers if p.enabled and p.api_key]

        if not self.active_providers:
            logger.warning("⚠️ No active LLM providers available!")
        else:
            logger.info(f"✓ LLM Router initialized with {len(self.active_providers)} active providers")
            logger.info(f"✓ Rotation strategy: {self.rotation_strategy}")

        # Round-robin counter
        self.round_robin_index = 0
        self.round_robin_lock = Lock()

    def _get_next_provider_round_robin(self) -> Optional[LLMProvider]:
        """Get next provider using round-robin strategy"""
        if not self.active_providers:
            return None

        with self.round_robin_lock:
            attempts = 0
            max_attempts = len(self.active_providers)

            while attempts < max_attempts:
                provider = self.active_providers[self.round_robin_index]
                self.round_robin_index = (self.round_robin_index + 1) % len(self.active_providers)

                if provider.can_make_request():
                    return provider

                attempts += 1

            return None  # All providers rate limited

    def _get_next_provider_priority(self) -> Optional[LLMProvider]:
        """Get next provider using priority strategy (lowest priority number first)"""
        sorted_providers = sorted(self.active_providers, key=lambda p: p.priority)

        for provider in sorted_providers:
            if provider.can_make_request():
                return provider

        return None  # All providers rate limited

    def _get_next_provider_load_balanced(self) -> Optional[LLMProvider]:
        """Get next provider using load balancing (least used first)"""
        available_providers = [p for p in self.active_providers if p.can_make_request()]

        if not available_providers:
            return None

        # Sort by usage (least used first)
        sorted_providers = sorted(available_providers, key=lambda p: p.total_calls)
        return sorted_providers[0]

    def get_next_provider(self) -> Optional[LLMProvider]:
        """Get next provider based on rotation strategy"""
        if self.rotation_strategy == 'round_robin':
            return self._get_next_provider_round_robin()
        elif self.rotation_strategy == 'priority':
            return self._get_next_provider_priority()
        elif self.rotation_strategy == 'load_balanced':
            return self._get_next_provider_load_balanced()
        else:
            logger.warning(f"Unknown rotation strategy: {self.rotation_strategy}, using round_robin")
            return self._get_next_provider_round_robin()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, RateLimitError)),
        reraise=True
    )
    def generate(self, prompt: str, max_tokens: int = 4000, temperature: float = 0.0) -> Optional[str]:
        """Generate response using best available provider"""
        provider = self.get_next_provider()

        if not provider:
            logger.error("✗ All LLM providers are rate limited or unavailable")
            # Wait 60 seconds and try again
            logger.info("⏳ Waiting 60 seconds for rate limits to reset...")
            time.sleep(60)
            provider = self.get_next_provider()

            if not provider:
                raise Exception("All LLM providers exhausted after waiting for rate limit reset")

        logger.debug(f"Using provider: {provider.name} ({self.rotation_strategy} strategy)")

        try:
            return provider.call_llm(prompt, max_tokens, temperature)

        except RateLimitError as e:
            logger.warning(f"Rate limit hit for {provider.name}, trying next provider...")
            # Retry will automatically try next provider
            raise

    def get_all_stats(self) -> Dict:
        """Get statistics for all providers"""
        return {
            'rotation_strategy': self.rotation_strategy,
            'total_providers': len(self.providers),
            'active_providers': len(self.active_providers),
            'providers': [p.get_stats() for p in self.providers]
        }

    def log_stats(self):
        """Log current statistics"""
        stats = self.get_all_stats()

        logger.info(f"\n{'=' * 80}")
        logger.info("LLM ROUTER STATISTICS")
        logger.info(f"{'=' * 80}")
        logger.info(f"Strategy: {stats['rotation_strategy']}")
        logger.info(f"Active providers: {stats['active_providers']} / {stats['total_providers']}")
        logger.info("")

        for provider_stats in stats['providers']:
            name = provider_stats['name']
            enabled = "✓" if provider_stats['enabled'] else "✗"
            has_key = "✓" if provider_stats['has_api_key'] else "✗"

            logger.info(f"{name:15} | Enabled: {enabled} | API Key: {has_key}")

            if provider_stats['total_calls'] > 0:
                logger.info(f"  Total calls: {provider_stats['total_calls']}")
                logger.info(f"  Success rate: {provider_stats['success_rate']:.1f}%")
                logger.info(f"  Avg latency: {provider_stats['average_latency_ms']:.0f}ms")
                logger.info(f"  Rate limited: {provider_stats['rate_limited_calls']}")
            logger.info("")

        logger.info(f"{'=' * 80}\n")
