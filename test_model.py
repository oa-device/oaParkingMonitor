#!/usr/bin/env python3
"""Test script to download and benchmark YOLOv11m model."""

import time
import sys
import logging
from pathlib import Path
import platform

import torch
import cv2
import numpy as np
from ultralytics import YOLO

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_system_info():
    """Display system information."""
    logger.info("System Information:")
    logger.info(f"  Platform: {platform.platform()}")
    logger.info(f"  Python: {sys.version}")
    logger.info(f"  PyTorch: {torch.__version__}")
    
    # Check for MPS (Metal Performance Shaders) support
    if torch.backends.mps.is_available():
        logger.info("  MPS (Metal) acceleration: Available ✓")
        mps_device = torch.device("mps")
        logger.info(f"  MPS device: {mps_device}")
    else:
        logger.info("  MPS (Metal) acceleration: Not available ✗")
    
    # Check GPU
    if torch.cuda.is_available():
        logger.info(f"  CUDA GPUs: {torch.cuda.device_count()}")
    else:
        logger.info("  CUDA: Not available")
    
    logger.info("")


def download_yolo_model():
    """Download YOLOv11m model if not exists."""
    model_dir = Path("models/downloads")
    model_dir.mkdir(parents=True, exist_ok=True)
    
    model_path = model_dir / "yolo11m.pt"
    
    if model_path.exists():
        logger.info(f"Model already exists: {model_path}")
        return str(model_path)
    
    logger.info("Downloading YOLOv11m model...")
    
    # This will download the model automatically
    model = YOLO("yolo11m.pt")
    
    # Move to our models directory
    import shutil
    source = Path("yolo11m.pt")
    if source.exists():
        shutil.move(str(source), str(model_path))
        logger.info(f"Model saved to: {model_path}")
    
    return str(model_path)


def test_model_loading(model_path: str):
    """Test model loading and basic functionality."""
    logger.info("Testing model loading...")
    
    try:
        model = YOLO(model_path)
        logger.info("✓ Model loaded successfully")
        logger.info(f"  Model classes: {len(model.names)} classes")
        logger.info(f"  Model type: {type(model.model)}")
        return model
    except Exception as e:
        logger.error(f"✗ Failed to load model: {e}")
        return None


def test_coreml_export(model, model_path: str):
    """Test CoreML export for M1 optimization."""
    logger.info("Testing CoreML export...")
    
    export_dir = Path("models/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    
    coreml_path = export_dir / "yolo11m_parking.coreml"
    
    if coreml_path.exists():
        logger.info(f"CoreML model already exists: {coreml_path}")
        return str(coreml_path)
    
    try:
        # Export to CoreML
        logger.info("Exporting to CoreML (this may take a few minutes)...")
        exported_model = model.export(format="coreml")
        
        # Move to exports directory
        import shutil
        source_path = Path(exported_model)
        if source_path.exists():
            shutil.move(str(source_path), str(coreml_path))
        
        logger.info(f"✓ CoreML export successful: {coreml_path}")
        return str(coreml_path)
        
    except Exception as e:
        logger.error(f"✗ CoreML export failed: {e}")
        return None


def benchmark_inference(model, device="cpu", num_frames=10):
    """Benchmark model inference performance."""
    logger.info(f"Benchmarking inference on {device}...")
    
    # Create dummy frames for testing
    test_frames = [
        np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        for _ in range(num_frames)
    ]
    
    inference_times = []
    
    # Warmup
    logger.info("Warming up model...")
    for i in range(3):
        _ = model(test_frames[0], device=device, verbose=False)
    
    logger.info("Running benchmark...")
    for i, frame in enumerate(test_frames):
        start_time = time.time()
        
        results = model(frame, device=device, verbose=False)
        
        inference_time = time.time() - start_time
        inference_times.append(inference_time)
        
        # Count detections
        detections = 0
        for result in results:
            if result.boxes is not None:
                detections = len(result.boxes)
        
        logger.info(f"  Frame {i+1}/{num_frames}: {inference_time*1000:.1f}ms, {detections} detections")
    
    # Calculate statistics
    avg_time = np.mean(inference_times)
    min_time = np.min(inference_times)
    max_time = np.max(inference_times)
    fps = 1.0 / avg_time if avg_time > 0 else 0
    
    logger.info("")
    logger.info(f"Benchmark Results ({device}):")
    logger.info(f"  Average inference time: {avg_time*1000:.1f}ms")
    logger.info(f"  Min/Max inference time: {min_time*1000:.1f}ms / {max_time*1000:.1f}ms")
    logger.info(f"  Estimated FPS: {fps:.1f}")
    logger.info("")
    
    return {
        "device": device,
        "avg_time_ms": avg_time * 1000,
        "min_time_ms": min_time * 1000,
        "max_time_ms": max_time * 1000,
        "fps": fps
    }


def main():
    """Main test function."""
    logger.info("=== YOLOv11m Performance Test for oaParkingMonitor ===")
    logger.info("")
    
    # Test system info
    test_system_info()
    
    # Download model
    try:
        model_path = download_yolo_model()
    except Exception as e:
        logger.error(f"Failed to download model: {e}")
        return 1
    
    # Test model loading
    model = test_model_loading(model_path)
    if not model:
        return 1
    
    # Test CoreML export (for M1 optimization)
    coreml_path = test_coreml_export(model, model_path)
    
    # Benchmark performance
    results = {}
    
    # Test CPU performance
    results["cpu"] = benchmark_inference(model, device="cpu", num_frames=5)
    
    # Test MPS performance (if available)
    if torch.backends.mps.is_available():
        results["mps"] = benchmark_inference(model, device="mps", num_frames=5)
    
    # Summary
    logger.info("=== Performance Summary ===")
    for device, metrics in results.items():
        logger.info(f"{device.upper()}: {metrics['fps']:.1f} FPS ({metrics['avg_time_ms']:.1f}ms avg)")
    
    # Recommendations
    logger.info("")
    logger.info("=== Recommendations ===")
    
    if "mps" in results and results["mps"]["fps"] > results["cpu"]["fps"]:
        speedup = results["mps"]["fps"] / results["cpu"]["fps"]
        logger.info(f"✓ Use MPS acceleration: {speedup:.1f}x faster than CPU")
    else:
        logger.info("? MPS not available or not faster - use CPU")
    
    target_fps = 30
    best_fps = max(r["fps"] for r in results.values())
    
    if best_fps >= target_fps:
        logger.info(f"✓ Target FPS ({target_fps}) achievable: {best_fps:.1f} FPS")
    else:
        logger.info(f"⚠ Target FPS ({target_fps}) may not be achievable: {best_fps:.1f} FPS")
        logger.info("  Consider using YOLOv11n for better performance")
    
    if coreml_path:
        logger.info("✓ CoreML export successful - use for production deployment")
    else:
        logger.info("✗ CoreML export failed - use PyTorch model")
    
    logger.info("")
    logger.info("Test completed successfully! 🚀")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())