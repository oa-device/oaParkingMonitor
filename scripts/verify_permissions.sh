#!/bin/bash
# Permission Verification Script for oaParkingMonitor
# Checks if required macOS permissions are granted

echo "[VERIFY] Parking Monitor Permission Verification"
echo "==============================================="

# Check camera permissions
echo -n "Camera Access: "
if system_profiler SPCameraDataType 2>/dev/null | grep -q "Camera"; then
    echo "[OK] Camera detected"
else
    echo "[WARN] No camera detected or access denied"
fi

# Check Python process permissions (approximate)
echo -n "Python Process: "
if pgrep -f python >/dev/null; then
    echo "[OK] Python processes running"
else
    echo "[INFO] No Python processes currently running"
fi

# Check file permissions for parking monitor directory
echo -n "File Access: "
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ -r "$PROJECT_DIR" ] && [ -w "$PROJECT_DIR" ]; then
    echo "[OK] Read/write access to project directory"
else
    echo "[FAIL] Cannot access project directory: $PROJECT_DIR"
fi

# Check log file access
LOG_FILE="$PROJECT_DIR/logs/parking_monitor.log"
echo -n "Log File Access: "
if [ -f "$LOG_FILE" ]; then
    if [ -w "$LOG_FILE" ]; then
        echo "[OK] Log file writable"
    else
        echo "[WARN] Log file not writable"
    fi
else
    echo "[INFO] Log file not found (will be created on startup)"
fi

echo ""
echo "[VERIFY] Permission verification complete"
echo "If issues found, run: ./scripts/grant_permissions.sh"