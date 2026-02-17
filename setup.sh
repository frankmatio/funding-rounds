#!/bin/bash
# V2 Setup Script

echo "========================================="
echo "Funding Round Collection Engine V2 Setup"
echo "========================================="
echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p data/logs
mkdir -p data/exports
mkdir -p logs

echo "✓ Directories created"
echo ""

# Install dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

echo "✓ Dependencies installed"
echo ""

# Initialize database
echo "Initializing database..."
python3 scripts/init_db.py

echo ""
echo "========================================="
echo "✓ Setup complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Ensure .env file exists in parent directory with API keys"
echo "  2. Review config/config.yaml for settings"
echo "  3. Run pipeline: python3 run_pipeline_v2.py"
echo ""
