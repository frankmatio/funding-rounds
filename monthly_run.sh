#!/bin/bash
################################################################################
# Monthly Run - Quick Launch Script
# For use AFTER initial setup is complete
################################################################################

set -e

echo "================================================================================"
echo "V2 Pipeline - Monthly Run"
echo "================================================================================"
echo ""

# Check if we're in the right directory
if [ ! -f "run_pipeline_v2.py" ]; then
    echo "❌ Error: Please run from /opt/funding-rounds/v2_parallel_db/"
    exit 1
fi

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Virtual environment not found!"
    echo "Please run setup_and_run.sh first."
    exit 1
fi

# Activate venv
source venv/bin/activate

# Get current config
MAX_WORKERS=$(grep "max_workers:" config/config.yaml | head -1 | awk '{print $2}')

echo "Quick options:"
echo ""
echo "1) Test run (5 companies) - ~5 minutes"
echo "2) Small batch (1,000 companies) - ~2 hours, ~450 MB"
echo "3) Medium batch (10,000 companies) - ~20 hours, ~4.5 GB"
echo "4) Large batch (15,000 companies) - ~30 hours, ~6.8 GB"
echo "5) MAXIMUM (20,000 companies) - ~50 hours, ~9 GB"
echo "6) Custom"
echo ""

read -p "Choice [1-6]: " choice

case $choice in
    1) LIMIT=5 ;;
    2) LIMIT=1000 ;;
    3) LIMIT=10000 ;;
    4) LIMIT=15000 ;;
    5) LIMIT=20000 ;;
    6)
        read -p "Number of companies: " LIMIT
        if ! [[ "$LIMIT" =~ ^[0-9]+$ ]]; then
            echo "Error: Invalid number"
            exit 1
        fi
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

NETWORK_GB=$(echo "scale=2; $LIMIT * 0.00045" | bc)

echo ""
echo "Will process: $LIMIT companies"
echo "Network usage: ~${NETWORK_GB} GB"
echo ""

if (( $(echo "$NETWORK_GB > 9.5" | bc -l) )); then
    echo "⚠️  WARNING: This exceeds 9.5 GB!"
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi

# For large runs, use screen
if (( LIMIT > 100 )); then
    echo "Launching in screen session..."
    echo ""

    # Check for existing screen session
    if screen -list | grep -q "funding-rounds"; then
        echo "⚠️  Screen session 'funding-rounds' already exists!"
        read -p "Kill it and start new? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            screen -S funding-rounds -X quit
            echo "Old session killed."
        else
            echo "Cancelled. Attach with: screen -r funding-rounds"
            exit 0
        fi
    fi

    # Start in screen
    screen -dmS funding-rounds bash -c "cd $(pwd) && source venv/bin/activate && python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS"

    echo "✓ Started in screen session!"
    echo ""
    echo "To check progress:"
    echo "  screen -r funding-rounds"
    echo ""
    echo "To detach: Ctrl+A, then D"
    echo ""
    echo "Attaching in 3 seconds..."
    sleep 3
    screen -r funding-rounds
else
    # Small run, foreground
    echo "Running in foreground..."
    echo ""
    python3 run_pipeline_v2.py --limit $LIMIT --workers $MAX_WORKERS
fi

echo ""
echo "✓ Done!"
