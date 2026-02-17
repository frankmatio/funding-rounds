#!/bin/bash
################################################################################
# Deploy V2 Pipeline from Git Repository
# Oracle Cloud Always Free Tier - Monthly Run
################################################################################

set -e

echo "================================================================================"
echo "V2 Pipeline - Git Deployment"
echo "================================================================================"
echo ""

# Configuration
GIT_REPO="https://github.com/frankmatio/funding-rounds.git"
DEPLOY_DIR="/opt/funding-rounds"
APP_DIR="$DEPLOY_DIR/v2_parallel_db"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

################################################################################
# Check if running on Oracle Cloud or locally
################################################################################

if [ -f "/etc/oracle-cloud-agent/oracle-cloud-agent.conf" ] || [ "$(uname -n)" != "$(hostname -f 2>/dev/null || echo 'local')" ]; then
    RUNNING_ON_OCI=true
    echo "Detected: Oracle Cloud Instance"
else
    RUNNING_ON_OCI=false
    echo "Detected: Local/Mac environment"
fi

echo ""

################################################################################
# STEP 1: Check prerequisites
################################################################################

echo "STEP 1: Checking prerequisites..."
echo "--------------------------------------------------------------------------------"

# Check git
if ! command -v git &> /dev/null; then
    echo -e "${YELLOW}⚠${NC}  Git not found. Installing..."
    if [ "$RUNNING_ON_OCI" = true ]; then
        sudo apt update
        sudo apt install -y git
    else
        echo -e "${RED}❌ Please install git first${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓${NC} Git installed"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 not found${NC}"
    if [ "$RUNNING_ON_OCI" = true ]; then
        echo "Installing Python3..."
        sudo apt install -y python3 python3-pip python3-venv libpq-dev
    else
        exit 1
    fi
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓${NC} Python version: $PYTHON_VERSION"

echo ""

################################################################################
# STEP 2: Get Git Repository URL
################################################################################

echo "STEP 2: Git repository setup..."
echo "--------------------------------------------------------------------------------"

# Check if GIT_REPO is set
if [ "$GIT_REPO" = "YOUR_GIT_REPO_URL" ]; then
    echo -e "${YELLOW}⚠${NC}  Git repository URL not configured in script."
    echo ""
    read -p "Enter your git repository URL (e.g., https://github.com/username/repo.git): " REPO_INPUT

    if [ -z "$REPO_INPUT" ]; then
        echo -e "${RED}❌ No repository URL provided${NC}"
        exit 1
    fi

    GIT_REPO="$REPO_INPUT"
fi

echo "Repository: $GIT_REPO"
echo ""

################################################################################
# STEP 3: Clone or update repository
################################################################################

echo "STEP 3: Getting code from git..."
echo "--------------------------------------------------------------------------------"

# Create deploy directory if it doesn't exist
sudo mkdir -p "$DEPLOY_DIR"
sudo chown $USER:$USER "$DEPLOY_DIR" 2>/dev/null || true

if [ -d "$APP_DIR/.git" ]; then
    echo "Repository already exists. Updating..."
    cd "$APP_DIR"

    # Stash any local changes
    if ! git diff-index --quiet HEAD --; then
        echo -e "${YELLOW}⚠${NC}  Local changes detected. Stashing..."
        git stash
    fi

    # Pull latest changes
    git pull origin main || git pull origin master

    echo -e "${GREEN}✓${NC} Code updated from git"
else
    echo "Cloning repository..."
    cd "$DEPLOY_DIR"

    # Clone the repo
    git clone "$GIT_REPO" v2_parallel_db

    echo -e "${GREEN}✓${NC} Code cloned from git"
fi

cd "$APP_DIR"
echo ""

################################################################################
# STEP 4: Check for .env file
################################################################################

echo "STEP 4: Checking environment configuration..."
echo "--------------------------------------------------------------------------------"

if [ ! -f "../.env" ]; then
    echo -e "${YELLOW}⚠${NC}  .env file not found at $DEPLOY_DIR/.env"
    echo ""
    echo "The .env file contains your API keys and database credentials."
    echo "It should NOT be in git (security risk)."
    echo ""

    if [ "$RUNNING_ON_OCI" = true ]; then
        echo "Please create it manually with your credentials:"
        echo ""
        echo "  nano $DEPLOY_DIR/.env"
        echo ""
        echo "Or upload it from your local machine:"
        echo ""
        echo "  scp -i ~/.ssh/oracle_cloud_key .env ubuntu@YOUR_IP:/opt/funding-rounds/"
        echo ""

        read -p "Do you want to create it now? (y/N): " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            nano "$DEPLOY_DIR/.env"
        else
            echo -e "${RED}❌ Cannot proceed without .env file${NC}"
            exit 1
        fi
    else
        echo "Please upload .env to Oracle Cloud:"
        echo "  scp -i ~/.ssh/oracle_cloud_key .env ubuntu@YOUR_IP:/opt/funding-rounds/"
        exit 1
    fi
