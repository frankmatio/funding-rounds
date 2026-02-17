#!/bin/bash
################################################################################
# V2 Pipeline - Complete Setup and Launch Script
# Oracle Cloud Always Free Tier - Monthly Run
################################################################################

set -e  # Exit on error

echo "================================================================================"
echo "Funding Round Data Collection Engine V2 - Setup & Launch"
echo "Oracle Cloud Always Free Tier - Monthly Run Model"
echo "================================================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

################################################################################
# STEP 1: Check Prerequisites
################################################################################

echo "STEP 1: Checking prerequisites..."
echo "--------------------------------------------------------------------------------"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 not found. Please install Python 3.9+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo -e "${GREEN}✓${NC} Python version: $PYTHON_VERSION"

# Check if we're in the right directory
if [ ! -f "run_pipeline_v2.py" ]; then
    echo -e "${RED}❌ Error: run_pipeline_v2.py not found${NC}"
    echo "Please run this script from: /opt/funding-rounds/v2_parallel_db/"
    exit 1
fi

echo -e "${GREEN}✓${NC} In correct directory: $(pwd)"

# Check if .env exists in parent directory
if [ ! -f "../.env" ]; then
    echo -e "${RED}❌ Error: .env file not found in parent directory${NC}"
    echo "Expected location: /opt/funding-rounds/.env"
    exit 1
fi

echo -e "${GREEN}✓${NC} Found .env file"

# Check if config.yaml exists
if [ ! -f "config/config.yaml" ]; then
    echo -e "${RED}❌ Error: config/config.yaml not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Found config.yaml"

echo ""

################################################################################
# STEP 2: Create Virtual Environment
################################################################################

echo "STEP 2: Setting up Python virtual environment..."
echo "--------------------------------------------------------------------------------"

if [ -d "venv" ]; then
    echo -e "${YELLOW}⚠${NC}  Virtual environment already exists"
    read -p "Do you want to recreate it? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing old virtual environment..."
        rm -rf venv
        echo "Creating new virtual environment..."
        python3 -m venv venv
        echo -e "${GREEN}✓${NC} Virtual environment recreated"
    else
        echo -e "${GREEN}✓${NC} Using existing virtual environment"
    fi
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
fi

echo ""

################################################################################
# STEP 3: Install Dependencies
################################################################################

echo "STEP 3: Installing Python dependencies..."
echo "--------------------------------------------------------------------------------"

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Install requirements
echo "Installing requirements from requirements.txt..."
pip install -r requirements.txt --quiet

echo -e "${GREEN}✓${NC} All dependencies installed"
echo ""

################################################################################
# STEP 4: Create Directories
################################################################################

echo "STEP 4: Creating necessary directories..."
echo "--------------------------------------------------------------------------------"

mkdir -p data/logs
mkdir -p data/exports
mkdir -p data/checkpoints

echo -e "${GREEN}✓${NC} Directories created:
  - data/logs
  - data/exports
  - data/checkpoints"
echo ""

################################################################################
# STEP 5: Test Database Connection
################################################################################

echo "STEP 5: Testing database and API connections..."
echo "--------------------------------------------------------------------------------"

python3 scripts/test_db_connection.py

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ Connection test failed!${NC}"
    echo "Please check:"
    echo "  1. DATABASE_URL in .env file"
    echo "  2. LLM API keys in .env file"
    echo "  3. Network connectivity"
    exit 1
fi

echo ""

################################################################################
# STEP 6: Display Configuration
################################################################################

echo "STEP 6: Current configuration..."
echo "--------------------------------------------------------------------------------"

MAX_WORKERS=$(grep "max_workers:" config/config.yaml | head -1 | awk '{print $2}')
QUERIES_PER_COMPANY=$(grep "queries_per_company:" config/config.yaml | awk '{print $2}')

echo "Workers:              $MAX_WORKERS"
echo "Search queries:       $QUERIES_PER_COMPANY per company"
echo "Network per company:  ~450 KB"
echo ""
echo "Monthly capacity estimates:"
echo "  10,000 companies:   ~4.5 GB network, ~20 hours"
echo "  15,000 companies:   ~6.8 GB network, ~30 hours"
echo "  20,000 companies:   ~9.0 GB network, ~50 hours (max safe)"
echo ""

################################################################################
# STEP 7: Launch Options
################################################################################

echo "================================================================================"
echo "Setup Complete! ✅"
echo "================================================================================"
echo ""
echo "What would you like to do?"
echo ""
echo "1) Test run with 5 companies (~5 minutes)"
echo "2) Small batch: 1,000 companies (~2 hours)"
echo "3) Medium batch: 10,000 companies (~20 hours)"
echo "4) Large batch: 15,000 companies (~30 hours)"
echo "5) Maximum batch: 20,000 companies (~50 hours) - RECOMMENDED MONTHLY"
echo "6) Custom number of companies"
echo "7) Exit (run manually later)"
echo ""

read -p "Enter choice [1-7]: " choice

