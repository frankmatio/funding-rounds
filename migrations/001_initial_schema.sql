-- Funding Round Collection Engine V2 - Initial Database Schema
-- PostgreSQL version (SQLite will use SQLAlchemy ORM instead)

-- Companies table
CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL UNIQUE,
    cik VARCHAR(20),
    official_name VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_companies_name ON companies(name);
CREATE INDEX idx_companies_cik ON companies(cik);

-- Investors table
CREATE TABLE IF NOT EXISTS investors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(500) NOT NULL UNIQUE,
    investor_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_investors_name ON investors(name);

-- Funding rounds table
CREATE TABLE IF NOT EXISTS funding_rounds (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    round_name VARCHAR(100),
    date VARCHAR(50),
    amount_raised_usd FLOAT,
    pre_money_valuation_usd FLOAT,
    post_money_valuation_usd FLOAT,
    lead_investor VARCHAR(500),
    source_type VARCHAR(50) NOT NULL,
    confidence_score VARCHAR(20) NOT NULL,
    source_urls JSONB,
    notes TEXT,
    raw_data JSONB,
    is_duplicate BOOLEAN DEFAULT FALSE NOT NULL,
    duplicate_of_id INTEGER REFERENCES funding_rounds(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_funding_rounds_company ON funding_rounds(company_id);
CREATE INDEX idx_funding_rounds_is_duplicate ON funding_rounds(is_duplicate);

-- Round-Investor many-to-many relationship
CREATE TABLE IF NOT EXISTS round_investors (
    round_id INTEGER NOT NULL REFERENCES funding_rounds(id) ON DELETE CASCADE,
    investor_id INTEGER NOT NULL REFERENCES investors(id) ON DELETE CASCADE,
    PRIMARY KEY (round_id, investor_id)
);

-- Sources table
CREATE TABLE IF NOT EXISTS sources (
    id SERIAL PRIMARY KEY,
    round_id INTEGER NOT NULL REFERENCES funding_rounds(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,
    url VARCHAR(2000),
    title VARCHAR(500),
    snippet TEXT,
    llm_provider VARCHAR(50),
    llm_model VARCHAR(100),
    extraction_confidence VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_sources_round ON sources(round_id);

-- Processing status table
CREATE TABLE IF NOT EXISTS processing_status (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL UNIQUE REFERENCES companies(id) ON DELETE CASCADE,
    stage1_resolved BOOLEAN DEFAULT FALSE NOT NULL,
    stage1_completed_at TIMESTAMP,
    stage2_sec_collected BOOLEAN DEFAULT FALSE NOT NULL,
    stage2_completed_at TIMESTAMP,
    stage2_rounds_found INTEGER DEFAULT 0 NOT NULL,
    stage3_search_extracted BOOLEAN DEFAULT FALSE NOT NULL,
    stage3_completed_at TIMESTAMP,
    stage3_rounds_found INTEGER DEFAULT 0 NOT NULL,
    stage4_merged BOOLEAN DEFAULT FALSE NOT NULL,
    stage4_completed_at TIMESTAMP,
    stage4_unique_rounds INTEGER DEFAULT 0 NOT NULL,
    has_errors BOOLEAN DEFAULT FALSE NOT NULL,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0 NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_processing_status_company ON processing_status(company_id);

-- LLM usage tracking table
CREATE TABLE IF NOT EXISTS llm_usage (
    id SERIAL PRIMARY KEY,
    provider_name VARCHAR(50) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    total_calls INTEGER DEFAULT 0 NOT NULL,
    successful_calls INTEGER DEFAULT 0 NOT NULL,
    failed_calls INTEGER DEFAULT 0 NOT NULL,
    rate_limited_calls INTEGER DEFAULT 0 NOT NULL,
    total_input_tokens INTEGER DEFAULT 0 NOT NULL,
    total_output_tokens INTEGER DEFAULT 0 NOT NULL,
    average_latency_ms FLOAT,
    min_latency_ms FLOAT,
    max_latency_ms FLOAT,
    date VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_llm_usage_provider ON llm_usage(provider_name);
CREATE INDEX idx_llm_usage_date ON llm_usage(date);

-- Update trigger for updated_at columns (PostgreSQL)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_investors_updated_at BEFORE UPDATE ON investors
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_funding_rounds_updated_at BEFORE UPDATE ON funding_rounds
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processing_status_updated_at BEFORE UPDATE ON processing_status
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_llm_usage_updated_at BEFORE UPDATE ON llm_usage
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
