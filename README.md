# oaParkingMonitor

Edge parking detection service with YOLOv11m vehicle detection and cloud pull architecture.

## Overview

Snapshot-based parking monitoring system for Mac Mini M1/M2 devices. Processes 1 frame every 5 seconds, stores detection data locally, and provides cloud pull endpoints for centralized analytics.

## Architecture

**Edge Device Role**: Data collection and storage only
**Cloud Role**: Data retrieval, aggregation, and analytics

```
[Camera] → [YOLOv11m Detection] → [SQLite Storage] → [Cloud Pull API]
   5sec      Vehicle Detection      Persistent Data    GET /detections
```

### Core Components
- **FastAPI Service**: Runs on port 9091
- **Detection Engine**: YOLOv11m with CoreML optimization  
- **Local Storage**: SQLite at `~/orangead/data/oaParkingMonitor/`
- **Cloud Integration**: Pull-based data synchronization

### Key Files
```
src/
├── main.py                 # FastAPI application
├── models/edge.py          # Data models
├── storage/edge_storage.py # SQLite persistence
└── services/parking_monitor.py # Detection orchestration

config/edge.yaml            # Device configuration
```

## Cloud Pull Endpoints

### Data Retrieval
```bash
# Get unuploaded detections (for cloud polling)
GET /detections?uploaded=false

# Get detections by timestamp range
GET /detections?start=1609459200000&end=1609462800000

# Get specific detections by ID
GET /detections?id=uuid1,uuid2,uuid3
```

### Upload Confirmation
```bash
# Mark detections as uploaded
POST /detections/confirm
{"ids": ["uuid1", "uuid2"]}
```

### Device Status
```bash
GET /health        # Service health
GET /snapshot      # Current parking state  
GET /config        # Device configuration
```

## Data Model

```json
{
  "id": "01234567-89ab-cdef-0123-456789abcdef",
  "ts": 1609459200000,
  "customerId": "customer-123",
  "siteId": "site-456", 
  "zoneId": "zone-789",
  "cameraId": "cam-001",
  "totalSpaces": 50,
  "occupiedSpaces": 32,
  "uploaded": false
}
```

## Installation

```bash
# Install dependencies
uv sync

# Run service
uvicorn src.main:app --host 0.0.0.0 --port 9091
```

## Configuration

**config/edge.yaml**:
```yaml
deployment:
  customerId: "customer-123"
  siteId: "site-456" 
  zoneId: "zone-789"
  cameraId: "cam-001"

device:
  snapshotInterval: 5      # seconds
  totalSpaces: 50
  modelPath: "models/yolo11m.pt"
```

## Performance

- **Processing**: <2 seconds per snapshot
- **Memory**: <4GB total footprint  
- **Capability**: 30+ FPS (throttled to 5-second intervals)
- **Storage**: Persistent SQLite with automatic cleanup