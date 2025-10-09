# oaParkingMonitor Workflow Diagram

## Overview

Edge-deployed parking space detection and monitoring service using YOLOv11m models optimized for vehicle detection with network optimization patterns and AWS cloud integration.

## ETL Workflow Architecture

```mermaid
%%{init: {
  'theme': 'base',
  'themeVariables': {
    'primaryColor': '#1f2937',
    'primaryTextColor': '#f8fafc',
    'primaryBorderColor': '#374151',
    'lineColor': '#6b7280',
    'sectionBkgColor': '#1e293b',
    'altSectionBkgColor': '#18181b',
    'gridColor': '#374151',
    'secondaryColor': '#3b82f6',
    'tertiaryColor': '#10b981',
    'background': '#111827',
    'textColor': '#f1f5f9',
    'edgeLabelBackground': '#374151',
    'clusterBkg': '#374151',
    'clusterBorder': '#6b7280',
    'titleColor': '#f8fafc'
  }
}}%%
flowchart TD
    %% Data Sources
    Camera[Camera Hardware\nBuilt-in Mac Mini Camera] --> FrameCapture
    FrameCapture[Frame Capture\nSnapshot Every 5s] --> Preprocessor

    %% Extraction Layer
    Preprocessor[Image Preprocessing\nResize + Enhancement] --> YOLOEngine
    YOLOEngine[YOLOv11m Detection\nMulti-scale Vehicle Detection] --> VehicleFilter

    %% Transformation Layer
    VehicleFilter[Vehicle Class Filter\nCars, Trucks, Buses] --> ZoneAnalyzer
    ZoneAnalyzer[Parking Zone Analysis\nPolygon Intersection] --> OccupancyEngine
    OccupancyEngine[Occupancy Engine\nTemporal Smoothing] --> ResultProcessor

    %% Loading Layer
    ResultProcessor[Result Processing\nJSON Serialization] --> EdgeStorage
    EdgeStorage[Edge Storage\nHierarchical Snapshots] --> UploadQueue
    UploadQueue[Upload Queue\nBatch Processing] --> AWSService

    %% Cloud Integration
    AWSService[AWS Upload Service\nS3 + API Gateway] --> CloudStorage
    CloudStorage[Cloud Storage\nS3 Buckets] --> CloudAPI
    CloudAPI[Cloud API\nData Retrieval] --> Confirmation
    Confirmation[Confirmation Handler\nReceipt Tracking] --> EdgeStorage

    %% API Layer
    EdgeStorage --> LocalAPI
    LocalAPI[Local FastAPI\nPort 9091] --> Clients

    %% Styling
    classDef source fill:#1f2937,stroke:#f8fafc,stroke-width:2px,color:#f8fafc
    classDef processing fill:#1e293b,stroke:#f1f5f9,stroke-width:2px,color:#f1f5f9
    classDef ml fill:#f59e0b,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef tracking fill:#3b82f6,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef api fill:#10b981,stroke:#1f2937,stroke-width:2px,color:#f8fafc
    classDef storage fill:#8b5cf6,stroke:#1f2937,stroke-width:2px,color:#f8fafc
    classDef network fill:#f59e0b,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef error fill:#ef4444,stroke:#1f2937,stroke-width:2px,color:#f8fafc

    class Camera,FrameCapture source
    class Preprocessor,YOLOEngine,VehicleFilter processing
    class ZoneAnalyzer,OccupancyEngine,ResultProcessor tracking
    class EdgeStorage,UploadQueue,AWSService,CloudStorage,CloudAPI,Confirmation storage
    class LocalAPI,Clients api
```

## Snapshot Processing Pipeline

