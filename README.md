# oaParkingMonitor

Edge-deployed parking space detection and monitoring service using YOLOv11m models optimized for vehicle detection.

## Overview

**oaParkingMonitor** is a specialized parking detection service designed for edge deployment on Mac Mini devices. It provides real-time vehicle detection, parking space monitoring, and cloud integration for parking analytics.

### Key Features

- **Real-time Detection**: YOLOv11m model with CoreML optimization for M1/M2 processors
- **Snapshot Architecture**: 5-second interval processing for optimal performance
- **Network Optimized**: Compression, caching, and delta updates for bandwidth efficiency
- **Cloud Integration**: AWS batch upload with retry logic and confirmation tracking
- **Edge Optimized**: <4GB memory footprint, minimal CPU impact on detection

## Architecture

### Core Components

- **Detector**: MVPParkingDetector with temporal smoothing and multi-scale detection
- **API Service**: FastAPI with network optimizations and comprehensive endpoints
- **Storage**: Edge storage with hierarchical snapshot organization
- **Upload Service**: AWS integration with batch processing and retry logic

### API Endpoints

**Core Operations:**
- `GET /health` - Service health check with upload status
- `GET /detection` - Current parking state (real-time snapshot)
- `GET /detections` - Historical detection batch retrieval
- `GET /config` - System configuration
- `POST /config` - Configuration updates

**Debug & Monitoring:**
- `GET /snapshot` - Processed image with detection overlays
- `GET /frame` - Raw camera frame
- `GET /camera/status` - Camera hardware status
- `GET /upload/status` - AWS upload service statistics

**Network Optimizations:**
- `GET /detection/changes?since=<epoch>` - Delta updates for bandwidth efficiency
- Quality parameters: `?quality=10-100` for image endpoints
- Automatic gzip compression for JSON responses
- HTTP caching with ETag support

## Deployment

### Requirements

- **Hardware**: Mac Mini M1/M2 with camera
- **OS**: macOS with launchd service management
- **Python**: 3.12+ with uv package manager
- **Network**: Tailscale connectivity for remote management

### Installation

Deployed via oaAnsible automation:

```bash
# From oaAnsible directory
./scripts/run projects/yhu/preprod -t parking-monitor
```

### Configuration

- **Environment**: Configure via `.env` file
- **Zones**: Define parking spaces in `config/mvp.yaml`
- **Camera**: Auto-detected hardware camera (source: "0")
- **AWS**: Configure upload credentials for cloud integration

## Performance

### Detection Performance

- **Processing**: <2 seconds per snapshot
- **Interval**: 5-second snapshots (configurable)
- **Accuracy**: Multi-scale detection with temporal smoothing
- **Memory**: <4GB total footprint

### Network Efficiency

- **Compression**: 60-70% payload reduction for JSON responses
- **Delta Updates**: 85-99% bandwidth savings for frequent polling
- **Image Quality**: Configurable 10-100 quality for bandwidth optimization
- **Caching**: 5-10x faster response times for repeated requests

## Monitoring

### Service Health

```bash
# Check service status
launchctl list com.orangead.parking-monitor

# View logs
tail -f /tmp/oaParkingMonitor.{out,err}

# API health check
curl http://localhost:9091/health
```

### Performance Metrics

```bash
# Detection statistics
curl http://localhost:9091/detection

# Upload service status
curl http://localhost:9091/upload/status

# Camera hardware status
curl http://localhost:9091/camera/status
```

## Directory Structure

```
oaParkingMonitor/
├── src/                     # Source code
│   ├── api/                 # API models and types
│   ├── config/              # Configuration management
│   ├── detector.py          # Core detection engine
│   ├── main.py              # FastAPI application
│   ├── middleware/          # HTTP middleware (compression, caching)
│   ├── models/              # Data models
│   ├── services/            # Business logic services
│   ├── tracking/            # Change tracking and analytics
│   └── utils/               # Utilities and helpers
├── config/                  # Configuration files
│   └── mvp.yaml            # Parking zone definitions
├── templates/               # HTML templates for dashboard
├── .env                     # Environment configuration
└── pyproject.toml          # Python dependencies
```

## Development

### Local Testing

```bash
# Install dependencies
uv sync

# Run service
uv run python -m src.main

# Test endpoints
curl http://localhost:9091/health
curl http://localhost:9091/detection
```

### Edge Deployment Testing

```bash
# Transfer updates to device
scp -r src/ admin@device:~/orangead/oaParkingMonitor/

# Restart service
ssh admin@device "launchctl unload ~/Library/LaunchAgents/com.orangead.parking-monitor.plist"
ssh admin@device "launchctl load ~/Library/LaunchAgents/com.orangead.parking-monitor.plist"

# Validate
ssh admin@device "curl http://localhost:9091/health"
```

## Network Optimization Features

### Compression
- Automatic gzip compression for JSON responses >512 bytes
- 60-70% bandwidth reduction for typical API responses
- Edge-optimized compression level 6 for CPU efficiency

### Quality Control
- Image quality parameters: `?quality=10-100`
- Bandwidth savings: 85% at quality=10, 30% at quality=75
- Backward compatible (default quality=95)

### Delta Updates
- `/detection/changes?since=<timestamp>` for incremental updates
- 85-99% bandwidth reduction for frequent polling clients
- 10-minute rolling change history

### Caching
- HTTP caching with ETag support for conditional requests
- 304 Not Modified responses for unchanged data
- 5-10x faster response times for cached endpoints

## Integration

### Cloud Architecture
- **Edge Push**: Automatic batch uploads every 60 seconds
- **Cloud Pull**: Historical data retrieval via `/detections` endpoint
- **Confirmation**: Cloud confirms receipt via `/detections/confirm`
- **Retry Logic**: Exponential backoff for failed uploads

### Monitoring Integration
- Real-time WebSocket updates (planned)
- Prometheus metrics export (planned)
- Alert integration via health endpoints

## License

Licensed under the terms specified in LICENSE file.