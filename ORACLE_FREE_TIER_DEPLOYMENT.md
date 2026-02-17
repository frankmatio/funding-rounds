# Oracle Cloud Always Free Tier Deployment Guide

## ⚠️ IMPORTANT: Free Tier Optimized Configuration

This guide is specifically for **Oracle Cloud Always Free Tier** with another program running.

---

## Oracle Always Free Tier Limits

### Compute Resources (SHARED with your other program)
- **Option A**: 2x VM.Standard.E2.1.Micro (1/8 OCPU, 1 GB RAM each)
- **Option B**: 1x Ampere A1 (up to 4 OCPUs, 24 GB RAM) - **RECOMMENDED**

### Storage
- 200 GB total block storage (across all instances)

### Network
- **10 GB outbound data transfer per month** - CRITICAL LIMIT!
- Unlimited inbound
- Unlimited within OCI

### Database
- Neon PostgreSQL (external, not counted against OCI limits)

---

## Recommended Setup for Free Tier

### Instance Configuration

Since you have another program running, **recommended allocation**:

**If using Ampere A1 (24 GB total):**
```
Total available:     4 OCPUs, 24 GB RAM
Your other program:  ~1-2 OCPUs, ~8 GB RAM (estimate)
This pipeline:       1-2 OCPUs, 8-12 GB RAM
Reserve:             ~4 GB for system
```

**Pipeline configuration** (already set in config.yaml):
```yaml
parallel:
  max_workers: 1  # Single worker to avoid resource conflicts
  batch_size: 50
```

---

## Critical: Network Bandwidth Management

**Your biggest constraint**: 10 GB/month outbound data

### Estimated Network Usage

**Per company processed:**
- SEC EDGAR queries: ~100 KB
- Search queries (6 per company): ~300 KB
- LLM API calls: ~50 KB
- Total: ~450 KB per company

**Monthly limits:**
- 10 GB = 10,240 MB
- 10,240 MB / 0.45 MB = **~22,755 companies/month max**
- Safe limit: **~20,000 companies/month** (allows buffer)

**Daily safe limit**: ~650 companies/day

### Network Optimization (Already Applied)

```yaml
search:
  max_results_per_query: 3  # Reduced from 4
  queries_per_company: 6     # Reduced from 8
  politeness_delay_seconds: 2 # Increased to reduce burst
```

---

## Deployment Steps (Free Tier)

### 1. Use Existing Ampere A1 Instance

Since you already have an instance running another program:

```bash
# SSH to your existing instance
ssh -i ~/.ssh/oracle_cloud_key ubuntu@<YOUR_IP>

# Check available resources
free -h          # Check RAM
nproc            # Check CPUs
df -h            # Check disk space
```

### 2. Create Application Directory

```bash
# Create directory
sudo mkdir -p /opt/funding-rounds
sudo chown $USER:$USER /opt/funding-rounds
```

### 3. Upload Code

**From your local machine:**

```bash
# Upload v2_parallel_db and .env
cd /Volumes/DiskExt/Users/hugh/Docs/projects/growth_stage_vc
scp -i ~/.ssh/oracle_cloud_key -r v2_parallel_db .env ubuntu@<YOUR_IP>:/opt/funding-rounds/
```

### 4. Install Dependencies

```bash
# On Oracle Cloud instance
cd /opt/funding-rounds/v2_parallel_db

# Update system (if needed)
sudo apt update

# Install Python dependencies (if not already installed)
sudo apt install -y python3 python3-pip python3-venv libpq-dev

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Verify Configuration

```bash
# Check config is set for free tier
cat config/config.yaml | grep max_workers
# Should show: max_workers: 1

# Test connection
python3 scripts/test_db_connection.py
# Should show: ✅ ALL SYSTEMS READY
```

### 6. Test Run (Small Batch)

```bash
# ALWAYS test with small batch first
python3 run_pipeline_v2.py --limit 5 --workers 1

# Monitor resource usage
# In another terminal:
htop
```

---

## Running the Pipeline (Free Tier)

### Recommended: Run in Batches

To avoid exceeding network limits and share resources with your other program:

```bash
# Process 500 companies at a time
python3 run_pipeline_v2.py --limit 500 --workers 1

# Wait and monitor before next batch
# Check network usage (see monitoring section)
```

### Option 1: Screen Session (Recommended)

```bash
# Install screen if not available
sudo apt install -y screen

