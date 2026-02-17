# Using CockroachDB with V2 Pipeline

## Overview

The V2 pipeline supports **CockroachDB** (a distributed, PostgreSQL-compatible database) out of the box. CockroachDB is great for:
- ✅ Cloud-native distributed database
- ✅ Built-in replication and resilience
- ✅ PostgreSQL wire protocol compatible
- ✅ Free tier available

---

## Quick Setup

### 1. Add Your CockroachDB Connection String to `.env`

Add this to your `.env` file (in the parent directory):

```bash
DATABASE_URL=postgresql://hd_kenpach:mrndeLaz-wusqffsdsfd0wRA@dour-flyer-20438.j77.aws-us-east-1.cockroachlabs.cloud:26257/aquadb?sslmode=verify-full
```

### 2. Update `config/config.yaml`

Change the database type from `sqlite` to `postgresql`:

```yaml
# Database Configuration
database:
  type: postgresql  # Changed from sqlite
  sqlite:
    path: data/funding_rounds.db
  postgresql:
    connection_string: ${DATABASE_URL}  # Reads from .env
```

### 3. Install Dependencies (if not already installed)

```bash
cd v2_parallel_db
pip install -r requirements.txt
```

This includes `psycopg2-binary` which is needed for PostgreSQL/CockroachDB connections.

### 4. Initialize Database Schema

```bash
python3 scripts/init_db.py
```

This will create all the tables in your CockroachDB database.

### 5. Run the Pipeline

```bash
# Test with 20 companies
python3 run_pipeline_v2.py

# Full run with 4 workers
python3 run_pipeline_v2.py --full --workers 4
```

---

## CockroachDB Connection String Breakdown

Your connection string:
```
postgresql://hd_kenpach:mrndeLaz-wusqffsdsfd0wRA@dour-flyer-20438.j77.aws-us-east-1.cockroachlabs.cloud:26257/aquadb?sslmode=verify-full
```

