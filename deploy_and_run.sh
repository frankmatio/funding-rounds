#!/bin/bash
################################################################################
# Complete Deploy and Run Script
# Downloads from GitHub, sets up everything, and runs the pipeline
################################################################################

set -e

# Configuration
GIT_REPO="https://github.com/frankmatio/funding-rounds.git"
DEPLOY_DIR="/opt/funding-rounds"
APP_DIR="$DEPLOY_DIR/v2_parallel_db"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "================================================================================"
echo "V2 Funding Rounds Pipeline - Complete Deployment & Run"
echo "================================================================================"
echo ""
echo "This script will:"
echo "  1. Clone/update code from GitHub"
echo "  2. Setup Python environment"
echo "  3. Install dependencies"
echo "  4. Test connections"
echo "  5. Run the pipeline"
echo ""
read -p "Continue? (Y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    exit 0
fi

################################################################################
# STEP 1: Install Prerequisites
################################################################################

echo ""
echo "================================================================================"
echo "STEP 1: Installing Prerequisites"
echo "================================================================================"

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

# Install git if needed
if ! command -v git &> /dev/null; then
    echo "Installing git..."
    $SUDO apt update
    $SUDO apt install -y git
fi
echo -e "${GREEN}✓${NC} Git installed"

# Install Python if needed
if ! command -v python3 &> /dev/null; then
    echo "Installing Python3..."
    $SUDO apt install -y python3 python3-pip python3-venv libpq-dev
fi
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION installed"

# Install screen for background runs
if ! command -v screen &> /dev/null; then
    echo "Installing screen..."
    $SUDO apt install -y screen
fi
echo -e "${GREEN}✓${NC} Screen installed"

################################################################################
# STEP 2: Download/Update Code
################################################################################

echo ""
echo "================================================================================"
echo "STEP 2: Getting Code from GitHub"
echo "================================================================================"

# Create deploy directory
$SUDO mkdir -p "$DEPLOY_DIR"
$SUDO chown $USER:$USER "$DEPLOY_DIR" 2>/dev/null || true

if [ -d "$APP_DIR/.git" ]; then
    echo "Repository exists. Updating..."
    cd "$APP_DIR"

    # Stash local changes
    if ! git diff-index --quiet HEAD --; then
        echo -e "${YELLOW}⚠${NC}  Stashing local changes..."
        git stash
    fi

    git pull origin main
    echo -e "${GREEN}✓${NC} Code updated from GitHub"
else
    echo "Cloning repository..."
    cd "$DEPLOY_DIR"

    # Remove old directory if exists but not git
    if [ -d "v2_parallel_db" ]; then
        echo "Removing old non-git directory..."
        rm -rf v2_parallel_db
    fi

    git clone "$GIT_REPO" .
    echo -e "${GREEN}✓${NC} Code cloned from GitHub"
fi

cd "$APP_DIR"

################################################################################
# STEP 3: Check .env File
################################################################################

echo ""
echo "================================================================================"
echo "STEP 3: Checking Environment Configuration"
echo "================================================================================"

if [ ! -f "$DEPLOY_DIR/.env" ]; then
    echo -e "${RED}❌ ERROR: .env file not found${NC}"
    echo ""
    echo "The .env file contains your API keys and database credentials."
    echo "Location: $DEPLOY_DIR/.env"
    echo ""
    echo "Please create it with:"
    echo ""
    echo "  nano $DEPLOY_DIR/.env"
    echo ""
    echo "Or upload from your local machine:"
    echo ""
    echo "  scp -i ~/.ssh/oracle_cloud_key .env ubuntu@YOUR_IP:/opt/funding-rounds/"
    echo ""
    read -p "Create .env file now? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        nano "$DEPLOY_DIR/.env"

        if [ ! -f "$DEPLOY_DIR/.env" ]; then
            echo -e "${RED}❌ .env file still not found. Exiting.${NC}"
            exit 1
        fi
    else
        echo -e "${RED}❌ Cannot proceed without .env file${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓${NC} .env file exists"

################################################################################
# STEP 4: Setup Python Environment
################################################################################

echo ""
echo "================================================================================"
echo "STEP 4: Setting up Python Environment"
echo "================================================================================"

if [ -d "venv" ]; then
    echo "Virtual environment exists"
else
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
echo -e "${GREEN}✓${NC} Virtual environment activated"

# Upgrade pip
pip install --upgrade pip --quiet

# Install dependencies
echo "Installing Python packages..."
pip install -r requirements.txt --quiet
echo -e "${GREEN}✓${NC} Dependencies installed"

################################################################################
# STEP 5: Create Directories
################################################################################

echo ""
echo "================================================================================"
echo "STEP 5: Creating Directories"
echo "================================================================================"

mkdir -p data/logs
mkdir -p data/exports
mkdir -p data/checkpoints
mkdir -p docs

echo -e "${GREEN}✓${NC} Directories created"

################################################################################
# STEP 6: Test Connections
################################################################################

echo ""
echo "================================================================================"
echo "STEP 6: Testing Connections"
echo "================================================================================"

python3 scripts/test_db_connection.py

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ Connection test failed!${NC}"
    echo ""
    echo "Please check:"
    echo "  1. DATABASE_URL in .env"
    echo "  2. LLM API keys in .env"
    echo "  3. Network connectivity"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

################################################################################
# STEP 7: Run Pipeline
################################################################################

echo ""
echo "================================================================================"
echo "STEP 7: Run Pipeline"
echo "================================================================================"

