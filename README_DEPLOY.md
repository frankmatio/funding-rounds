# V2 Pipeline - Oracle Cloud Deployment

## ✅ Code Already Uploaded!

Since you've uploaded the code, you're ready to go!

---

## One-Time Setup (Run Once)

SSH to your Oracle Cloud instance and run:

```bash
cd /opt/funding-rounds/v2_parallel_db
bash setup_and_run.sh
```

This automated script will:
1. ✅ Check prerequisites (Python, .env, config)
2. ✅ Create virtual environment
3. ✅ Install all dependencies
4. ✅ Test database connection
5. ✅ Test LLM providers (9 APIs)
6. ✅ Test SEC agents (10 accounts)
7. ✅ Give you launch options

**Interactive menu:**
```
1) Test run with 5 companies (~5 minutes)
2) Small batch: 1,000 companies (~2 hours)
3) Medium batch: 10,000 companies (~20 hours)
4) Large batch: 15,000 companies (~30 hours)
5) Maximum batch: 20,000 companies (~50 hours) - RECOMMENDED MONTHLY
6) Custom number of companies
7) Exit (run manually later)
```

---

## Monthly Runs (After Setup)

Each month, just run:

```bash
cd /opt/funding-rounds/v2_parallel_db
bash monthly_run.sh
```

Quick menu to select how many companies to process.

---

## Manual Run (Alternative)

If you prefer manual control:

```bash
cd /opt/funding-rounds/v2_parallel_db
source venv/bin/activate

# Test (5 companies)
python3 run_pipeline_v2.py --limit 5 --workers 2

# Monthly maximum (20,000 companies)
screen -S funding-rounds
python3 run_pipeline_v2.py --limit 20000 --workers 2
# Ctrl+A, D to detach
```

---

## Checking Progress

```bash
# Reattach to screen
screen -r funding-rounds

# View logs
tail -f data/logs/v2_pipeline.log

# Check database stats
cd /opt/funding-rounds/v2_parallel_db
source venv/bin/activate
python3 scripts/test_db_connection.py
```

---

## Download Results

From your Mac:

```bash
scp -i ~/.ssh/oracle_cloud_key \
  ubuntu@<YOUR_IP>:/opt/funding-rounds/v2_parallel_db/data/exports/*.xlsx \
  ~/Downloads/
```

---

## Files Overview

| File | Purpose |
|------|---------|
| `setup_and_run.sh` | ⭐ First-time setup + interactive launcher |
| `monthly_run.sh` | ⭐ Quick launcher for monthly runs |
| `run_pipeline_v2.py` | Main pipeline script |
| `config/config.yaml` | Configuration (2 workers, optimized for free tier) |
| `scripts/test_db_connection.py` | Test all connections |

---

## Quick Commands Reference

```bash
# Setup (first time only)
bash setup_and_run.sh

# Monthly run
bash monthly_run.sh

# Check progress
screen -r funding-rounds

# View logs
tail -f data/logs/v2_pipeline.log

# Check stats
python3 scripts/test_db_connection.py
```

---

## Expected Performance

| Companies | Network | Duration | Cost |
|-----------|---------|----------|------|
| 5         | ~2 MB   | 5 min    | FREE |
| 1,000     | ~450 MB | 2 hrs    | FREE |
| 10,000    | ~4.5 GB | 20 hrs   | FREE |
| 15,000    | ~6.8 GB | 30 hrs   | FREE |
| 20,000    | ~9.0 GB | 50 hrs   | FREE ✅ |

**Annual capacity**: 240,000 companies (20K × 12 months) = **$0/year**

---

## That's It!

Just run `bash setup_and_run.sh` and follow the prompts!
