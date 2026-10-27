#!/usr/bin/env bash
# test.sh - Run test suite for SentientOS
# Usage: bash test.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export PATH="$HOME/.local/bin:$PATH"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

python3 -m pytest tests/ -v
