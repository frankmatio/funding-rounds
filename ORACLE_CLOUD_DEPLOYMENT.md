# Oracle Cloud Deployment Guide

## Prerequisites

### Oracle Cloud Compute Instance Requirements
- **OS**: Oracle Linux 8 or Ubuntu 20.04/22.04
- **Shape**: VM.Standard.E4.Flex (recommended)
  - **CPUs**: 2-4 OCPUs (for parallel workers)
  - **RAM**: 8-16 GB (for concurrent LLM processing)
  - **Storage**: 50-100 GB (for logs and exports)
- **Network**: Allow outbound HTTPS (443) for API calls
- **Firewall**: Open port 22 (SSH) for management

### External Services
- **Neon PostgreSQL**: Already configured (connection string in .env)
- **LLM API Keys**: 9 providers configured in .env
- **SEC User Agents**: 10 accounts configured in .env

## Deployment Steps

### 1. Provision Oracle Cloud Compute Instance

```bash
# Via OCI CLI (optional)
oci compute instance launch \
  --availability-domain <AD> \
  --compartment-id <COMPARTMENT_ID> \
  --shape VM.Standard.E4.Flex \
  --shape-config '{"ocpus":4,"memoryInGBs":16}' \
  --image-id <UBUNTU_22.04_IMAGE_ID> \
  --subnet-id <SUBNET_ID> \
  --display-name "funding-rounds-pipeline"
```

Or use the Oracle Cloud Console UI.

### 2. Connect to Instance

```bash
ssh -i ~/.ssh/oracle_cloud_key ubuntu@<INSTANCE_PUBLIC_IP>
```

### 3. Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.10+
sudo apt install -y python3 python3-pip python3-venv git

# Install PostgreSQL client libraries (for psycopg2)
sudo apt install -y libpq-dev

# Verify Python version (needs 3.9+)
python3 --version
```

### 4. Clone Repository

```bash
# Create app directory
sudo mkdir -p /opt/funding-rounds
sudo chown ubuntu:ubuntu /opt/funding-rounds

# Clone or upload code
cd /opt/funding-rounds
# Option A: Git clone (if repo is in git)
# git clone <your-repo-url> .

# Option B: Upload via SCP from local machine
# From your local machine:
# scp -i ~/.ssh/oracle_cloud_key -r v2_parallel_db ubuntu@<IP>:/opt/funding-rounds/
```

### 5. Setup Python Environment

```bash
cd /opt/funding-rounds/v2_parallel_db

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 6. Configure Environment Variables

```bash
# Create .env file (parent directory)
cd /opt/funding-rounds
nano .env
```

**Copy your .env content** (with all API keys and DATABASE_URL). DO NOT commit .env to git!

**Verify .env location**:
```
/opt/funding-rounds/.env              ← Environment variables
/opt/funding-rounds/v2_parallel_db/   ← Application code
```

### 7. Configure Application

```bash
cd /opt/funding-rounds/v2_parallel_db

# Review configuration
nano config/config.yaml

# Key settings to verify:
# - database.type: postgresql (Neon)
# - parallel.max_workers: 4 (match your OCPUs)
# - search.politeness_delay_seconds: 1
```

### 8. Initialize Database

```bash
# Activate venv if not already active
source venv/bin/activate

# Run database initialization
python3 scripts/init_db.py
```

This will:
- Connect to Neon PostgreSQL
- Create all tables (companies, funding_rounds, investors, etc.)
- Create indexes for performance

### 9. Test Run

```bash
# Test with 3 companies
python3 run_pipeline_v2.py --limit 3 --workers 2

# Expected output:
# ✓ Connected to PostgreSQL (Neon)
# ✓ All components initialized
# Stage 1: Loading...
# Stage 2: SEC collection...
# Stage 3: Search extraction...
# Stage 4: Deduplication...
# ✓ Pipeline complete!
```

### 10. Production Run

```bash
# Full run with all companies
python3 run_pipeline_v2.py --full --workers 4

# Or with limit
python3 run_pipeline_v2.py --limit 100 --workers 4
```

## Running as a Background Service

### Option 1: Systemd Service (Recommended)

Create service file:

```bash
sudo nano /etc/systemd/system/funding-rounds.service
```

See `funding-rounds.service` file in this directory for content.

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable funding-rounds.service
sudo systemctl start funding-rounds.service

# Check status
sudo systemctl status funding-rounds.service

# View logs
sudo journalctl -u funding-rounds.service -f
```

### Option 2: Screen Session

```bash
# Install screen
sudo apt install -y screen

# Start screen session
screen -S funding-rounds

