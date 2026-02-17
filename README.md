# V2 Funding Round Data Collection Pipeline

Parallel processing pipeline for collecting funding round data from SEC EDGAR and web search.

## Features

- ✅ **Parallel Processing**: 2 workers optimized for Oracle Cloud Free Tier
- ✅ **Database**: Neon PostgreSQL (cloud) with SQLite fallback
- ✅ **9 LLM Providers**: 315 RPM combined capacity (all free tier)
- ✅ **10 SEC Accounts**: Distributed rate limiting
- ✅ **16 Data Sources**: SEC EDGAR + 15 authoritative web sources
- ✅ **Monthly Capacity**: 20,000 companies (~9 GB network)
- ✅ **Cost**: $0/month (Oracle Free Tier + free APIs)

## Quick Deployment on Oracle Cloud

```bash
bash <(curl -sSL YOUR_RAW_GITHUB_URL/deploy_from_git.sh)
```

## Requirements

- Oracle Cloud Always Free Tier
- Neon PostgreSQL (free tier)
- 9 LLM API keys (all free)
- 10 SEC user agents

## Performance

| Companies | Network | Duration | Cost |
|-----------|---------|----------|------|
| 20,000    | ~9.0 GB | 50 hrs   | FREE |

**Annual capacity**: 240,000 companies (free)

## Documentation

- `MONTHLY_RUN_GUIDE.md` - Full guide
- `deploy_from_git.sh` - Automated deployment