**Components:**
- **Protocol**: `postgresql://` (CockroachDB uses PostgreSQL wire protocol)
- **Username**: `hd_kenpach`
- **Password**: `mrndeLaz-wusqffsdsfd0wRA`
- **Host**: `dour-flyer-20438.j77.aws-us-east-1.cockroachlabs.cloud`
- **Port**: `26257` (CockroachDB's default port, not 5432)
- **Database**: `aquadb`
- **SSL Mode**: `verify-full` (required for CockroachDB Cloud)

---

## Benefits of Using CockroachDB

### vs SQLite
- ✅ **Distributed**: Data replicated across multiple nodes
- ✅ **Concurrent writes**: Multiple workers can write simultaneously
- ✅ **Cloud-hosted**: No need to manage database files
- ✅ **Backups**: Automatic backups in CockroachDB Cloud
- ✅ **Scalability**: Can handle much larger datasets

### vs Local PostgreSQL
- ✅ **No server setup**: Fully managed cloud service
- ✅ **High availability**: Automatic failover
- ✅ **Global distribution**: Data centers worldwide
- ✅ **Free tier**: Generous free tier available

---

## Performance Considerations

### Parallel Processing with CockroachDB

CockroachDB excels with parallel writes:
- **SQLite**: Write operations are serialized (but batched)
- **CockroachDB**: Multiple workers can write concurrently

**Recommended settings for CockroachDB:**
```yaml
parallel:
  max_workers: 8       # Can use more workers than SQLite
  batch_size: 50       # Smaller batches for more frequent commits
  checkpoint_interval: 5  # More frequent checkpoints
```

### Network Latency

Since CockroachDB is cloud-hosted:
- Expect slightly higher latency than local SQLite (network roundtrip)
- But faster overall due to better concurrent write performance
- Use batching to minimize network calls

---

## Monitoring Your CockroachDB Database

### Check Database Statistics

```bash
python3 -c "
from src.database import DatabaseManager
import yaml
import os
from dotenv import load_dotenv

load_dotenv('../.env')  # Load DATABASE_URL

with open('config/config.yaml') as f:
    config = yaml.safe_load(f)

db = DatabaseManager(config)
stats = db.get_statistics()

print('=== Database Statistics ===')
print(f'Companies: {stats[\"companies\"]}')
print(f'Funding rounds: {stats[\"funding_rounds\"]}')
print(f'Investors: {stats[\"investors\"]}')
print(f'Sources: {stats[\"sources\"]}')
print(f'Duplicates removed: {stats[\"duplicates_found\"]}')
print(f'Total raised: \${stats[\"total_amount_raised_usd\"]:,.0f}')
"
```

### CockroachDB Console

You can also monitor your database via the CockroachDB Cloud console:
1. Go to https://cockroachlabs.cloud/
2. Login to your account
3. View your cluster metrics, queries, and data

---

## Troubleshooting

### Connection Issues

**SSL Certificate Errors:**
```bash
# Ensure SSL mode is set in connection string
?sslmode=verify-full
```

**Timeout Issues:**
```bash
# Add connect_timeout to connection string
?sslmode=verify-full&connect_timeout=10
```

**Authentication Errors:**
- Verify username and password are correct
- Check that user has permissions on the database

### Performance Issues

**Slow Writes:**
```yaml
# Reduce batch size for more frequent commits
parallel:
  batch_size: 20  # Smaller batches
```

**High Latency:**
```yaml
# Reduce workers to minimize concurrent connections
parallel:
  max_workers: 4
```

---

## Migration from SQLite to CockroachDB

If you've been using SQLite and want to migrate to CockroachDB:

### Option 1: Export and Re-import

```bash
# 1. Export from SQLite to JSON
cd v2_parallel_db
python3 -c "
from src.database import DatabaseManager
from src.exporter_v2 import ExporterV2
import yaml

# Load with SQLite
with open('config/config.yaml') as f:
    config = yaml.safe_load(f)

config['database']['type'] = 'sqlite'
db = DatabaseManager(config)
exporter = ExporterV2(config, db)

with db.session_scope() as session:
    exporter.export_to_json(session)
"

# 2. Switch to CockroachDB in config.yaml

# 3. Initialize CockroachDB schema
python3 scripts/init_db.py

# 4. Re-run pipeline (it will skip already processed companies via checkpointing)
python3 run_pipeline_v2.py --full --workers 4
```

### Option 2: Fresh Start

Simply switch to CockroachDB and re-run the pipeline. The checkpointing system will track progress in the new database.

---

## Cost Considerations

### CockroachDB Free Tier

CockroachDB offers a generous free tier:
- ✅ **5 GB storage**
- ✅ **50M Request Units per month**
- ✅ **1 vCPU**
- ✅ **Unlimited users**

**Estimated usage for your workload:**
- 3,834 companies × ~10 rounds each = ~40,000 rows
- Estimated storage: **~50-100 MB** (well within 5 GB limit)
- Monthly runs should stay within free tier

### Upgrading

If you exceed free tier limits:
- CockroachDB Serverless: Pay as you go ($1-5/month for your workload)
- CockroachDB Dedicated: Starting at $0.50/hour

---

## Recommended Configuration for CockroachDB

**For Oracle Cloud + CockroachDB:**

```yaml
# config/config.yaml
database:
  type: postgresql
  postgresql:
    connection_string: ${DATABASE_URL}

parallel:
  max_workers: 6  # More than SQLite (concurrent writes supported)
  batch_size: 50  # Smaller batches
  checkpoint_interval: 5  # More frequent checkpoints

search:
  politeness_delay_seconds: 1  # Faster iteration

export:
  formats:
    - excel
    - json  # Remove CSV if not needed
```

**Benefits:**
- Better concurrent write performance
- More frequent checkpoints (better resume capability)
- Automatic cloud backups
- No database file management

---

## Summary

**To use CockroachDB:**
1. Add `DATABASE_URL` to `.env` ✅
2. Change `database.type` to `postgresql` in `config/config.yaml` ✅
3. Run `python3 scripts/init_db.py` ✅
4. Run pipeline normally ✅

**You're all set!** The V2 pipeline now supports CockroachDB with the same features as SQLite, but with better concurrency and cloud-native benefits.
