#!/bin/bash
# Start script for oaParkingMonitor service

set -e

# Default configuration
CONFIG_FILE="config.yaml"
PORT=""
LOG_LEVEL="INFO"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -p|--port)
            PORT="$2"
            shift 2
            ;;
        --log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -c, --config FILE    Configuration file (default: config.yaml)"
            echo "  -p, --port PORT      Port to run on (overrides config)"
            echo "  --log-level LEVEL    Log level (DEBUG, INFO, WARNING, ERROR)"
            echo "  -h, --help           Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "🚀 Starting oaParkingMonitor..."

# Check if configuration file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Configuration file not found: $CONFIG_FILE"
    echo "Run ./scripts/setup.sh first or copy config/default.yaml to config.yaml"
    exit 1
fi

# Check if virtual environment exists
if [ ! -f ".venv/bin/python" ]; then
    echo "❌ Virtual environment not found"
    echo "Run ./scripts/setup.sh first to initialize the project"
    exit 1
fi

# Verify model files exist
if [ ! -f "models/downloads/yolo11m.pt" ]; then
    echo "🧠 Downloading YOLOv11m model..."
    uv run python test_model.py
fi

echo "✅ Configuration: $CONFIG_FILE"
echo "✅ Log level: $LOG_LEVEL"

# Build command arguments
ARGS="--config $CONFIG_FILE --log-level $LOG_LEVEL"
if [ -n "$PORT" ]; then
    ARGS="$ARGS --port $PORT"
    echo "✅ Port: $PORT"
fi

echo "✅ Models ready"
echo ""

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the service
echo "🎯 Starting parking monitor service..."
echo "   API will be available at http://localhost:9091"
echo "   Health check: curl http://localhost:9091/health"
echo "   Documentation: http://localhost:9091/docs"
echo ""
echo "Press Ctrl+C to stop the service"
echo ""

# Run with uv
exec uv run python -m src.main $ARGS