MAX_WORKERS=$(grep "max_workers:" config/config.yaml | head -1 | awk '{print $2}')

echo ""
echo "Configuration:"
echo "  Workers: $MAX_WORKERS"
echo "  Network per company: ~450 KB"
echo ""
echo "Select batch size:"
echo ""
echo "  1) Test (5 companies) - ~2 MB, 5 min"
echo "  2) Small (1,000 companies) - ~450 MB, 2 hours"
echo "  3) Medium (10,000 companies) - ~4.5 GB, 20 hours"
echo "  4) Large (15,000 companies) - ~6.8 GB, 30 hours"
echo "  5) Maximum (20,000 companies) - ~9.0 GB, 50 hours ${BLUE}← MONTHLY${NC}"
echo "  6) Custom"
echo "  7) Exit (don't run now)"
echo ""

read -p "Choice [1-7]: " choice

case $choice in
    1) LIMIT=5; RUN_IN_SCREEN=false ;;
    2) LIMIT=1000; RUN_IN_SCREEN=true ;;
    3) LIMIT=10000; RUN_IN_SCREEN=true ;;
    4) LIMIT=15000; RUN_IN_SCREEN=true ;;
    5) LIMIT=20000; RUN_IN_SCREEN=true ;;
    6)
        read -p "Number of companies: " LIMIT
        if ! [[ "$LIMIT" =~ ^[0-9]+$ ]]; then
            echo -e "${RED}Invalid number${NC}"
            exit 1
        fi
        if (( LIMIT > 100 )); then
            RUN_IN_SCREEN=true
        else
            RUN_IN_SCREEN=false
        fi
        ;;
    7)
        echo ""
        echo "Setup complete! To run manually:"
        echo ""
        echo "  cd $APP_DIR"
        echo "  source venv/bin/activate"
        echo "  python3 run_pipeline_v2.py --limit 20000 --workers $MAX_WORKERS"
        echo ""
        echo "Or use the quick launcher:"
        echo ""
        echo "  cd $APP_DIR"
        echo "  bash monthly_run.sh"
        echo ""
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

NETWORK_GB=$(echo "scale=2; $LIMIT * 0.00045" | bc)

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Starting Pipeline Run${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "  Companies:     $LIMIT"
echo "  Network usage: ~${NETWORK_GB} GB"
echo "  Workers:       $MAX_WORKERS"
echo ""

if (( $(echo "$NETWORK_GB > 9.5" | bc -l) )); then
    echo -e "${YELLOW}⚠  WARNING: This will use ${NETWORK_GB} GB (exceeds 9.5 GB limit!)${NC}"
    echo "You may incur charges. Oracle Free Tier limit is 10 GB/month."
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

# Run the pipeline
if [ "$RUN_IN_SCREEN" = true ]; then
    echo ""
    echo "Starting pipeline in screen session..."
    echo ""

    # Check for existing screen session
    if screen -list | grep -q "funding-rounds"; then
        echo -e "${YELLOW}⚠  Screen session 'funding-rounds' already exists!${NC}"
        read -p "Kill it and start new? (y/N): " -n 1 -r
        echo

        if [[ $REPLY =~ ^[Yy]$ ]]; then
            screen -S funding-rounds -X quit
            sleep 1
        else
            echo ""
            echo "Attach to existing session with:"
            echo "  screen -r funding-rounds"
            echo ""
            exit 0
        fi
    fi

    # Create startup script for screen
    cat > /tmp/run_pipeline.sh << EOFRUN
#!/bin/bash
cd "$APP_DIR"
source venv/bin/activate
python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS
echo ""
echo "================================================================================"
echo "Pipeline complete!"
echo "================================================================================"
echo ""
echo "Press any key to close this screen session, or Ctrl+A D to detach..."
read -n 1
EOFRUN

    chmod +x /tmp/run_pipeline.sh

    # Start in detached screen
    screen -dmS funding-rounds bash /tmp/run_pipeline.sh

    echo ""
    echo -e "${GREEN}✓${NC} Pipeline started in screen session!"
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Pipeline Running in Background${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Session: funding-rounds"
    echo "Companies: $LIMIT"
    echo "Duration: ~$((LIMIT / 5)) minutes (estimated)"
    echo ""
    echo "Commands:"
    echo "  Check progress:  screen -r funding-rounds"
    echo "  Detach:          Ctrl+A, then D"
    echo "  View logs:       tail -f $APP_DIR/data/logs/v2_pipeline.log"
    echo ""
    echo "Connecting to screen in 3 seconds..."
    echo "(Press Ctrl+C to cancel and leave it running)"
    sleep 3

    # Attach to screen
    screen -r funding-rounds
else
    # Small run, foreground
    echo ""
    echo "Running in foreground..."
    echo ""
    python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS
fi

echo ""
echo "================================================================================"
echo "✅ Complete!"
echo "================================================================================"
echo ""
echo "Results are in:"
echo "  Database: Neon PostgreSQL (accessible from other apps)"
echo "  Exports:  $APP_DIR/data/exports/"
echo "  Logs:     $APP_DIR/data/logs/v2_pipeline.log"
echo ""
echo "To download exports to your Mac:"
echo "  scp -i ~/.ssh/oracle_cloud_key \\"
echo "    ubuntu@YOUR_IP:$APP_DIR/data/exports/*.xlsx \\"
echo "    ~/Downloads/"
echo ""
