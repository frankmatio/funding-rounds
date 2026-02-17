# V2 Pipeline - Oracle Cloud Deployment Status

## ✅ READY FOR ORACLE CLOUD DEPLOYMENT

**Last Tested:** 2026-02-16
**Status:** All systems operational and ready for production

---

## Pre-Deployment Test Results

```
================================================================================
DATABASE CONNECTION TEST
================================================================================
✓ Connected to Neon PostgreSQL
✓ Database version: PostgreSQL 17.7
✓ Connection string validated

================================================================================
LLM PROVIDERS TEST
================================================================================
✓ All 9 providers configured and ready:
  1. Gemini (15 RPM)
  2. Groq (30 RPM)
  3. DeepSeek (60 RPM)
  4. OpenRouter (20 RPM)
  5. Cerebras (30 RPM)
  6. Mistral (30 RPM)
  7. Fireworks (30 RPM)
  8. Qwen (60 RPM)
  9. OpenRouter #2 (20 RPM)

Total capacity: ~315 RPM

================================================================================
SEC USER AGENTS TEST
================================================================================
✓ All 10 SEC user agents configured and ready

================================================================================
OVERALL STATUS
================================================================================
Database:      ✓ READY
LLM Providers: ✓ READY
SEC Agents:    ✓ READY

✅ ALL SYSTEMS READY FOR DEPLOYMENT
```

---

## What's Included

### Core Components
- ✅ Parallel processing pipeline (4-stage)
- ✅ Neon PostgreSQL integration (cloud database)
- ✅ 9 LLM providers with round-robin rotation
- ✅ 10 SEC user agents for rate limit distribution
- ✅ Thread-safe database operations
- ✅ Automatic fallback to SQLite if needed
- ✅ Multi-format export (Excel, CSV, JSON)
- ✅ Deduplication with fuzzy matching
- ✅ 16 authoritative data sources

### Deployment Files
- ✅ `requirements.txt` - All dependencies
- ✅ `setup.sh` - Automated setup script
- ✅ `scripts/init_db.py` - Database initialization
- ✅ `scripts/test_db_connection.py` - Pre-flight checks
- ✅ `funding-rounds.service` - Systemd service file
- ✅ `ORACLE_CLOUD_DEPLOYMENT.md` - Complete deployment guide
- ✅ `DEPLOYMENT_CHECKLIST.md` - Step-by-step checklist

### Configuration
- ✅ `.env` - All API keys and credentials configured
- ✅ `config/config.yaml` - Pipeline settings optimized

---

## Deployment Instructions

### Quick Start (3 Steps)

1. **Provision Oracle Cloud Instance**
   - Shape: VM.Standard.E4.Flex (4 OCPUs, 16 GB RAM)
   - OS: Ubuntu 22.04
   - Storage: 50-100 GB

2. **Upload and Setup**
   ```bash
   # From local machine
   scp -i ~/.ssh/oracle_cloud_key -r v2_parallel_db .env ubuntu@<IP>:/opt/funding-rounds/

   # On Oracle Cloud instance
   cd /opt/funding-rounds/v2_parallel_db
   bash setup.sh
   ```

3. **Run**
   ```bash
   # Test
   python3 run_pipeline_v2.py --limit 3 --workers 2

   # Production
   python3 run_pipeline_v2.py --full --workers 4
   ```

### Detailed Instructions
See `ORACLE_CLOUD_DEPLOYMENT.md` for complete step-by-step guide.

---

## Pre-Flight Checklist

Run this before deployment:

```bash
cd v2_parallel_db
python3 scripts/test_db_connection.py
```

**Expected output:**
```
✅ ALL SYSTEMS READY FOR DEPLOYMENT
```

---

## Technical Specifications

### Performance
- **Throughput**: 5-15 companies/minute (with 4 workers)
- **LLM Capacity**: 315 requests/minute across 9 providers
- **SEC Rate Limit**: Distributed across 10 accounts
- **Estimated time** (1000 companies): 1-3 hours

