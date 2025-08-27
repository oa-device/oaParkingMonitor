# oaParkingMonitor

YOLOv11-based intelligent parking space detection system optimized for Mac Mini M1. Part of the OrangeAd device ecosystem, providing real-time parking occupancy monitoring with vehicle classification capabilities.

## Features

- **YOLOv11m Detection Engine**: Optimized for Mac M1 with CoreML acceleration
- **Real-time Processing**: 30+ FPS parking space detection  
- **Vehicle Classification**: Car type and attribute detection
- **Display Integration**: Ad display with detection overlay
- **Health Monitoring**: Comprehensive service health tracking
- **API Service**: FastAPI endpoints for oaDashboard integration

## Requirements

### System Requirements
- macOS 12.0+ (Monterey or later for M1 support)
- Mac Mini M1/M2 or MacBook with Apple Silicon
- Minimum 8GB RAM (16GB recommended)
- Camera access permissions
- Python 3.12+

## Quick Start

### Installation

```bash
# Clone repository
git clone git@github.com:oa-device/oaParkingMonitor.git
cd oaParkingMonitor

# Install dependencies with uv
uv sync

# Run setup script
./scripts/setup.sh
```

### Configuration

```bash
# Copy configuration template
cp config/default.yaml config.yaml

# Edit configuration for your environment
vim config.yaml
```

### Running the Service

```bash
# Start parking monitor
./scripts/start.sh

# Check service health
curl http://localhost:9091/health
```

## API Endpoints

- `GET /health` - Service health check
- `GET /api/parking/status` - Current parking occupancy
- `GET /api/parking/metrics` - Performance metrics  
- `GET /api/parking/stream` - Real-time detection stream (WebSocket)

## Integration

### oaDashboard Integration
The service integrates with oaDashboard for:
- Real-time parking space monitoring
- Performance metrics collection
- Health status reporting
- Remote service management

### Deployment via oaAnsible
Automated deployment using the `macos/parking_monitor` Ansible role:

```bash
# Deploy to staging
ansible-playbook -i inventory/yuh/staging.yml playbooks/universal.yml -t parking-monitor

# Deploy to production
ansible-playbook -i inventory/yuh/prod.yml playbooks/universal.yml -t parking-monitor
```

## Architecture

```text
[Camera Input] → [YOLOv11m Engine] → [Parking Detection] → [Vehicle Classification]
                                                    ↓
[Display Manager] ← [API Server (9091)] ← [Performance Metrics]
```

## Development

### Running Tests
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src tests/
```

### Code Quality
```bash
# Format code
uv run black src/ tests/
uv run isort src/ tests/

# Lint code
uv run ruff check src/ tests/

# Type checking
uv run mypy src/
```

## Model Information

- **Base Model**: YOLOv11m (99% accuracy for parking detection)
- **Optimization**: CoreML export for Mac M1 acceleration
- **Performance**: 30+ FPS real-time processing
- **Memory Usage**: <4GB total application footprint

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Contributing

Please read our [contributing guidelines](docs/contributing.md) before submitting pull requests.

## Support

For support and questions:
- Create an issue in this repository
- Contact the OrangeAd development team
- Check the [troubleshooting guide](docs/troubleshooting.md)