```mermaid
stateDiagram-v2
    [*] --> Initialize
    Initialize --> LoadConfig: Load Zones Config
    LoadConfig --> InitCamera: Initialize Camera
    InitCamera --> WaitTimer: Wait for Timer

    state SnapshotCycle {
        [*] --> CaptureFrame
        CaptureFrame --> PreprocessImage: Enhance + Resize
        PreprocessImage --> RunDetection: YOLOv11m Inference
        RunDetection --> FilterVehicles: Keep Vehicle Classes
        FilterVehicles --> AnalyzeZones: Check Zone Occupancy
        AnalyzeZones --> ApplySmoothing: Temporal Filtering
        ApplySmoothing --> StoreResults: Edge Storage
        StoreResults --> QueueUpload: Batch Queue
        QueueUpload --> [*]
    }

    WaitTimer --> SnapshotCycle: Timer Trigger

    state UploadCycle {
        [*] --> CheckQueue
        CheckQueue --> PrepareBatch: Group Snapshots
        PrepareBatch --> CompressData: Gzip Compression
        CompressData --> UploadToAWS: S3 + API Gateway
        UploadToAWS --> HandleResponse: Process Response
        HandleResponse --> ConfirmUpload: Mark Confirmed
        ConfirmUpload --> [*]
    }

    SnapshotCycle --> UploadCycle: Batch Ready
    UploadCycle --> SnapshotCycle: Upload Complete

    SnapshotCycle --> APIRequest: API Call
    APIRequest --> ProcessAPI: Handle Request
    ProcessAPI --> ReturnResponse: JSON + Images
    ReturnResponse --> SnapshotCycle

    state ErrorHandling {
        [*] --> DetectError
        DetectError --> LogError: Log + Alert
        LogError --> RetryOperation: Retry with Backoff
        RetryOperation --> FallbackMode: Degrade Gracefully
        FallbackMode --> [*]
    }

    SnapshotCycle --> ErrorHandling: Error Detected
    ErrorHandling --> SnapshotCycle: Recovery Complete

    SnapshotCycle --> Shutdown: Service Stop
    Shutdown --> [*]
```

## Network Optimization Patterns

```mermaid
flowchart TD
    subgraph Optimization [Network Optimization Layer]
        Compression[Data Compression\nGzip Level 6] --> Caching
        Caching[HTTP Caching\nETag Support] --> Delta
        Delta[Delta Updates\nChange Detection] --> Quality
        Quality[Quality Control\nImage Compression] --> Throttling
        Throttling[Request Throttling\nRate Limiting] --> OptimizationEnd
    end

    subgraph Bandwidth [Bandwidth Efficiency]
        JSONComp[JSON Compression\n60-70% Reduction] --> DeltaUpdates
        DeltaUpdates[Delta Updates\n85-99% Savings] --> ImageQuality
        ImageQuality[Image Quality Control\n85% Savings at Q=10] --> CacheHit
        CacheHit[Cache Hit Rate\n5-10x Faster] --> ResponseTime
        ResponseTime[Response Time\n<100ms Cached]
    end

    subgraph API [Optimized API Endpoints]
        Detection[GET /detection\nCurrent State] --> Changes
        Changes[GET /detection/changes?since=X\nDelta Updates] --> History
        History[GET /detections\nBatch Retrieval] --> Snapshot
        Snapshot[GET /snapshot?quality=50\nCompressed Image] --> Frame
        Frame[GET /frame?quality=75\nRaw Frame] --> Status
        Status[GET /upload/status\nUpload Statistics]
    end

    Optimization --> Bandwidth
    Bandwidth --> API

    classDef opt fill:#10b981,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef bw fill:#3b82f6,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef endpoint fill:#f59e0b,stroke:#1f2937,stroke-width:2px,color:#1f2937

    class Compression,Caching,Delta,Quality,Throttling,OptimizationEnd opt
    class JSONComp,DeltaUpdates,ImageQuality,CacheHit,ResponseTime bw
    class Detection,Changes,History,Snapshot,Frame,Status endpoint
```

## AWS Integration Architecture

```mermaid
flowchart TD
    subgraph EdgeDevice [Edge Device Mac Mini]
        Service[oaParkingMonitor\nPort 9091] --> UploadService
        UploadService[Upload Service\nBatch Processing] --> LocalQueue
        LocalQueue[Local Queue\nRetry Logic] --> NetworkLayer
        NetworkLayer[Network Layer\nTailscale VPN] --> AWS
    end

    subgraph AWS [AWS Cloud Infrastructure]
        APIGateway[API Gateway\nREST API] --> Lambda
        Lambda[Lambda Functions\nData Processing] --> S3
        S3[S3 Buckets\nSnapshot Storage] --> DynamoDB
        DynamoDB[DynamoDB\nMetadata Store] --> CloudFront
        CloudFront[CloudFront CDN\nGlobal Distribution] --> WebApp
    end

    subgraph DataFlow [Data Flow Patterns]
        Upload[AWS Upload\nBatch Every 60s] --> Confirmation
        Confirmation[Upload Confirmation\nReceipt Tracking] --> Sync
        Sync[Data Synchronization\nDelta Updates] --> Analytics
        Analytics[Analytics Engine\nHistorical Analysis] --> Reports
        Reports[Reports & Insights\nBusiness Intelligence]
    end

    subgraph Monitoring [Monitoring & Alerting]
        CloudWatch[CloudWatch\nMetrics & Logs] --> Alarms
        Alarms[CloudWatch Alarms\nAlert System] --> Notifications
        Notifications[SNS Notifications\nEmail/SMS] --> Ops
        Ops[Operations Team\nIssue Resolution]
    end

    EdgeDevice --> AWS
    AWS --> DataFlow
    AWS --> Monitoring

    classDef edge fill:#1f2937,stroke:#f8fafc,stroke-width:2px,color:#f8fafc
    classDef cloud fill:#10b981,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef data fill:#3b82f6,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef monitor fill:#f59e0b,stroke:#1f2937,stroke-width:2px,color:#1f2937

    class Service,UploadService,LocalQueue,NetworkLayer edge
    class APIGateway,Lambda,S3,DynamoDB,CloudFront,WebApp cloud
    class Upload,Confirmation,Sync,Analytics,Reports data
    class CloudWatch,Alarms,Notifications,Ops monitor
```

