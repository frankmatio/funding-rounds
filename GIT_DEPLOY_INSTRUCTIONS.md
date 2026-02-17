# Git Deployment Instructions

## Step 1: Push Code to GitHub (From Your Mac)

```bash
cd /Volumes/DiskExt/Users/hugh/Docs/projects/growth_stage_vc/v2_parallel_db

# Initialize git (if not already done)
git init

# Add all files (gitignore will exclude .env automatically)
git add .

# Commit
git commit -m "Initial commit: V2 pipeline for Oracle Cloud Free Tier"

# Create repo on GitHub first, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# Push to GitHub
git push -u origin main
```

If you get an error about `master` vs `main`:
```bash
git branch -M main
git push -u origin main
```

---

## Step 2: Deploy on Oracle Cloud (Automated)

### Option A: One-Line Deploy

```bash
bash <(curl -sSL https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/v2_parallel_db/deploy_from_git.sh)
```

Replace `YOUR_USERNAME/YOUR_REPO` with your actual GitHub username and repo name.

### Option B: Clone and Deploy

```bash
# SSH to Oracle Cloud
ssh -i ~/.ssh/oracle_cloud_key ubuntu@<YOUR_IP>

# Clone the repo
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git /opt/funding-rounds/v2_parallel_db

# Run deployment script
cd /opt/funding-rounds/v2_parallel_db
bash deploy_from_git.sh
```

---

## Step 3: Add .env File (IMPORTANT!)

The `.env` file is NOT in git (for security). You must upload it separately:

```bash
# From your Mac
scp -i ~/.ssh/oracle_cloud_key \
  /Volumes/DiskExt/Users/hugh/Docs/projects/growth_stage_vc/.env \
  ubuntu@<YOUR_IP>:/opt/funding-rounds/
```

Or create it manually on Oracle Cloud:

```bash
# On Oracle Cloud
nano /opt/funding-rounds/.env

# Paste your API keys and DATABASE_URL, then save (Ctrl+X, Y, Enter)
```

---

## Step 4: Run the Pipeline

```bash
cd /opt/funding-rounds/v2_parallel_db
bash monthly_run.sh
```

Select option 5 for maximum monthly run (20,000 companies).

---

## Updating Code Later

When you make changes and push to git:

```bash
# On your Mac
cd /Volumes/DiskExt/Users/hugh/Docs/projects/growth_stage_vc/v2_parallel_db
git add .
git commit -m "Update: description of changes"
git push
```

Then on Oracle Cloud:

```bash
# On Oracle Cloud
cd /opt/funding-rounds/v2_parallel_db
git pull
source venv/bin/activate
pip install -r requirements.txt  # If requirements changed
bash monthly_run.sh
```

---

## Files Excluded from Git (Security)

The `.gitignore` automatically excludes:
- ✅ `.env` (API keys - NEVER commit this!)
- ✅ `data/` (database files, logs, exports)
- ✅ `venv/` (Python virtual environment)
- ✅ `__pycache__/` (Python cache)

Only code and configuration templates are in git.

---

## Summary

**One-time setup:**
1. Push code to GitHub (from Mac)
2. Run `deploy_from_git.sh` (on Oracle Cloud)
3. Upload `.env` file (never in git!)

**Monthly runs:**
```bash
cd /opt/funding-rounds/v2_parallel_db
bash monthly_run.sh
```

**Updates:**
```bash
# Mac: git push
# Oracle Cloud: git pull && bash monthly_run.sh
```

That's it!
