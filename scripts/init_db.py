#!/usr/bin/env python3
"""
Database Initialization Script
Initializes the database schema based on config.yaml
"""

import os
import sys
import yaml
from dotenv import load_dotenv

# Load environment variables from parent directory
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.database import DatabaseManager, init_database, create_db_engine


def load_config():
    """Load configuration from YAML file"""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Initialize the database"""
    print("=" * 80)
    print("Funding Round Collection Engine V2 - Database Initialization")
    print("=" * 80)
    print()

    # Load configuration
    config = load_config()
    db_config = config['database']
    db_type = db_config.get('type', 'sqlite')

    print(f"Database type: {db_type}")

    if db_type == 'sqlite':
        db_path = db_config.get('sqlite', {}).get('path', 'data/funding_rounds.db')
        print(f"Database path: {db_path}")

        # Create directory if needed
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    elif db_type == 'postgresql':
        pg_config = db_config.get('postgresql', {})
        connection_string = pg_config.get('connection_string')
        if connection_string and connection_string.startswith('${'):
            # Environment variable placeholder, show that we're using env var
            print(f"PostgreSQL connection: Using environment variable")
        elif connection_string:
            # Show connection string (hide password for security)
            if '@' in connection_string:
                host_part = connection_string.split('@')[1].split('/')[0]
                db_part = connection_string.split('/')[-1].split('?')[0]
                print(f"PostgreSQL host: {host_part}")
                print(f"PostgreSQL database: {db_part}")
            else:
                print(f"PostgreSQL connection: Custom connection string")
        else:
            print(f"PostgreSQL host: {pg_config.get('host', 'localhost')}")
            print(f"PostgreSQL database: {pg_config.get('database', 'funding_rounds')}")

    print()
    print("Creating database schema...")

    # Create engine and initialize
    engine = create_db_engine(db_config)
    init_database(engine)

    print("✓ Database schema created successfully!")
    print()

    # Create database manager to verify
    db_manager = DatabaseManager(config)
    stats = db_manager.get_statistics()

    print("Database statistics:")
    print(f"  Companies: {stats['companies']}")
    print(f"  Funding rounds: {stats['funding_rounds']}")
    print(f"  Investors: {stats['investors']}")
    print(f"  Sources: {stats['sources']}")
    print()

    print("=" * 80)
    print("✓ Database initialization complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()