# Run pipeline
cd /opt/funding-rounds/v2_parallel_db
source venv/bin/activate
python3 run_pipeline_v2.py --full --workers 4

# Detach: Ctrl+A, then D
# Reattach: screen -r funding-rounds
```

### Option 3: Nohup

```bash
cd /opt/funding-rounds/v2_parallel_db
source venv/bin/activate
nohup python3 run_pipeline_v2.py --full --workers 4 > pipeline.log 2>&1 &

# Check progress
tail -f pipeline.log
```

## Monitoring and Maintenance

### Check Pipeline Status

```bash
# View recent logs
tail -f /opt/funding-rounds/v2_parallel_db/data/logs/v2_pipeline.log

# Check database statistics
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
print(f'Funding Rounds: {stats[\"funding_rounds\"]}')
print(f'Investors: {stats[\"investors\"]}')
"
```

### Download Exports

```bash
# From Oracle Cloud instance to local machine
scp -i ~/.ssh/oracle_cloud_key \
  ubuntu@<IP>:/opt/funding-rounds/v2_parallel_db/data/exports/*.xlsx \
  ~/Downloads/
```

### Backup Database (Neon PostgreSQL)

Neon handles backups automatically, but you can export data:

```bash
# Export to CSV
cd /opt/funding-rounds/v2_parallel_db
source venv/bin/activate
python3 -c "
from src.exporter_v2 import ExporterV2
from src.database import DatabaseManager
import yaml

with open('config/config.yaml') as f:
    config = yaml.safe_load(f)

db = DatabaseManager(config)
exporter = ExporterV2(config, db)

with db.session_scope() as session:
    files = exporter.export_all_formats(session)
    print('Exported:', files)
"
```

## Scaling Considerations

### Vertical Scaling (More Resources)

Increase compute shape:
```bash
# Via OCI Console: Compute → Instances → Edit → Change Shape
# Select larger shape: VM.Standard.E4.Flex with 8 OCPUs, 32 GB RAM

# Update config.yaml:
parallel:
  max_workers: 8  # Match OCPUs
```

### Horizontal Scaling (Multiple Instances)

Run multiple instances processing different company batches:

**Instance 1:**
```bash
python3 run_pipeline_v2.py --csv companies_batch1.csv --full --workers 4
```

**Instance 2:**
```bash
python3 run_pipeline_v2.py --csv companies_batch2.csv --full --workers 4
```

Both write to the same Neon PostgreSQL database (thread-safe).

## Troubleshooting

### Connection Issues

```bash
# Test Neon PostgreSQL connection
cd /opt/funding-rounds/v2_parallel_db
source venv/bin/activate
python3 scripts/test_db_connection.py

# Test LLM providers
python3 -c "
from src.llm_router_v2 import LLMRouterV2
from src.database import DatabaseManager
import yaml

with open('config/config.yaml') as f:
    config = yaml.safe_load(f)

db = DatabaseManager(config)
router = LLMRouterV2(config, db)
print('Available providers:', len(router.providers))
"
```

### Rate Limiting

If you hit rate limits:
1. Increase `politeness_delay_seconds` in config.yaml
2. Add more LLM provider API keys
3. Reduce `parallel.max_workers`

### Memory Issues

If running out of memory:
```bash
# Check memory usage
free -h

# Reduce workers in config.yaml
parallel:
  max_workers: 2  # Reduce from 4
```

## Security Best Practices

1. **Never commit .env file** - Contains API keys
2. **Use Oracle Cloud IAM** - Restrict SSH access
3. **Enable firewall** - Only allow necessary ports
4. **Rotate API keys** - Periodically update LLM/SEC keys
5. **Monitor costs** - Track Oracle Cloud and LLM API usage
6. **Backup exports** - Download results regularly

## Cost Optimization

### Oracle Cloud
- Use Always Free tier VM.Standard.E2.1.Micro (limited)
- Or VM.Standard.E4.Flex: ~$0.03/OCPU/hour (~$90/month for 4 OCPUs)

### External Services
- **Neon PostgreSQL**: Free tier (10 GB, good for 100K+ rounds)
- **LLM APIs**: All 9 providers are free tier (~315 RPM combined)

### Estimated Monthly Cost
- Oracle Cloud Compute (4 OCPUs): $90/month
- Neon PostgreSQL: $0/month (free tier)
- LLM APIs: $0/month (free tier)
- **Total: ~$90/month**

## Support

For issues:
1. Check logs: `data/logs/v2_pipeline.log`
2. Review configuration: `config/config.yaml`
3. Test database connection: `scripts/test_db_connection.py`
4. Verify environment variables: `.env` file exists and is correct