## Zone Analysis Workflow

```mermaid
flowchart TD
    subgraph ZoneConfig [Zone Configuration]
        ConfigFile[config/mvp.yaml] --> ZoneParser
        ZoneParser[Zone Parser\nPydantic Validation] --> ZoneRegistry
        ZoneRegistry[Zone Registry\nRuntime Storage] --> ZoneA
        ZoneRegistry --> ZoneB
        ZoneA[A1-A7\nFront Row - Easy] --> Analyzer
        ZoneB[B1-B5\nBack Row - Hard] --> Analyzer
    end

    subgraph Detection [Vehicle Detection]
        YOLO[YOLOv11m Engine] --> VehicleDetections
        VehicleDetections[Vehicle Detections\nbbox + confidence] --> Filter
        Filter[Confidence Filter\n> 0.5 threshold] --> ValidDetections
        ValidDetections[Valid Detections\nHigh Confidence] --> Analyzer
    end

    subgraph Analysis [Zone Analysis Engine]
        Analyzer[Zone Analyzer\nPolygon Intersection] --> OccupancyCheck
        OccupancyCheck[Occupancy Check\nPoint-in-Polygon] --> TemporalFilter
        TemporalFilter[Temporal Smoothing\nMulti-frame Validation] --> OccupancyResult
        OccupancyResult[Occupancy Result\noccupied + confidence] --> StatusUpdate
        StatusUpdate[Status Update\nZone State Change] --> History
        History[History Tracker\nChange Detection] --> API
    end

    ZoneConfig --> Detection
    Detection --> Analysis

    classDef config fill:#1e293b,stroke:#f1f5f9,stroke-width:2px,color:#f1f5f9
    classDef detection fill:#f59e0b,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef analysis fill:#3b82f6,stroke:#1f2937,stroke-width:2px,color:#1f2937

    class ConfigFile,ZoneParser,ZoneRegistry,ZoneA,ZoneB config
    class YOLO,VehicleDetections,Filter,ValidDetections detection
    class Analyzer,OccupancyCheck,TemporalFilter,OccupancyResult,StatusUpdate,History,API analysis
```

## Edge Storage Architecture

```mermaid
flowchart TD
    subgraph FileSystem [File System Structure]
        Root["Root Directory\n/orangead/oaParkingMonitor"] --> Snapshots
        Root --> Logs
        Root --> Config
        Root --> Models

        Snapshots["Snapshots Directory\n/snapshots"] --> ByDate["Date Structure\nYYYY-MM-DD/"]
        ByDate --> ByTime["Time Structure\nHH:MM:SS/"]
        ByTime --> Original["Original Image\noriginal.jpg"]
        ByTime --> Processed["Processed Image\nprocessed.jpg"]
        ByTime --> Metadata["Metadata File\nmetadata.json"]
        ByTime --> Thumbnail["Thumbnail Image\nthumbnail.jpg"]
    end

    subgraph StorageLayers [Storage Layer Architecture]
        MemoryLayer[Memory Layer\nRecent Data] --> CacheLayer
        CacheLayer[Cache Layer\nFrequent Access] --> DiskLayer
        DiskLayer[Disk Layer\nPersistent Storage] --> CloudLayer
        CloudLayer[Cloud Layer\nAWS S3 Backup]
    end

    subgraph DataManagement [Data Management]
        Retention[Retention Policy\n30 Days Local] --> Compression
        Compression[Compression\nAutomatic Gzip] --> Cleanup
        Cleanup[Cleanup Service\nOld File Removal] --> Sync
        Sync[Sync Service\nCloud Upload] --> Confirmation
        Confirmation[Upload Confirmation\nDelete Local]
    end

    FileSystem --> StorageLayers
    StorageLayers --> DataManagement

    classDef fs fill:#1f2937,stroke:#f8fafc,stroke-width:2px,color:#f8fafc
    classDef storage fill:#10b981,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef mgmt fill:#f59e0b,stroke:#1f2937,stroke-width:2px,color:#1f2937

    class Root,Snapshots,ByDate,ByTime,Original,Processed,Metadata,Thumbnail fs
    class MemoryLayer,CacheLayer,DiskLayer,CloudLayer storage
    class Retention,Compression,Cleanup,Sync,Confirmation mgmt
```

