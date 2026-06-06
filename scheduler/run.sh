#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Check Python version >= 3.9
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED="3.9"
if [ "$(printf '%s\n' "$REQUIRED" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED" ]; then
    echo "ERROR: Python >= $REQUIRED required, found $PYTHON_VERSION"
    exit 1
fi
echo "Python $PYTHON_VERSION detected"

# Install dependencies if needed
if ! python3 -c "import pyspark, apscheduler, numpy, pandas, yaml" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt --quiet
fi

# Run pipeline
echo "Running sustainment analytics pipeline..."
python3 scheduler/pipeline.py --run-once

# Print summary
echo ""
echo "=== Generated Reports ==="
if [ -d "reports/data" ]; then
    echo "CSV reports:"
    ls -lh reports/data/*.csv 2>/dev/null || echo "  (none)"
fi
if [ -d "reports/figures" ]; then
    echo "Figures:"
    ls -lh reports/figures/*.png 2>/dev/null || echo "  (none yet — run Phase 5)"
fi
echo ""
echo "Pipeline log: logs/pipeline.log"
