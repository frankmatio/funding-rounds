# Quick Start: Oracle Cloud Always Free Tier

## ✅ Already Optimized for Free Tier!

Your configuration is already set for Oracle Cloud Always Free Tier with shared resources.

---

## Critical Limits

⚠️ **Network**: 10 GB/month outbound (your main constraint)
- **Safe limit**: ~600 companies/day = 18,000/month
- **Monitor**: OCI Console → Instances → Metrics → Network Bytes Out

✅ **CPU**: 1 worker configured (won't conflict with your other program)
✅ **RAM**: ~2-4 GB usage (plenty of room in 24 GB shared)
✅ **Storage**: ~5 GB total (well under 200 GB limit)

---

## 5-Minute Deployment

### 1. Upload to Your Existing Instance

**From your Mac:**
```bash
cd /Volumes/DiskExt/Users/hugh/Docs/projects/growth_stage_vc

# Upload code
scp -i ~/.ssh/oracle_cloud_key -r v2_parallel_db .env ubuntu@<YOUR_IP>:/opt/funding-rounds/
```

### 2. Setup on Oracle Cloud

**SSH to your instance:**
```bash
ssh -i ~/.ssh/oracle_cloud_key ubuntu@<YOUR_IP>
```

**Install and test:**
```bash
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

### 3. Test Run

```bash
# Test with 5 companies first
python3 run_pipeline_v2.py --limit 5 --workers 1

# Monitor resource usage in another terminal
htop
```

### 4. Production Run (Daily Batches)

**Option A: Manual batches**
```bash
# Run in screen session
screen -S funding-rounds
cd /opt/funding-rounds/v2_parallel_db
source venv/bin/activate

# Process 600 companies (safe daily limit)
python3 run_pipeline_v2.py --limit 600 --workers 1

# Detach: Ctrl+A then D
# Reattach later: screen -r funding-rounds
```

**Option B: Automated daily (recommended)**
```bash
# Setup cron job to run daily at 2 AM
crontab -e

# Add this line:
0 2 * * * cd /opt/funding-rounds/v2_parallel_db && source venv/bin/activate && python3 run_pipeline_v2.py --limit 600 --workers 1 >> /opt/funding-rounds/v2_parallel_db/cron.log 2>&1
```

---

## Configuration (Already Set!)

✅ **Workers**: 1 (won't overwhelm shared instance)
✅ **Search queries**: 6 per company (reduced to save bandwidth)
✅ **Batch size**: 50 (smaller commits)
✅ **Delays**: 2 seconds between searches (polite rate limiting)

You don't need to change anything in `config/config.yaml` - it's already optimized!

---

## Monitoring

### Check Network Usage (CRITICAL!)

**OCI Console:**
1. Go to: Compute → Instances → Your Instance
2. Click "Metrics"
3. Look at "Network Bytes Out"
4. **Alert if approaching 8-9 GB in a month**

**Command line:**
```bash
# Install monitoring tool
sudo apt install -y vnstat

# Check monthly usage
sudo vnstat -m
```

### Check Pipeline Progress

```bash
# View logs
tail -f /opt/funding-rounds/v2_parallel_db/data/logs/v2_pipeline.log

# Check database stats
cd /opt/funding-rounds/v2_parallel_db
source venv/bin/activate
python3 -c "
from src.database import DatabaseManager
import yaml
with open('config/config.yaml') as f:
    config = yaml.safe_load(f)
db = DatabaseManager(config)
stats = db.get_statistics()
print(f'Companies: {stats[\"companies\"]}')
print(f'Funding rounds: {stats[\"funding_rounds\"]}')
print(f'Investors: {stats[\"investors\"]}')
"
```

### Check Resource Usage

```bash
# RAM and CPU
htop

# Disk space
df -h

# Pipeline disk usage
du -sh /opt/funding-rounds/v2_parallel_db/data/
```

---

## What to Expect

### Performance (1 Worker)
- **Speed**: ~3-5 companies/minute
- **600 companies**: ~2-3 hours
- **Daily**: Process 600 companies = safe for network limit
- **Monthly**: ~18,000 companies total

### Network Usage
- **Per company**: ~450 KB (with search)
- **600 companies**: ~270 MB/day
- **18,000 companies**: ~8.1 GB/month ✅ (under 10 GB limit)

### Storage
- **Logs**: ~100 MB per 1,000 companies
- **Exports**: ~50 MB per 1,000 companies
- **Database**: External (Neon), doesn't count
- **Total**: ~5 GB for full pipeline

---

## Staying Within Free Tier Limits

### ✅ DO:
- Process 600 companies/day max
- Monitor network usage weekly
- Use 1 worker (already configured)
- Run during off-hours if other program is active
- Rotate/compress logs weekly

### ❌ DON'T:
- Don't increase max_workers above 1
- Don't process >1,000 companies/day (network)
- Don't download large exports frequently (network)
- Don't change instance shape (will incur costs)
- Don't add more instances (will incur costs)

---

## Troubleshooting

### "Running out of memory"

Your other program might be using a lot. Check:
```bash
ps aux --sort=-%mem | head -10
```

Add swap space:
```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### "Pipeline is slow"

Expected! With 1 worker, it's slower but safe:
- 4 workers: ~15 companies/min
- 1 worker: ~3-5 companies/min

This is intentional to share resources with your other program.

### "Approaching network limit"

If you see 8+ GB in OCI metrics:
1. **STOP the pipeline immediately**
2. Wait until next month
3. Reduce to 400 companies/day instead of 600

Or disable search entirely (SEC only):
```bash
# Edit config.yaml
search:
  queries_per_company: 0  # Disable search
```

This uses <10 KB per company = ~1M companies/month possible.

---

## Recommended Schedule

### Daily (Automated via cron)
- 2:00 AM: Process 600 companies
- Duration: ~2-3 hours
- Finishes: ~5:00 AM
- Network: ~270 MB

### Weekly (Manual)
- Check OCI network metrics
- Review logs for errors
- Check disk space: `df -h`
- Verify database: `python3 scripts/test_db_connection.py`

### Monthly
- Export results (counts toward network!)
- Verify under 10 GB network usage
- Rotate old logs

---

## Summary

✅ **Configuration already optimized for free tier**
✅ **No changes needed to config.yaml**
✅ **Safe to run alongside your other program**
✅ **Will stay within all free tier limits**

**Just upload, test, and run!**

**Maximum safe processing**: 600 companies/day = 18,000/month

For detailed information, see `ORACLE_FREE_TIER_DEPLOYMENT.md`
