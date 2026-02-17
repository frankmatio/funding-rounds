"""
SQLAlchemy Database Models for Funding Round Collection Engine V2
Supports both SQLite (development) and PostgreSQL (production)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Table, Text, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

Base = declarative_base()

# Many-to-many relationship table for rounds and investors
round_investors = Table(
    'round_investors',
    Base.metadata,
    Column('round_id', Integer, ForeignKey('funding_rounds.id'), primary_key=True),
    Column('investor_id', Integer, ForeignKey('investors.id'), primary_key=True)
)


class Company(Base):
    """Company entity with SEC identifiers"""
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False, unique=True, index=True)
    cik = Column(String(20), nullable=True, index=True)
    official_name = Column(String(500), nullable=True)

    # Relationships
    funding_rounds = relationship('FundingRound', back_populates='company', cascade='all, delete-orphan')
    processing_status = relationship('ProcessingStatus', back_populates='company', uselist=False, cascade='all, delete-orphan')

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Company(name='{self.name}', cik='{self.cik}')>"


class FundingRound(Base):
    """Funding round with comprehensive details"""
    __tablename__ = 'funding_rounds'

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False, index=True)

    # Round details
    round_name = Column(String(100), nullable=True)  # e.g., "Series A", "Seed"
    date = Column(String(50), nullable=True)
    amount_raised_usd = Column(Float, nullable=True)
    pre_money_valuation_usd = Column(Float, nullable=True)
    post_money_valuation_usd = Column(Float, nullable=True)

    # Lead investor
    lead_investor = Column(String(500), nullable=True)

    # All investors (many-to-many relationship)
    investors = relationship('Investor', secondary=round_investors, back_populates='funding_rounds')

    # Data provenance
    source_type = Column(String(50), nullable=False)  # 'SEC_FORM_D' or 'WEB_SEARCH'
    confidence_score = Column(String(20), nullable=False)  # 'HIGH', 'MEDIUM', 'LOW'
    source_urls = Column(JSON, nullable=True)  # List of source URLs

    # Additional metadata
    notes = Column(Text, nullable=True)
    raw_data = Column(JSON, nullable=True)  # Store original extracted data

    # Deduplication tracking
    is_duplicate = Column(Boolean, default=False, nullable=False)
    duplicate_of_id = Column(Integer, ForeignKey('funding_rounds.id'), nullable=True)

    # Relationships
    company = relationship('Company', back_populates='funding_rounds')
    sources = relationship('Source', back_populates='funding_round', cascade='all, delete-orphan')

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<FundingRound(company='{self.company.name if self.company else 'Unknown'}', round='{self.round_name}', amount=${self.amount_raised_usd})>"


class Investor(Base):
    """Investor entity (venture capital firms, angels, etc.)"""
    __tablename__ = 'investors'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(500), nullable=False, unique=True, index=True)
    investor_type = Column(String(50), nullable=True)  # 'VC', 'Angel', 'Corporate', etc.

    # Relationships
    funding_rounds = relationship('FundingRound', secondary=round_investors, back_populates='investors')

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Investor(name='{self.name}')>"


class Source(Base):
    """Data source tracking for each funding round"""
    __tablename__ = 'sources'

    id = Column(Integer, primary_key=True, autoincrement=True)
    round_id = Column(Integer, ForeignKey('funding_rounds.id'), nullable=False, index=True)

    # Source details
    source_type = Column(String(50), nullable=False)  # 'SEC_FORM_D', 'TECHCRUNCH', 'CRUNCHBASE', etc.
    url = Column(String(2000), nullable=True)
    title = Column(String(500), nullable=True)
    snippet = Column(Text, nullable=True)

    # LLM extraction details
    llm_provider = Column(String(50), nullable=True)  # 'gemini', 'groq', 'mistral', etc.
    llm_model = Column(String(100), nullable=True)
    extraction_confidence = Column(String(20), nullable=True)  # 'HIGH', 'MEDIUM', 'LOW'

    # Relationships
    funding_round = relationship('FundingRound', back_populates='sources')

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Source(type='{self.source_type}', url='{self.url[:50]}...')>"


class ProcessingStatus(Base):
    """Track processing progress for each company (checkpointing)"""
    __tablename__ = 'processing_status'

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_id = Column(Integer, ForeignKey('companies.id'), nullable=False, unique=True, index=True)

    # Processing stages
    stage1_resolved = Column(Boolean, default=False, nullable=False)
    stage1_completed_at = Column(DateTime, nullable=True)

    stage2_sec_collected = Column(Boolean, default=False, nullable=False)
    stage2_completed_at = Column(DateTime, nullable=True)
    stage2_rounds_found = Column(Integer, default=0, nullable=False)

    stage3_search_extracted = Column(Boolean, default=False, nullable=False)
    stage3_completed_at = Column(DateTime, nullable=True)
    stage3_rounds_found = Column(Integer, default=0, nullable=False)

    stage4_merged = Column(Boolean, default=False, nullable=False)
    stage4_completed_at = Column(DateTime, nullable=True)
    stage4_unique_rounds = Column(Integer, default=0, nullable=False)

    # Error tracking
    has_errors = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)

    # Relationships
    company = relationship('Company', back_populates='processing_status')

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<ProcessingStatus(company='{self.company.name if self.company else 'Unknown'}', stage1={self.stage1_resolved}, stage2={self.stage2_sec_collected}, stage3={self.stage3_search_extracted}, stage4={self.stage4_merged})>"


class LLMUsage(Base):
    """Track LLM API usage and costs"""
    __tablename__ = 'llm_usage'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Provider details
    provider_name = Column(String(50), nullable=False, index=True)
    model_name = Column(String(100), nullable=False)

    # Usage metrics
    total_calls = Column(Integer, default=0, nullable=False)
    successful_calls = Column(Integer, default=0, nullable=False)
    failed_calls = Column(Integer, default=0, nullable=False)
    rate_limited_calls = Column(Integer, default=0, nullable=False)

    # Token usage (if available)
    total_input_tokens = Column(Integer, default=0, nullable=False)
    total_output_tokens = Column(Integer, default=0, nullable=False)

    # Performance metrics
    average_latency_ms = Column(Float, nullable=True)
    min_latency_ms = Column(Float, nullable=True)
    max_latency_ms = Column(Float, nullable=True)

    # Date tracking
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD format

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<LLMUsage(provider='{self.provider_name}', calls={self.total_calls}, date='{self.date}')>"


# Database connection helper
def create_db_engine(db_config: dict):
    """Create SQLAlchemy engine from configuration with automatic fallback"""
    import os
    import re
    import logging

    logger = logging.getLogger(__name__)

    def resolve_env_vars(value):
        """Resolve ${VAR_NAME} patterns in strings"""
        if not isinstance(value, str):
            return value

        # Pattern to match ${VAR_NAME}
        pattern = r'\$\{([^}]+)\}'

        def replacer(match):
            var_name = match.group(1)
            return os.getenv(var_name, match.group(0))  # Keep original if not found

        return re.sub(pattern, replacer, value)

    db_type = db_config.get('type', 'sqlite')
    auto_fallback = db_config.get('auto_fallback', False)

    # Try PostgreSQL first if configured
    if db_type == 'postgresql':
        pg_config = db_config.get('postgresql', {})

        # Check if raw connection string is provided
        connection_string = pg_config.get('connection_string')

        if connection_string:
            # Resolve environment variables in connection string
            connection_string = resolve_env_vars(connection_string)
        else:
            # Build from individual fields
            host = resolve_env_vars(pg_config.get('host', 'localhost'))
            port = pg_config.get('port', 5432)
            database = resolve_env_vars(pg_config.get('database', 'funding_rounds'))
            user = resolve_env_vars(pg_config.get('user', 'postgres'))
            password = resolve_env_vars(pg_config.get('password', ''))
            connection_string = f'postgresql://{user}:{password}@{host}:{port}/{database}'

        # Try to create PostgreSQL engine
        try:
            engine = create_engine(connection_string, echo=False)
            # Test the connection
            with engine.connect() as conn:
                pass
            logger.info("✓ Connected to PostgreSQL/CockroachDB")
            return engine
        except Exception as e:
            error_msg = str(e).lower()
            if auto_fallback:
                # Check if it's a quota/limit error
                if 'request unit limit' in error_msg or 'quota' in error_msg:
                    logger.warning("⚠️ CockroachDB quota exceeded, falling back to SQLite")
                else:
                    logger.warning(f"⚠️ PostgreSQL connection failed ({str(e)[:100]}), falling back to SQLite")

                # Fall back to SQLite
                db_type = 'sqlite'
            else:
                raise

    # Use SQLite (either by choice or fallback)
    if db_type == 'sqlite':
        db_path = db_config.get('sqlite', {}).get('path', 'data/funding_rounds.db')
        db_path = resolve_env_vars(db_path)
        # Create parent directory if needed
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        connection_string = f'sqlite:///{db_path}'
        engine = create_engine(connection_string, echo=False)
        logger.info(f"✓ Using SQLite database: {db_path}")
        return engine

    raise ValueError(f"Unsupported database type: {db_type}")


def init_database(engine):
    """Initialize database schema"""
    Base.metadata.create_all(engine)


def get_session(engine):
    """Create a new database session"""
    Session = sessionmaker(bind=engine)
    return Session()