case $choice in
    1)
        LIMIT=5
        echo ""
        echo "Starting TEST RUN with 5 companies..."
        python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS
        ;;
    2)
        LIMIT=1000
        echo ""
        echo "Starting small batch: 1,000 companies..."
        echo "This will run in foreground. Press Ctrl+C to stop."
        echo ""
        read -p "Press Enter to continue or Ctrl+C to cancel..."
        python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS
        ;;
    3)
        LIMIT=10000
        echo ""
        echo "Starting medium batch: 10,000 companies..."
        echo "Launching in screen session..."
        echo ""
        read -p "Press Enter to continue or Ctrl+C to cancel..."

        # Check if screen is installed
        if ! command -v screen &> /dev/null; then
            echo "Installing screen..."
            sudo apt install -y screen
        fi

        echo ""
        echo "Starting screen session 'funding-rounds'..."
        echo "The pipeline will run in background."
        echo ""
        echo "To check progress later:"
        echo "  screen -r funding-rounds"
        echo ""
        echo "To detach from screen:"
        echo "  Press Ctrl+A, then D"
        echo ""
        read -p "Press Enter to start..."

        screen -dmS funding-rounds bash -c "cd $(pwd) && source venv/bin/activate && python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS"

        echo ""
        echo -e "${GREEN}✓${NC} Pipeline started in screen session!"
        echo ""
        echo "Attaching to screen in 3 seconds..."
        sleep 3
        screen -r funding-rounds
        ;;
    4)
        LIMIT=15000
        echo ""
        echo "Starting large batch: 15,000 companies..."
        echo "Launching in screen session..."
        echo ""
        read -p "Press Enter to continue or Ctrl+C to cancel..."

        if ! command -v screen &> /dev/null; then
            echo "Installing screen..."
            sudo apt install -y screen
        fi

        echo ""
        echo "Starting screen session 'funding-rounds'..."
        screen -dmS funding-rounds bash -c "cd $(pwd) && source venv/bin/activate && python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS"

        echo ""
        echo -e "${GREEN}✓${NC} Pipeline started in screen session!"
        echo ""
        echo "To check progress:"
        echo "  screen -r funding-rounds"
        echo ""
        echo "Attaching to screen in 3 seconds..."
        sleep 3
        screen -r funding-rounds
        ;;
    5)
        LIMIT=20000
        echo ""
        echo "================================================================================"
        echo "MONTHLY MAXIMUM RUN: 20,000 companies"
        echo "================================================================================"
        echo ""
        echo "This will:"
        echo "  - Process up to 20,000 companies"
        echo "  - Use ~9 GB of your 10 GB monthly network quota"
        echo "  - Take approximately 40-60 hours (2-3 days)"
        echo "  - Run in a screen session (survives disconnect)"
        echo ""
        echo -e "${YELLOW}⚠${NC}  Make sure:"
        echo "  - This is the beginning of the month (quota reset)"
        echo "  - You've checked OCI network metrics (near 0 GB used)"
        echo "  - Your other program has enough resources"
        echo ""
        read -p "Continue with 20,000 companies? (y/N): " -n 1 -r
        echo

        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Cancelled."
            exit 0
        fi

        if ! command -v screen &> /dev/null; then
            echo "Installing screen..."
            sudo apt install -y screen
        fi

        echo ""
        echo "Starting MAXIMUM monthly run in screen session..."
        screen -dmS funding-rounds bash -c "cd $(pwd) && source venv/bin/activate && python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS"

        echo ""
        echo -e "${GREEN}✓${NC} Pipeline started!"
        echo ""
        echo "================================================================================"
        echo "Monthly Run Started Successfully"
        echo "================================================================================"
        echo ""
        echo "The pipeline is running in a screen session."
        echo ""
        echo "To check progress:"
        echo "  screen -r funding-rounds"
        echo ""
        echo "To detach from screen:"
        echo "  Press Ctrl+A, then D"
        echo ""
        echo "To check logs:"
        echo "  tail -f data/logs/v2_pipeline.log"
        echo ""
        echo "Expected completion: 2-3 days"
        echo ""
        echo "Attaching to screen in 5 seconds..."
        sleep 5
        screen -r funding-rounds
        ;;
    6)
        echo ""
        read -p "Enter number of companies to process: " LIMIT

        if ! [[ "$LIMIT" =~ ^[0-9]+$ ]]; then
            echo -e "${RED}Error: Please enter a valid number${NC}"
            exit 1
        fi

        NETWORK_GB=$(echo "scale=2; $LIMIT * 0.00045" | bc)

        echo ""
        echo "Custom run: $LIMIT companies"
        echo "Estimated network usage: ~${NETWORK_GB} GB"
        echo ""

        if (( $(echo "$NETWORK_GB > 9.5" | bc -l) )); then
            echo -e "${YELLOW}⚠  WARNING: This exceeds 9.5 GB and may incur charges!${NC}"
            read -p "Continue anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                echo "Cancelled."
                exit 0
            fi
        fi

        if (( LIMIT > 100 )); then
            echo "Running in screen session..."
            if ! command -v screen &> /dev/null; then
                sudo apt install -y screen
            fi
            screen -dmS funding-rounds bash -c "cd $(pwd) && source venv/bin/activate && python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS"
            echo ""
            echo -e "${GREEN}✓${NC} Pipeline started in screen session!"
            echo "To check: screen -r funding-rounds"
            sleep 3
            screen -r funding-rounds
        else
            echo "Running in foreground..."
            python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS
        fi
        ;;
    7)
        echo ""
        echo "Setup complete! To run manually:"
        echo ""
        echo "  cd /opt/funding-rounds/v2_parallel_db"
        echo "  source venv/bin/activate"
        echo "  python3 run_pipeline_v2.py --limit 20000 --workers $MAX_WORKERS"
        echo ""
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo "================================================================================"
echo "Done!"
echo "================================================================================"
