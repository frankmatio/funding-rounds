#!/bin/bash
################################################################################
# Setup and Run Script for Oracle Linux (Free Tier)
# No git required - uses files from zip
################################################################################

set -e

DEPLOY_DIR="/opt/funding-rounds"
APP_DIR="$DEPLOY_DIR/v2_parallel_db"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "================================================================================"
echo "V2 Funding Rounds Pipeline - Oracle Linux Setup"
echo "================================================================================"
echo ""

# Detect package manager
if command -v dnf &> /dev/null; then
    PKG="sudo dnf"
elif command -v yum &> /dev/null; then
    PKG="sudo yum"
elif command -v apt &> /dev/null; then
    PKG="sudo apt"
    $PKG update -y
else
    echo -e "${RED}❌ No package manager found (tried dnf, yum, apt)${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Package manager: $PKG"

################################################################################
# STEP 1: Install Python
################################################################################

echo ""
echo "STEP 1: Installing Python..."
echo "--------------------------------------------------------------------------------"

if ! command -v python3 &> /dev/null; then
    echo "Installing Python3..."
    $PKG install -y python3 python3-pip
    # Install venv
    $PKG install -y python3-venv 2>/dev/null || \
    pip3 install virtualenv 2>/dev/null || true
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✓${NC} $PYTHON_VERSION"

# Install PostgreSQL dev libs for psycopg2
if ! python3 -c "import psycopg2" 2>/dev/null; then
    echo "Installing PostgreSQL libraries..."
    $PKG install -y python3-devel postgresql-devel gcc 2>/dev/null || \
    $PKG install -y python3-dev libpq-dev 2>/dev/null || true
fi

# Install screen
if ! command -v screen &> /dev/null; then
    echo "Installing screen..."
    $PKG install -y screen 2>/dev/null || true
fi

echo -e "${GREEN}✓${NC} Prerequisites installed"

################################################################################
# STEP 2: Setup App Directory
################################################################################

echo ""
echo "STEP 2: Setting up application directory..."
echo "--------------------------------------------------------------------------------"

# Create directory
sudo mkdir -p "$APP_DIR"
sudo chown $USER:$USER "$DEPLOY_DIR" 2>/dev/null || true
sudo chown $USER:$USER "$APP_DIR" 2>/dev/null || true

