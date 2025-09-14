#!/bin/bash
# Python Environment Activation Script for oaParkingMonitor
# Activates UV environment and sets up development environment

echo "Activating parking monitor uv environment..."
cd "$(dirname "$0")/.."

# Add uv to PATH (installed in ~/.local/bin)
export PATH="$HOME/.local/bin:$PATH"
export PYTHONPATH="$(pwd)/src:$PYTHONPATH"

echo "[OK] uv Environment activated - ready for parking monitor development"
echo "Use 'uv run python' to execute Python with the project environment"
echo "Current directory: $(pwd)"
echo "Python path: $PYTHONPATH"