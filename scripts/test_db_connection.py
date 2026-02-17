#!/usr/bin/env python3
"""
Test database connection for Oracle Cloud deployment
"""

import os
import sys
import yaml
from pathlib import Path

# Add v2_parallel_db directory to path (where src/ is located)
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

def test_connection():
    """Test database connection"""
    print("=" * 80)
    print("DATABASE CONNECTION TEST")
    print("=" * 80)
    print()

    # Load environment (.env is in parent of v2_parallel_db)
    env_path = Path(__file__).parent.parent.parent / '.env'
    if not env_path.exists():
        print(f"❌ ERROR: .env file not found at {env_path}")
        print("   Please create .env file with DATABASE_URL and API keys")
        return False

    load_dotenv(env_path)
    print(f"✓ Loaded environment from {env_path}")

    # Load config
    config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
    if not config_path.exists():
        print(f"❌ ERROR: config.yaml not found at {config_path}")
        return False

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    print(f"✓ Loaded configuration from {config_path}")
    print()

    # Test database connection
    print("Testing database connection...")
    print("-" * 80)

    try:
        from src.database import DatabaseManager

        db_config = config.get('database', {})
        db_type = db_config.get('type', 'sqlite')

        print(f"Database type: {db_type}")

        if db_type == 'postgresql':
            database_url = os.getenv('DATABASE_URL')
            if not database_url:
                print("❌ ERROR: DATABASE_URL not set in .env")
                return False

            # Mask password in URL for display
            masked_url = database_url
            if '@' in masked_url:
                parts = masked_url.split('@')
                if ':' in parts[0]:
                    user_pass = parts[0].split('://')[-1]
                    user = user_pass.split(':')[0]
                    masked_url = masked_url.replace(user_pass, f"{user}:***")

            print(f"Connection string: {masked_url}")

        print()
        print("Attempting connection...")

        db_manager = DatabaseManager(config)

        # Test query
        from sqlalchemy import text
        with db_manager.session_scope() as session:
            result = session.execute(text("SELECT 1")).fetchone()
            if result:
                print("✓ Connection successful!")

                # Get database info
                if db_type == 'postgresql':
                    version_result = session.execute(
                        text("SELECT version()")
                    ).fetchone()
                    if version_result:
                        print(f"✓ Database version: {version_result[0][:80]}...")

        print()
        print("-" * 80)
        print("Database statistics:")
        stats = db_manager.get_statistics()
        print(f"  Companies:      {stats['companies']}")
        print(f"  Funding rounds: {stats['funding_rounds']}")
        print(f"  Investors:      {stats['investors']}")
        print(f"  Duplicates:     {stats['duplicates_found']}")

        print()
        print("=" * 80)
        print("✅ DATABASE CONNECTION TEST PASSED")
        print("=" * 80)
        return True

    except Exception as e:
        print()
        print("=" * 80)
        print("❌ DATABASE CONNECTION TEST FAILED")
        print("=" * 80)
        print(f"Error: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        return False


def test_llm_providers():
    """Test LLM provider availability"""
    print()
    print("=" * 80)
    print("LLM PROVIDERS TEST")
    print("=" * 80)
    print()

    try:
        env_path = Path(__file__).parent.parent.parent / '.env'
        load_dotenv(env_path)

        config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        from src.database import DatabaseManager
        from src.llm_router_v2 import LLMRouterV2

        db_manager = DatabaseManager(config)
        router = LLMRouterV2(config, db_manager)

        print(f"Total providers configured: {len(router.providers)}")
        print()

        available_count = 0
        for provider in router.providers:
            status = "✓ Available" if provider.api_key else "✗ Missing API key"
            if provider.api_key:
                available_count += 1
            print(f"  {provider.name:15} - {status}")

        print()
        print(f"Available providers: {available_count}/{len(router.providers)}")

        if available_count == 0:
            print("⚠️  WARNING: No LLM providers available")
            return False
        else:
            print("✓ LLM providers ready")
            return True

    except Exception as e:
        print(f"❌ Error testing LLM providers: {str(e)}")
        return False


def test_sec_agents():
    """Test SEC user agent availability"""
    print()
    print("=" * 80)
    print("SEC USER AGENTS TEST")
    print("=" * 80)
    print()

    try:
        env_path = Path(__file__).parent.parent.parent / '.env'
        load_dotenv(env_path)

        config_path = Path(__file__).parent.parent / 'config' / 'config.yaml'
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        from src.database import DatabaseManager
        from src.sec_collector_v2 import SECCollectorV2

        db_manager = DatabaseManager(config)
        sec_collector = SECCollectorV2(config, db_manager)

        print(f"Total SEC user agents: {len(sec_collector.user_agents)}")
        print()

        for i, agent in enumerate(sec_collector.user_agents, 1):
            # Mask email for display
            masked_ua = agent.user_agent
            if '@' in masked_ua:
                parts = masked_ua.split()
                if len(parts) >= 2 and '@' in parts[1]:
                    email = parts[1]
                    email_parts = email.split('@')
                    if len(email_parts) == 2:
                        masked_email = email_parts[0][:3] + '***@' + email_parts[1]
                        masked_ua = f"{parts[0]} {masked_email}"

            print(f"  Agent {i}: {masked_ua}")

        print()
        if len(sec_collector.user_agents) > 0:
            print("✓ SEC user agents ready")
            return True
        else:
            print("⚠️  WARNING: No SEC user agents configured")
            return False

    except Exception as e:
        print(f"❌ Error testing SEC agents: {str(e)}")
        return False


if __name__ == "__main__":
    print()
    db_ok = test_connection()
    llm_ok = test_llm_providers()
    sec_ok = test_sec_agents()

    print()
    print("=" * 80)
    print("OVERALL STATUS")
    print("=" * 80)
    print(f"Database:     {'✓ READY' if db_ok else '✗ FAILED'}")
    print(f"LLM Providers: {'✓ READY' if llm_ok else '✗ FAILED'}")
    print(f"SEC Agents:    {'✓ READY' if sec_ok else '✗ FAILED'}")
    print()

    if db_ok and llm_ok and sec_ok:
        print("✅ ALL SYSTEMS READY FOR DEPLOYMENT")
        sys.exit(0)
    else:
        print("❌ DEPLOYMENT NOT READY - Fix errors above")
        sys.exit(1)