# Check if we're already in the right place
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$SCRIPT_DIR" != "$APP_DIR" ]; then
    echo "Copying files to $APP_DIR..."
    cp -r "$SCRIPT_DIR"/* "$APP_DIR/" 2>/dev/null || true
    cp -r "$SCRIPT_DIR"/.[^.]* "$APP_DIR/" 2>/dev/null || true
    echo -e "${GREEN}✓${NC} Files copied to $APP_DIR"
else
    echo -e "${GREEN}✓${NC} Already in correct directory"
fi

cd "$APP_DIR"

################################################################################
# STEP 3: Check .env File
################################################################################

echo ""
echo "STEP 3: Checking .env file..."
echo "--------------------------------------------------------------------------------"

if [ ! -f "$DEPLOY_DIR/.env" ]; then
    echo -e "${YELLOW}⚠${NC}  .env not found at $DEPLOY_DIR/.env"
    echo ""
    echo "Upload it from your Mac with:"
    echo "  scp -i ~/.ssh/oracle_cloud_key .env opc@YOUR_IP:/opt/funding-rounds/"
    echo ""
    read -p "Create .env manually now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        nano "$DEPLOY_DIR/.env"
    else
        echo -e "${RED}❌ Cannot proceed without .env${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}✓${NC} .env file exists"

################################################################################
# STEP 4: Python Virtual Environment
################################################################################

echo ""
echo "STEP 4: Setting up Python virtual environment..."
echo "--------------------------------------------------------------------------------"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv 2>/dev/null || \
    python3 -m virtualenv venv 2>/dev/null || \
    virtualenv venv
fi

source venv/bin/activate
echo -e "${GREEN}✓${NC} Virtual environment activated"

# Upgrade pip
pip install --upgrade pip --quiet

################################################################################
# STEP 5: Install Python Packages
################################################################################

echo ""
echo "STEP 5: Installing Python packages..."
echo "--------------------------------------------------------------------------------"

# Try binary first (no compilation needed)
pip install --quiet \
    python-dotenv==1.0.0 \
    pyyaml==6.0.1 \
    requests==2.31.0 \
    sqlalchemy==2.0.23 \
    ddgs \
    pandas==2.1.3 \
    openpyxl==3.1.2 \
    tenacity==8.2.3

# Try psycopg2-binary first (no system libs needed)
pip install psycopg2-binary --quiet 2>/dev/null || \
pip install psycopg2 --quiet 2>/dev/null || \
echo -e "${YELLOW}⚠${NC}  psycopg2 install failed - will use SQLite fallback"

echo -e "${GREEN}✓${NC} Python packages installed"

################################################################################
# STEP 6: Create Directories
################################################################################

echo ""
echo "STEP 6: Creating directories..."
echo "--------------------------------------------------------------------------------"

mkdir -p data/logs data/exports data/checkpoints docs
echo -e "${GREEN}✓${NC} Directories created"

################################################################################
# STEP 7: Test Connections
################################################################################

echo ""
echo "STEP 7: Testing connections..."
echo "--------------------------------------------------------------------------------"

python3 scripts/test_db_connection.py

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${YELLOW}⚠${NC}  Connection test had issues. Check .env file."
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

################################################################################
# STEP 8: Run Pipeline
################################################################################

echo ""
echo "================================================================================"
echo "✅ Setup Complete! Ready to run."
echo "================================================================================"
echo ""
MAX_WORKERS=$(grep "max_workers:" config/config.yaml | head -1 | awk '{print $2}')
echo "Workers: $MAX_WORKERS | Network/company: ~450 KB | Free tier limit: 10 GB/month"
echo ""
echo "  1) Test (5 companies)            ~2 MB     5 min"
echo "  2) Small (1,000 companies)       ~450 MB   2 hours"
echo "  3) Medium (10,000 companies)     ~4.5 GB   20 hours"
echo "  4) Large (15,000 companies)      ~6.8 GB   30 hours"
echo "  5) Maximum (20,000 companies)    ~9.0 GB   50 hours  ← MONTHLY"
echo "  6) Custom"
echo "  7) Exit"
echo ""
read -p "Choice [1-7]: " choice

case $choice in
    1) LIMIT=5; BIG=false ;;
    2) LIMIT=1000; BIG=true ;;
    3) LIMIT=10000; BIG=true ;;
    4) LIMIT=15000; BIG=true ;;
    5) LIMIT=20000; BIG=true ;;
    6)
        read -p "Number of companies: " LIMIT
        [[ "$LIMIT" =~ ^[0-9]+$ ]] || { echo "Invalid"; exit 1; }
        (( LIMIT > 100 )) && BIG=true || BIG=false
        ;;
    7) echo "Run later with: bash monthly_run.sh"; exit 0 ;;
    *) echo "Invalid"; exit 1 ;;
esac

NET=$(echo "scale=1; $LIMIT * 0.00045" | bc)
echo ""
echo "Companies: $LIMIT | Network: ~${NET} GB"
echo ""

if (( $(echo "$NET > 9.5" | bc -l) )); then
    echo -e "${YELLOW}⚠  WARNING: May exceed 10 GB free tier limit!${NC}"
    read -p "Continue? (y/N): " -n 1 -r; echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 0
fi

if [ "$BIG" = true ] && command -v screen &> /dev/null; then
    # Kill existing session if any
    screen -S funding-rounds -X quit 2>/dev/null || true
    sleep 1

    # Write run script
    cat > /tmp/run_now.sh << RUNEOF
#!/bin/bash
cd $APP_DIR
source venv/bin/activate
python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS
echo ""
echo "DONE! Press any key to close..."
read -n 1
RUNEOF
    chmod +x /tmp/run_now.sh

    screen -dmS funding-rounds bash /tmp/run_now.sh

    echo -e "${GREEN}✓${NC} Pipeline running in screen session!"
    echo ""
    echo "  Check progress:  screen -r funding-rounds"
    echo "  Detach:          Ctrl+A then D"
    echo "  Logs:            tail -f $APP_DIR/data/logs/v2_pipeline.log"
    echo ""
    sleep 2
    screen -r funding-rounds
else
    echo "Running in foreground..."
    python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS
fi