# Start screen session
screen -S funding-rounds

# Activate venv and run
cd /opt/funding-rounds/v2_parallel_db
source venv/bin/activate
python3 run_pipeline_v2.py --limit 500 --workers 1

# Detach: Ctrl+A, then D
# Reattach later: screen -r funding-rounds
```

### Option 2: Nohup

```bash
cd /opt/funding-rounds/v2_parallel_db
source venv/bin/activate
nohup python3 run_pipeline_v2.py --limit 500 --workers 1 > pipeline.log 2>&1 &

# Check progress
tail -f pipeline.log
```

### Option 3: Scheduled Batches (cron)

Process small batches daily to stay within network limits:

```bash
# Edit crontab
crontab -e

# Add this line to run daily at 2 AM, processing 600 companies
0 2 * * * cd /opt/funding-rounds/v2_parallel_db && source venv/bin/activate && python3 run_pipeline_v2.py --limit 600 --workers 1 >> /opt/funding-rounds/v2_parallel_db/data/logs/cron.log 2>&1
```

This processes ~18,000 companies/month, safely under the 20,000 limit.

---

## Resource Monitoring (Critical!)

### 1. Monitor Network Usage

**Check OCI Console:**
- Go to: Instances → Your Instance → Metrics
- Monitor: "Network Bytes Out"
- **Alert threshold**: If approaching 8 GB in a month, STOP pipeline

**Check from command line:**

```bash
# Check network stats (requires vnstat)
sudo apt install -y vnstat
sudo vnstat -m  # Monthly stats

# Or use OCI CLI
oci monitoring metric-data summarize-metrics-data \
  --compartment-id <YOUR_COMPARTMENT_ID> \
  --namespace oci_vcn \
  --query-text "NetworkBytesOut"
```

### 2. Monitor Memory Usage

```bash
# Real-time monitoring
htop

# Or simple check
free -h

# Memory breakdown
ps aux --sort=-%mem | head -10
```

**Expected usage:**
- Your other program: ~8 GB (varies)
- This pipeline: ~2-4 GB (1 worker)
- System: ~2 GB
- Total: ~12-14 GB of 24 GB

### 3. Monitor CPU Usage

```bash
# Real-time
htop

# Average load (should stay under 4.0)
uptime
```

### 4. Monitor Disk Space

```bash
# Check free space
df -h

# Pipeline disk usage
du -sh /opt/funding-rounds/v2_parallel_db/data/

# Logs can grow large, rotate if needed
ls -lh /opt/funding-rounds/v2_parallel_db/data/logs/
```

---

## Network Bandwidth Optimization

### Further Reduce Network Usage (if needed)

If approaching 10 GB limit, edit `config/config.yaml`:

```yaml
search:
  max_results_per_query: 2  # Reduce from 3
  queries_per_company: 4     # Reduce from 6
  politeness_delay_seconds: 3 # Increase delay
```

This reduces usage to ~250 KB per company = ~40,000 companies/month capacity.

### Disable Search Stage Entirely (SEC only)

If network is critical, use only SEC EDGAR (no bandwidth cost):

Edit `run_pipeline_v2.py` and comment out Stage 3:

```python
# Stage 3: Search extraction (parallel)
# stage3_start = datetime.now()
# run_stage3_parallel(db_manager, search_extractor, args.workers)
# stage3_elapsed = datetime.now() - stage3_start
# logger.info(f"Stage 3 complete in {stage3_elapsed}")
```

This uses <10 KB per company = ~1M companies/month capacity.

---

## Sharing Resources with Your Other Program

### 1. Check What's Running

```bash
# See all processes
ps aux --sort=-%mem

# Top CPU users
top -o %CPU

# Top memory users
top -o %MEM
```

### 2. Set Resource Limits

**Limit pipeline memory:**

```bash
# Run with memory limit (e.g., 8 GB max)
ulimit -v 8388608  # 8 GB in KB
python3 run_pipeline_v2.py --limit 500 --workers 1
```

**Use systemd resource limits** (if using service):

Edit `funding-rounds.service`:

```ini
[Service]
# Limit to 8 GB RAM
MemoryLimit=8G
MemoryMax=8G

