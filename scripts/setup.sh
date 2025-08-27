#!/bin/bash
# Setup script for oaParkingMonitor

set -e

echo "🚀 Setting up oaParkingMonitor..."

# Check if we're on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ This script is designed for macOS only"
    exit 1
fi

# Check Python version
python_version=$(python3 --version | cut -d' ' -f2)
required_version="3.12.0"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.12+ required. Found: $python_version"
    exit 1
fi

echo "✅ Python version: $python_version"

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "📦 Installing uv package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.cargo/env
else
    echo "✅ uv already installed: $(uv --version)"
fi

# Install dependencies
echo "📦 Installing Python dependencies..."
uv sync

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p logs
mkdir -p models/{downloads,exports,custom}
mkdir -p assets/{sample_images,overlay_templates,logos}

# Copy configuration template
if [ ! -f "config.yaml" ]; then
    echo "⚙️ Creating configuration file..."
    cp config/default.yaml config.yaml
    echo "✅ Configuration created at config.yaml"
    echo "📝 Please edit config.yaml to match your environment"
else
    echo "✅ Configuration file already exists"
fi

# Test model download and performance
echo "🧠 Testing YOLOv11m model download and performance..."
uv run python test_model.py

# Create logs directory with proper permissions
chmod 755 logs

echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Edit config.yaml to configure camera and parking zones"
echo "2. Run: ./scripts/start.sh"
echo "3. Check service health: curl http://localhost:9091/health"
echo ""
echo "For more information, see README.md"