# Monthly Run Guide - Oracle Cloud Always Free Tier

## 🎯 Optimized for ONCE-A-MONTH Processing

Since you're running once a month, you can use the **entire 10 GB network quota** in one run!

---

## Maximum Monthly Capacity

### Network Calculation

**Oracle Free Tier**: 10 GB/month outbound

**Per company**: ~450 KB (with search)

**Maximum possible**: 10 GB ÷ 450 KB = ~22,755 companies

**Safe monthly limit**: **~20,000 companies** (leaves buffer for other usage)

### Single Monthly Run

```bash
# Process up to 20,000 companies in one monthly run
python3 run_pipeline_v2.py --limit 20000 --workers 2
```

**Expected duration**: ~40-80 hours (1.5-3 days)

---

## Configuration (Already Set!)

✅ **Workers**: 2 (faster than 1, safe for periodic run)
✅ **Search**: 6 queries per company
✅ **Batch size**: 100 companies per commit
✅ **Checkpoints**: Every 50 companies (resume capability)

---

## Deployment: Monthly Run

### 1. Upload Code (one-time)

```bash
cd /Volumes/DiskExt/Users/hugh/Docs/projects/growth_stage_vc
scp -i ~/.ssh/oracle_cloud_key -r v2_parallel_db .env ubuntu@<YOUR_IP>:/opt/funding-rounds/
```

### 2. Setup (one-time)

```bash
ssh -i ~/.ssh/oracle_cloud_key ubuntu@<YOUR_IP>
cd /opt/funding-rounds/v2_parallel_db

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Test connection
python3 scripts/test_db_connection.py
# Should show: ✅ ALL SYSTEMS READY
```

### 3. Monthly Run (repeat each month)

**Start screen session** (recommended for long runs):

```bash
ssh -i ~/.ssh/oracle_cloud_key ubuntu@<YOUR_IP>

# Start screen
screen -S funding-rounds

# Navigate and activate
cd /opt/funding-rounds/v2_parallel_db
source venv/bin/activate

# Process 20,000 companies (or whatever you need)
python3 run_pipeline_v2.py --limit 20000 --workers 2

# Detach screen: Ctrl+A, then D
# You can disconnect SSH - pipeline keeps running!
```

**Check progress** (anytime):

```bash
# Reattach to screen
screen -r funding-rounds

# Or check logs without screen
tail -f /opt/funding-rounds/v2_parallel_db/data/logs/v2_pipeline.log
```

**When complete**:

```bash
# Reattach to see results
screen -r funding-rounds

# Download exports to your Mac
# From your Mac:
scp -i ~/.ssh/oracle_cloud_key ubuntu@<YOUR_IP>:/opt/funding-rounds/v2_parallel_db/data/exports/*.xlsx ~/Downloads/
```

---

## Performance Expectations

### With 2 Workers

- **Speed**: ~6-10 companies/minute
- **1,000 companies**: ~2-3 hours
- **10,000 companies**: ~20-30 hours (~1 day)
- **20,000 companies**: ~40-60 hours (~2-3 days)

### Network Usage

| Companies | Network Used | Within 10 GB? |
|-----------|--------------|---------------|
| 5,000     | ~2.3 GB      | ✅ Yes        |
| 10,000    | ~4.5 GB      | ✅ Yes        |
| 15,000    | ~6.8 GB      | ✅ Yes        |
| 20,000    | ~9.0 GB      | ✅ Yes        |
| 25,000    | ~11.3 GB     | ❌ No (overage charges) |

**Recommendation**: Start with 15,000 companies for first run, then increase to 20,000 if needed.

---

## Resource Monitoring During Run

### Check Resources (from another SSH session)

```bash
# Monitor CPU/RAM
htop

# Check disk space
df -h

# Check network (if vnstat installed)
sudo vnstat -l
```

### Expected Resource Usage (2 workers)

- **CPU**: ~2-3 cores (of 4 total)
- **RAM**: ~4-8 GB (of 24 total)
- **Disk**: ~10-15 GB (logs + exports)

Your other program should have:
- **CPU**: 1-2 cores available
- **RAM**: 16-20 GB available

---

## Month-by-Month Schedule

### Beginning of Month

1. **Check network quota reset** (1st of month)
   - OCI Console → Instances → Metrics → Network
   - Verify quota is reset to 0/10 GB

2. **Start monthly run** (1st-5th of month)
   ```bash
   screen -S funding-rounds
   cd /opt/funding-rounds/v2_parallel_db
   source venv/bin/activate
   python3 run_pipeline_v2.py --limit 20000 --workers 2
   # Ctrl+A, D to detach
   ```

3. **Monitor progress** (during run)
   - Check screen: `screen -r funding-rounds`
   - Check logs: `tail -f data/logs/v2_pipeline.log`
   - Check resources: `htop`

### Mid-Month (Run Complete)

4. **Verify completion** (~3 days after start)
   - Reattach screen: `screen -r funding-rounds`
   - Check final stats in logs
   - Verify exports created

5. **Download results**
   ```bash
   # From your Mac
   scp -i ~/.ssh/oracle_cloud_key \
     ubuntu@<YOUR_IP>:/opt/funding-rounds/v2_parallel_db/data/exports/*.xlsx \
     ~/Downloads/
   ```

