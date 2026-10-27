#!/usr/bin/env bash
# run.sh - Launch SentientOS dashboard
# Usage: bash run.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export PATH="$HOME/.local/bin:$PATH"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "=================================================="
echo "  Starting SentientOS Autonomous AI Dashboard..."
echo "  Open in Windows Browser: http://localhost:8501"
echo "=================================================="
echo ""

python3 -m streamlit run app.py --server.headless true