### Resource Requirements
- **CPUs**: 4 OCPUs (VM.Standard.E4.Flex)
- **RAM**: 16 GB (8 GB minimum)
- **Storage**: 50-100 GB
- **Network**: Outbound HTTPS (443)

### Cost Estimate
- **Oracle Cloud**: ~$90/month (4 OCPUs)
- **Neon PostgreSQL**: $0/month (free tier, 10 GB)
- **LLM APIs**: $0/month (all free tier)
- **Total**: ~$90/month

---

## Data Sources

The pipeline collects funding round data from:

### Stage 2: SEC EDGAR
- Official SEC Form D filings (US companies)

### Stage 3: Search-Based (16 sources)
- TechCrunch
- Crunchbase
- PitchBook
- Reuters
- Bloomberg
- CB Insights
- The Information
- Axios
- VentureBeat
- GeekWire
- WSJ
- Financial Times
- Forbes
- EU-Startups (European focus)
- Sifted (FT-backed European)
- FinSMEs (Global)

---

## Architecture Highlights

### Database
- **Primary**: Neon PostgreSQL (cloud-hosted, accessible from other apps)
- **Fallback**: SQLite (automatic failover)
- **Schema**: Companies, FundingRounds, Investors, ProcessingStatus
- **Features**: Thread-safe sessions, automatic migrations

### Parallel Processing
- **ThreadPoolExecutor** for concurrent company processing
- **Session-per-thread** pattern for database safety
- **Checkpoint system** for resume capability
- **Progress tracking** per company

### LLM Rotation
- **Strategy**: Round-robin across 9 providers
- **Rate limiting**: Per-provider RPM tracking
- **Failover**: Automatic retry with different provider
- **Efficiency**: 315 combined RPM capacity

### SEC Collection
- **Multi-account**: 10 user agents
- **Rotation**: Distributes load to avoid rate limits
- **Caching**: Reduces redundant API calls

---

## Support & Troubleshooting

### Test Connection
```bash
python3 scripts/test_db_connection.py
```

### View Logs
```bash
tail -f data/logs/v2_pipeline.log
```

### Check Database Stats
```bash
python3 -c "
from src.database import DatabaseManager
import yaml
with open('config/config.yaml') as f:
    config = yaml.safe_load(f)
db = DatabaseManager(config)
print(db.get_statistics())
"
```

### Common Issues

**Database connection failed:**
- Verify DATABASE_URL in .env
- Check network connectivity
- Test with: `scripts/test_db_connection.py`

**LLM rate limits:**
- Increase `politeness_delay_seconds` in config.yaml
- Add more API keys
- Reduce `parallel.max_workers`

**Out of memory:**
- Reduce workers in config.yaml
- Increase instance RAM

---

## Security Checklist

- ✅ .env file excluded from git
- ✅ API keys stored in environment variables only
- ✅ Database uses SSL/TLS (Neon PostgreSQL)
- ✅ No hardcoded credentials in code
- ⚠️  Ensure .env has restricted permissions (chmod 600)
- ⚠️  Use Oracle Cloud IAM for SSH access control
- ⚠️  Enable Oracle Cloud firewall rules

---

## Next Steps

1. **Read deployment guide**: `ORACLE_CLOUD_DEPLOYMENT.md`
2. **Follow checklist**: `DEPLOYMENT_CHECKLIST.md`
3. **Provision Oracle Cloud instance**
4. **Upload code and .env file**
5. **Run setup.sh**
6. **Test with 3 companies**
7. **Start production run**

---

## Version Info

- **Pipeline Version**: V2
- **Python**: 3.9+ required (3.10+ recommended)
- **Database**: PostgreSQL 12+ or SQLite 3.35+
- **Dependencies**: See requirements.txt

---

**Status**: ✅ Production Ready
**Tested**: Local environment + Neon PostgreSQL
**Ready for**: Oracle Cloud deployment