# Limit CPU to 50% of 1 core
CPUQuota=50%
```

### 3. Nice Priority

Run pipeline with lower priority so your other program gets preference:

```bash
# Lower priority (higher nice value = lower priority)
nice -n 10 python3 run_pipeline_v2.py --limit 500 --workers 1
```

---

## Cost Monitoring

### Free Tier (No Cost)

✅ **Included in Free Tier:**
- Ampere A1 instance (4 OCPUs, 24 GB)
- 200 GB storage
- 10 GB outbound network per month

✅ **External Services (Free):**
- Neon PostgreSQL: Free tier (10 GB)
- 9 LLM APIs: All free tier
- SEC EDGAR: Free

⚠️ **Will Incur Costs if Exceeded:**
- **Network**: $0.0085/GB over 10 GB/month
- **Storage**: $0.0255/GB over 200 GB
- **Compute**: If you upgrade instance beyond free tier

### Staying Within Free Tier

**Network:**
- Process max 600 companies/day = 18,000/month
- Monitor OCI console metrics weekly
- Stop pipeline if approaching 8-9 GB

**Storage:**
- Exports typically <1 GB per 10,000 companies
- Logs can grow: rotate weekly
- Database is external (Neon), doesn't count

**Compute:**
- Don't change instance shape
- Keep max_workers: 1
- Don't add additional instances

---

## Troubleshooting Free Tier Issues

### "Out of Memory" Errors

```bash
# Check swap
free -h

# Add swap if needed (use disk space)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### "Network Quota Exceeded"

If you exceed 10 GB and get charged:

1. **Stop the pipeline immediately**
2. **Wait until next month** for quota reset
3. **Reduce batch sizes** to stay within limit
4. **Consider SEC-only mode** (disable Stage 3)

### "Instance Slow/Unresponsive"

Your other program and pipeline are competing:

1. **Check resource usage**: `htop`
2. **Reduce workers to 1** (already done)
3. **Use nice priority**: `nice -n 10 python3...`
4. **Run during off-hours** when other program is idle
5. **Process smaller batches**: `--limit 100`

---

## Performance Expectations (Free Tier)

### With 1 Worker

- **Speed**: ~2-5 companies/minute (slower than 4 workers)
- **Daily capacity**: ~2,000-5,000 companies
- **Monthly capacity**: ~20,000 companies (network limited)

### Full Run Times

- **100 companies**: ~20-50 minutes
- **500 companies**: ~2-4 hours
- **1,000 companies**: ~4-8 hours

### Network-Constrained Monthly Limits

- **With search** (6 queries): ~20,000 companies/month
- **With search** (4 queries): ~30,000 companies/month
- **SEC only** (no search): ~1M+ companies/month

---

## Recommended Workflow for Free Tier

### Daily Batch Processing

```bash
# Every day, process 600 companies (automated via cron)
0 2 * * * cd /opt/funding-rounds/v2_parallel_db && \
  source venv/bin/activate && \
  python3 run_pipeline_v2.py --limit 600 --workers 1 >> cron.log 2>&1
```

**Benefits:**
- Stays within 10 GB network limit (~18,000/month)
- Shares resources with other program (runs at 2 AM)
- Automatic and hands-off
- ~18,000 companies/month processed

### Weekly Check

```bash
# Check network usage in OCI console
# Check disk space: df -h
# Check logs for errors: tail -100 data/logs/v2_pipeline.log
# Download exports: scp ... (counts toward network limit!)
```

---

## Summary: Free Tier Safe Limits

| Resource | Free Tier Limit | Pipeline Usage | Safe? |
|----------|----------------|----------------|-------|
| CPU | 4 OCPUs (shared) | 1-2 OCPUs | ✅ |
| RAM | 24 GB (shared) | 2-4 GB | ✅ |
| Storage | 200 GB | ~5 GB | ✅ |
| Network OUT | 10 GB/month | **CRITICAL** | ⚠️ Monitor! |

**KEY TAKEAWAY**: Network bandwidth is your constraint. Process ~600 companies/day max.

---

## Next Steps

1. ✅ Upload code to existing Oracle Cloud instance
2. ✅ Run `python3 scripts/test_db_connection.py`
3. ✅ Test with 5 companies: `python3 run_pipeline_v2.py --limit 5 --workers 1`
4. ✅ Monitor resource usage: `htop` and OCI console
5. ✅ Setup daily cron job for 600 companies/day
6. ✅ Monitor network usage weekly in OCI console

**Configuration is already optimized for free tier!**
