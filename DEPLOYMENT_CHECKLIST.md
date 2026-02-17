# Oracle Cloud Deployment Checklist

Use this checklist to ensure successful deployment.

## Pre-Deployment

- [ ] Oracle Cloud Compute instance provisioned
  - [ ] VM.Standard.E4.Flex (4 OCPUs, 16 GB RAM recommended)
  - [ ] Ubuntu 22.04 or Oracle Linux 8
  - [ ] 50-100 GB storage
  - [ ] SSH access configured

- [ ] External services ready
  - [ ] Neon PostgreSQL connection string available
  - [ ] 9 LLM API keys collected (minimum 1 required)
  - [ ] 10 SEC user agents prepared (minimum 1 required)

- [ ] Local preparation
  - [ ] .env file created with all credentials
  - [ ] config.yaml reviewed and customized
  - [ ] Code tested locally (optional but recommended)

## Deployment Steps

- [ ] Connect to Oracle Cloud instance via SSH
- [ ] Install system dependencies
  ```bash
  sudo apt update && sudo apt upgrade -y
  sudo apt install -y python3 python3-pip python3-venv git libpq-dev
  ```

- [ ] Create application directory
  ```bash
  sudo mkdir -p /opt/funding-rounds
  sudo chown ubuntu:ubuntu /opt/funding-rounds
  ```

- [ ] Upload code to instance
  ```bash
  # From local machine:
  cd /Volumes/DiskExt/Users/hugh/Docs/projects/growth_stage_vc
  scp -i ~/.ssh/oracle_cloud_key -r v2_parallel_db .env ubuntu@<IP>:/opt/funding-rounds/
  ```

- [ ] Setup Python virtual environment
  ```bash
  cd /opt/funding-rounds/v2_parallel_db
  python3 -m venv venv
  source venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  ```

- [ ] Verify environment variables
  ```bash
  ls -la /opt/funding-rounds/.env
  # File should exist and contain DATABASE_URL and API keys
  ```

- [ ] Initialize database
  ```bash
  cd /opt/funding-rounds/v2_parallel_db
  source venv/bin/activate
  python3 scripts/init_db.py
  ```

- [ ] Run connection tests
  ```bash
  python3 scripts/test_db_connection.py
  # Should show:
  # ✅ ALL SYSTEMS READY FOR DEPLOYMENT
  ```

## Testing

- [ ] Test run with 3 companies
  ```bash
  python3 run_pipeline_v2.py --limit 3 --workers 2
  ```

- [ ] Verify results
  - [ ] Check database has data
  - [ ] Check exports created in data/exports/
  - [ ] Review logs in data/logs/v2_pipeline.log

## Production Setup

- [ ] Configure systemd service (optional, for auto-restart)
  ```bash
  sudo cp funding-rounds.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable funding-rounds.service
  ```

- [ ] OR setup screen/tmux session
  ```bash
  sudo apt install -y screen
  screen -S funding-rounds
  # Run pipeline inside screen
  # Detach with Ctrl+A, D
  ```

## Production Run

- [ ] Start production run
  ```bash
  # Full run
  python3 run_pipeline_v2.py --full --workers 4

  # OR with limit
  python3 run_pipeline_v2.py --limit 100 --workers 4
  ```

- [ ] Monitor progress
  ```bash
  tail -f data/logs/v2_pipeline.log
  ```

## Post-Deployment

- [ ] Verify data in Neon PostgreSQL
  - [ ] Connect via psql or pgAdmin
  - [ ] Check companies table
  - [ ] Check funding_rounds table

- [ ] Download exports
  ```bash
  # From local machine:
  scp -i ~/.ssh/oracle_cloud_key \
    ubuntu@<IP>:/opt/funding-rounds/v2_parallel_db/data/exports/*.xlsx \
    ~/Downloads/
  ```

- [ ] Setup backup/export schedule (optional)
  - [ ] Create cron job for periodic exports
  - [ ] Setup log rotation

## Monitoring

- [ ] Setup monitoring
  - [ ] CPU/memory usage: `htop`
  - [ ] Disk space: `df -h`
  - [ ] Pipeline logs: `tail -f data/logs/v2_pipeline.log`

- [ ] Check LLM usage
  - [ ] Monitor rate limits in logs
  - [ ] Verify rotation is working
  - [ ] Check for API errors

## Troubleshooting

If issues occur:

1. **Database connection failed**
   ```bash
   # Check DATABASE_URL in .env
   cat /opt/funding-rounds/.env | grep DATABASE_URL

   # Test connection manually
   python3 scripts/test_db_connection.py
   ```

2. **LLM API errors**
   ```bash
   # Check API keys
   python3 scripts/test_db_connection.py

   # Review logs for specific errors
   grep -i "error" data/logs/v2_pipeline.log
   ```

3. **Out of memory**
   ```bash
   # Check memory
   free -h

   # Reduce workers in config.yaml
   nano config/config.yaml
   # Set parallel.max_workers: 2
   ```

4. **Slow performance**
   - Increase `politeness_delay_seconds` if rate limited
   - Add more LLM API keys for higher throughput
   - Check network latency to Neon PostgreSQL

## Security Checklist

- [ ] .env file has restricted permissions
  ```bash
  chmod 600 /opt/funding-rounds/.env
  ```

- [ ] Oracle Cloud firewall configured
  - [ ] Only SSH (22) open for your IP
  - [ ] Outbound HTTPS (443) allowed

- [ ] Regular security updates
  ```bash
  sudo apt update && sudo apt upgrade -y
  ```

- [ ] API keys rotated periodically

## Success Criteria

✅ Deployment is successful when:

- [ ] Connection test passes completely
- [ ] Test run completes without errors
- [ ] Data appears in Neon PostgreSQL
- [ ] Exports are generated correctly
- [ ] Logs show normal operation
- [ ] All 4 stages complete successfully

## Estimated Timeline

- Provisioning Oracle Cloud instance: 10 minutes
- System setup and dependencies: 10 minutes
- Code upload and Python setup: 5 minutes
- Database initialization: 2 minutes
- Testing: 5 minutes
- **Total: ~30 minutes**

Production run time depends on:
- Number of companies
- Number of workers
- LLM API rate limits

**Estimated rates:**
- SEC collection: ~10-20 companies/minute
- Search extraction: ~5-10 companies/minute (depends on LLM)
- Total: ~5-15 companies/minute

**For 1000 companies:**
- Estimated time: 1-3 hours (with 4 workers)