fi

echo -e "${GREEN}✓${NC} .env file exists"
echo ""

################################################################################
# STEP 5: Create virtual environment
################################################################################

echo "STEP 5: Setting up Python virtual environment..."
echo "--------------------------------------------------------------------------------"

if [ -d "venv" ]; then
    echo -e "${YELLOW}⚠${NC}  Virtual environment exists"

    if [ "$RUNNING_ON_OCI" = true ]; then
        read -p "Recreate virtual environment? (y/N): " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf venv
            python3 -m venv venv
            echo -e "${GREEN}✓${NC} Virtual environment recreated"
        else
            echo -e "${GREEN}✓${NC} Using existing virtual environment"
        fi
    else
        echo -e "${GREEN}✓${NC} Using existing virtual environment"
    fi
else
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
fi

echo ""

################################################################################
# STEP 6: Install dependencies
################################################################################

echo "STEP 6: Installing dependencies..."
echo "--------------------------------------------------------------------------------"

source venv/bin/activate

pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo -e "${GREEN}✓${NC} Dependencies installed"
echo ""

################################################################################
# STEP 7: Create directories
################################################################################

echo "STEP 7: Creating directories..."
echo "--------------------------------------------------------------------------------"

mkdir -p data/logs
mkdir -p data/exports
mkdir -p data/checkpoints

echo -e "${GREEN}✓${NC} Directories created"
echo ""

################################################################################
# STEP 8: Test connections
################################################################################

echo "STEP 8: Testing database and API connections..."
echo "--------------------------------------------------------------------------------"

python3 scripts/test_db_connection.py

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ Connection test failed${NC}"
    exit 1
fi

echo ""

################################################################################
# STEP 9: Display info
################################################################################

echo "================================================================================"
echo "✅ Deployment Complete!"
echo "================================================================================"
echo ""
echo "Configuration:"
MAX_WORKERS=$(grep "max_workers:" config/config.yaml | head -1 | awk '{print $2}')
echo "  Workers: $MAX_WORKERS"
echo "  CSV: docs/growth_companies_to_scrap.csv"
echo ""
echo "Monthly capacity (10 GB network limit):"
echo "  20,000 companies: ~9.0 GB, ~50 hours"
echo ""

################################################################################
# STEP 10: Run options
################################################################################

if [ "$RUNNING_ON_OCI" = false ]; then
    echo "To run on Oracle Cloud, SSH and execute:"
    echo "  cd $APP_DIR"
    echo "  bash monthly_run.sh"
    echo ""
    exit 0
fi

echo "What would you like to do?"
echo ""
echo "1) Test run (5 companies) - ~5 minutes"
echo "2) Small batch (1,000 companies) - ~2 hours"
echo "3) Medium batch (10,000 companies) - ~20 hours"
echo "4) Large batch (15,000 companies) - ~30 hours"
echo "5) Maximum (20,000 companies) - ~50 hours - RECOMMENDED MONTHLY"
echo "6) Custom number"
echo "7) Exit (run manually later)"
echo ""

read -p "Choice [1-7]: " choice

case $choice in
    1) LIMIT=5 ;;
    2) LIMIT=1000 ;;
    3) LIMIT=10000 ;;
    4) LIMIT=15000 ;;
    5) LIMIT=20000 ;;
    6)
        read -p "Number of companies: " LIMIT
        if ! [[ "$LIMIT" =~ ^[0-9]+$ ]]; then
            echo -e "${RED}Invalid number${NC}"
            exit 1
        fi
        ;;
    7)
        echo ""
        echo "To run later:"
        echo "  cd $APP_DIR"
        echo "  bash monthly_run.sh"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

NETWORK_GB=$(echo "scale=2; $LIMIT * 0.00045" | bc)
echo ""
echo "Processing: $LIMIT companies"
echo "Network: ~${NETWORK_GB} GB"
echo ""

if (( $(echo "$NETWORK_GB > 9.5" | bc -l) )); then
    echo -e "${YELLOW}⚠  WARNING: Exceeds 9.5 GB!${NC}"
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# Install screen if needed
if (( LIMIT > 100 )); then
    if ! command -v screen &> /dev/null; then
        echo "Installing screen..."
        sudo apt install -y screen
    fi

    echo "Starting in screen session..."
    screen -dmS funding-rounds bash -c "cd $(pwd) && source venv/bin/activate && python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS"

    echo ""
    echo -e "${GREEN}✓${NC} Pipeline started in screen!"
    echo ""
    echo "To check progress:"
    echo "  screen -r funding-rounds"
    echo ""
    sleep 3
    screen -r funding-rounds
else
    echo "Running in foreground..."
    python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS
fi

echo ""
echo "✓ Done!"