6. **Check network usage**
   - OCI Console → Network metrics
   - Should be ~9 GB or less
   - If over 10 GB, reduce next month's limit

### End of Month

7. **Clean up (optional)**
   - Compress old logs
   - Archive exports
   - Clear checkpoint files

---

## Resuming Interrupted Runs

If the run stops (power outage, network issue, etc.), the pipeline has checkpoint capability:

```bash
# Reattach screen
screen -r funding-rounds

# Pipeline tracks which companies are processed
# Just re-run the same command
python3 run_pipeline_v2.py --limit 20000 --workers 2

# It will skip already-processed companies automatically!
```

The database tracks processing status per company, so you won't duplicate work.

---

## Optimization Options

### Option 1: Faster (3 workers)

If your other program is idle, try 3 workers:

```yaml
# Edit config/config.yaml
parallel:
  max_workers: 3
```

Expected speed: ~9-15 companies/minute (20,000 in ~24-36 hours)

**Monitor RAM closely!** May use up to 12 GB.

### Option 2: Network Saver (SEC only)

If you only need US companies and want to maximize capacity:

```yaml
# Edit config/config.yaml
search:
  queries_per_company: 0  # Disable search, SEC only
```

This reduces to ~10 KB per company = **~1 million companies/month possible!**

But you'll only get data from SEC Form D filings (US companies only).

### Option 3: Balanced

Current default:
- 2 workers
- 6 search queries per company
- ~20,000 companies/month
- Global coverage (SEC + Search)

**This is recommended for most use cases.**

---

## Troubleshooting Long Runs

### "Screen session disconnected"

```bash
# Reconnect
screen -r funding-rounds

# If shows "no session":
screen -ls  # List sessions
screen -r <session_id>
```

### "Running out of memory"

```bash
# Check usage
free -h

# If needed, reduce workers mid-run:
# 1. Stop current run (Ctrl+C in screen)
# 2. Edit config.yaml: max_workers: 1
# 3. Restart: python3 run_pipeline_v2.py --limit 20000 --workers 1
```

### "Pipeline seems stuck"

```bash
# Check if still running
ps aux | grep python

# Check recent log activity
tail -50 data/logs/v2_pipeline.log

# Check database progress
python3 -c "
from src.database import DatabaseManager
import yaml
with open('config/config.yaml') as f:
    config = yaml.safe_load(f)
db = DatabaseManager(config)
stats = db.get_statistics()
print(f'Companies processed: {stats[\"companies\"]}')
print(f'Funding rounds found: {stats[\"funding_rounds\"]}')
"
```

### "Approaching 10 GB network limit"

If you see 9+ GB in OCI metrics mid-run:

1. **Stop the pipeline** (Ctrl+C in screen)
2. **Note how many companies processed**
3. **Wait until next month**
4. **Reduce next month's limit** accordingly

---

## Example Monthly Workflow

### Month 1: Test Run (5,000 companies)

```bash
# Conservative first run
python3 run_pipeline_v2.py --limit 5000 --workers 2
# Duration: ~10-15 hours
# Network: ~2.3 GB
# Result: Test data quality and performance
```

### Month 2: Medium Run (15,000 companies)

```bash
# Increase capacity
python3 run_pipeline_v2.py --limit 15000 --workers 2
# Duration: ~30-45 hours
# Network: ~6.8 GB
# Result: Substantial dataset
```

### Month 3+: Full Run (20,000 companies)

```bash
# Maximum safe capacity
python3 run_pipeline_v2.py --limit 20000 --workers 2
# Duration: ~40-60 hours
# Network: ~9.0 GB
# Result: Maximum free tier capacity
```

---

## Summary: Monthly Run Model

✅ **Optimized configuration**: 2 workers, checkpoints enabled
✅ **Maximum capacity**: 20,000 companies/month safely
✅ **Duration**: ~2-3 days per monthly run
✅ **Cost**: $0/month (stays within free tier)
✅ **Automatic resume**: If interrupted, just restart
✅ **No cron needed**: Manual monthly execution

**Annual capacity**: ~240,000 companies/year (20K × 12 months)

---

## Quick Monthly Checklist

**Start of month (Day 1-5):**
- [ ] SSH to Oracle Cloud instance
- [ ] Start screen session: `screen -S funding-rounds`
- [ ] Navigate: `cd /opt/funding-rounds/v2_parallel_db`
- [ ] Activate venv: `source venv/bin/activate`
- [ ] Run: `python3 run_pipeline_v2.py --limit 20000 --workers 2`
- [ ] Detach: Ctrl+A, D
- [ ] Disconnect SSH (pipeline keeps running)

**Mid-run checks (every 1-2 days):**
- [ ] SSH and check screen: `screen -r funding-rounds`
- [ ] Check OCI network metrics (should stay under 10 GB)
- [ ] Verify other program still running fine

**End of run (Day 3-5):**
- [ ] Verify completion in screen
- [ ] Download exports to Mac
- [ ] Check database stats
- [ ] Note companies processed for next month

**Next month**: Repeat!

---

This monthly model is **perfect for free tier** - you get maximum capacity without daily overhead!
