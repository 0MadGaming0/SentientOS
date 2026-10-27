#!/usr/bin/env bash
# setup.sh - One-time setup for SentientOS
# Run once: bash setup.sh
# Then launch: bash run.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  SentientOS Setup"
echo "============================================"

# Install pip and venv if needed
if ! python3 -m pip --version &>/dev/null; then
    echo "[+] Installing python3-pip..."
    sudo apt-get install -y python3-pip python3-venv
fi

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "[+] Creating virtual environment..."
    python3 -m venv .venv || python3 -m venv --without-pip .venv
fi

# Activate and install
echo "[+] Installing requirements..."
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo ""
echo "============================================"
echo "  Setup complete!"
echo "  Launch with:  bash run.sh"
echo "  Or manually:  source .venv/bin/activate"
echo "                streamlit run app.py"
echo "============================================"