## API Request Flow

```mermaid
sequenceDiagram
    participant Client as Client Application
    participant API as FastAPI Server
    participant Middleware as Middleware Layer
    participant Cache as Response Cache
    participant Storage as Edge Storage
    participant Detector as Detection Engine
    participant Uploader as Upload Service

    Note over Client,Uploader: Detection State Request
    Client->>API: GET /detection
    API->>Middleware: Request Processing
    Middleware->>Cache: Check Cache (ETag)
    alt Cache Hit
        Cache->>Middleware: 304 Not Modified
        Middleware->>API: Cached Response
    else Cache Miss
        Middleware->>Storage: Get Latest Detection
        Storage->>Detector: Trigger Detection if Needed
        Detector->>Storage: Store Results
        Storage->>Middleware: Detection Data
        Middleware->>Cache: Store Response with ETag
    end
    API->>Client: JSON Response + ETag Header

    Note over Client,Uploader: Delta Update Request
    Client->>API: GET /detection/changes?since=1234567890
    API->>Storage: Get Changes Since Timestamp
    Storage->>API: Delta Data (85-99% smaller)
    API->>Client: JSON Delta Response

    Note over Client,Uploader: Snapshot Request
    Client->>API: GET /snapshot?quality=50
    API->>Storage: Get Processed Image
    API->>API: Compress to Quality 50
    API->>Client: Compressed JPEG (85% smaller)

    Note over Client,Uploader: Upload Status Request
    Client->>API: GET /upload/status
    API->>Uploader: Get Upload Statistics
    Uploader->>API: Status Data
    API->>Client: Upload Status JSON

    Note over Client,Uploader: Background Upload Process
    loop Every 60 Seconds
        Detector->>Storage: New Detection Results
        Storage->>Uploader: Queue for Upload
        Uploader->>Uploader: Batch Processing
        Uploader->>+AWS: Upload to S3 + API Gateway
        AWS-->>-Uploader: Upload Confirmation
        Uploader->>Storage: Mark as Uploaded
    end
```

## Performance Optimization Flow

```mermaid
flowchart TD
    subgraph InputOptimization [Input Optimization]
        Interval[Snapshot Interval\n5 seconds] --> Resolution
        Resolution[Resolution Control\n1280x720 Optimal] --> Preprocessing
        Preprocessing[Smart Preprocessing\nROI Detection] --> ModelOpt
    end

    subgraph ModelOptimization [Model Optimization]
        ModelOpt[YOLOv11m CoreML\nM1/M2 Accelerated] --> MultiScale
        MultiScale[Multi-scale Detection\nAccuracy vs Speed] --> Confidence
        Confidence[Confidence Threshold\nQuality Filter] --> BatchSize
        BatchSize[Batch Processing\nEfficient Inference] --> Memory
    end

    subgraph ResourceManagement [Resource Management]
        Memory[Memory Management\n<4GB Footprint] --> CPU
        CPU[CPU Optimization\n<50% Usage] --> Threading
        Threading[Async Threading\nNon-blocking IO] --> Queue
        Queue[Queue Management\nBackpressure Control] --> Throughput
    end

    subgraph NetworkOptimization [Network Optimization]
        Throughput[Throughput Control\nBandwidth Limit] --> Compression
        Compression[Smart Compression\nAdaptive Quality] --> Caching
        Caching[Intelligent Caching\nPredictive Prefetch] --> Latency
        Latency[Latency Reduction\n<100ms Response] --> UX
    end

    InputOptimization --> ModelOptimization
    ModelOptimization --> ResourceManagement
    ResourceManagement --> NetworkOptimization

    classDef input fill:#10b981,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef model fill:#3b82f6,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef resource fill:#f59e0b,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef network fill:#1e293b,stroke:#f1f5f9,stroke-width:2px,color:#f1f5f9

    class Interval,Resolution,Preprocessing,ModelOpt input
    class MultiScale,Confidence,BatchSize,Memory model
    class CPU,Threading,Queue,Throughput resource
    class Compression,Caching,Latency,UX network
```

## Error Handling and Recovery

```mermaid
stateDiagram-v2
    [*] --> Healthy
    Healthy --> CameraError: Camera Failure
    Healthy --> NetworkError: Network Issue
    Healthy --> ModelError: Model Load Fail
    Healthy --> StorageError: Disk Full
    Healthy --> UploadError: AWS Upload Fail
    Healthy --> QueueError: Queue Processing Fail

    CameraError --> RetryCamera: Retry Connection
    RetryCamera --> Healthy: Camera OK
    RetryCamera --> DegradeMode: Max Retries

    NetworkError --> RetryNetwork: Reconnect Network
    RetryNetwork --> Healthy: Network OK
    RetryNetwork --> OfflineMode: Persistent Fail

    ModelError --> ReloadModel: Reload Model
    ReloadModel --> Healthy: Model OK
    ReloadModel --> FallbackModel: Use Default Model

    StorageError --> CleanupStorage: Clean Old Files
    CleanupStorage --> Healthy: Space OK
    CleanupStorage --> ReadOnlyMode: Still Full

    UploadError --> QueueUpload: Queue for Later
    QueueUpload --> Healthy: Upload OK
    QueueError --> BatchUpload: Batch Retry
    BatchUpload --> Healthy: Batch OK

    DegradeMode --> Healthy: Issue Resolved
    OfflineMode --> Healthy: Network Restored
    FallbackModel --> Healthy: Custom Model OK
    ReadOnlyMode --> Healthy: Space Available
    BatchUpload --> Healthy: Upload OK

    Healthy --> [*]: Service Shutdown
    DegradeMode --> [*]: Service Shutdown
    OfflineMode --> [*]: Service Shutdown
    FallbackModel --> [*]: Service Shutdown
    ReadOnlyMode --> [*]: Service Shutdown
    BatchUpload --> [*]: Service Shutdown
```

## Monitoring and Metrics

```mermaid
flowchart TD
    subgraph SystemMetrics [System Performance Metrics]
        CPU[CPU Usage\n< 50% target] --> Memory
        Memory[Memory Usage\n< 4GB limit] --> Disk
        Disk[Disk Usage\n30 day retention] --> Network
        Network[Network Bandwidth\nOptimized transfers] --> Uptime
        Uptime[Service Uptime\n99.9% target]
    end

    subgraph DetectionMetrics [Detection Performance Metrics]
        FPS[Processing FPS\n2+ snapshots/min] --> Accuracy
        Accuracy[Detection Accuracy\n> 95% target] --> Latency
        Latency[Detection Latency\n< 2 seconds] --> ModelLoad
        ModelLoad[Model Load Time\n< 10 seconds] --> ZoneCount
        ZoneCount[Zone Processing\n12 zones total]
    end

    subgraph BusinessMetrics [Business Intelligence Metrics]
        Occupancy[Occupancy Rate\nReal-time %] --> Trends
        Trends[Parking Trends\nHourly/Daily] --> Revenue
        Revenue[Revenue Impact\nParking optimization] --> Alerts
        Alerts[Alert System\nAnomaly detection] --> Reports
        Reports[Automated Reports\nDaily/Weekly/Monthly]
    end

    subgraph CloudMetrics [Cloud Integration Metrics]
        UploadSuccess[Upload Success Rate\n> 99% target] --> UploadLatency
        UploadLatency[Upload Latency\n< 30 seconds] --> DataTransfer
        DataTransfer[Data Transfer\nGB per day] --> Cost
        Cost[Cloud Cost\nOptimization] --> SLA
        SLA[SLA Compliance\nService levels]
    end

    SystemMetrics --> DetectionMetrics
    DetectionMetrics --> BusinessMetrics
    BusinessMetrics --> CloudMetrics

    classDef system fill:#1f2937,stroke:#f8fafc,stroke-width:2px,color:#f8fafc
    classDef detection fill:#f59e0b,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef business fill:#3b82f6,stroke:#1f2937,stroke-width:2px,color:#1f2937
    classDef cloud fill:#10b981,stroke:#1f2937,stroke-width:2px,color:#1f2937

    class CPU,Memory,Disk,Network,Uptime system
    class FPS,Accuracy,Latency,ModelLoad,ZoneCount detection
    class Occupancy,Trends,Revenue,Alerts,Reports business
    class UploadSuccess,UploadLatency,DataTransfer,Cost,SLA cloud
```