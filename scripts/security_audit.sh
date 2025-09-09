#!/bin/bash
# Security Audit Script for oaParkingMonitor  
# Audits security configuration and file permissions

echo "[AUDIT] Parking Monitor Security Audit"
echo "======================================"

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[FILES] File Permissions:"
# Check critical files
if [ -f "$PROJECT_DIR/.env" ]; then
    ls -la "$PROJECT_DIR/.env" 2>/dev/null || echo "Error reading .env file"
else
    echo "[WARN] .env file not found"
fi

echo ""
echo "Configuration directories:"
for dir in config logs scripts; do
    if [ -d "$PROJECT_DIR/$dir" ]; then
        echo ""
        echo "$PROJECT_DIR/$dir:"
        ls -la "$PROJECT_DIR/$dir" 2>/dev/null | head -10
    else
        echo "[WARN] Directory not found: $dir"
    fi
done

echo ""
echo "[SERVICE] Service Status:"
if launchctl list | grep -q "com.orangead.parking-monitor"; then
    echo "  [OK] Service is loaded"
    launchctl list | grep "com.orangead.parking-monitor"
else
    echo "  [INFO] Service not loaded in LaunchAgent"
fi

echo ""
echo "[NETWORK] Network Status:"
if lsof -i :9091 >/dev/null 2>&1; then
    echo "  [OK] Port 9091 is active"
    lsof -i :9091 2>/dev/null | head -3
else
    echo "  [INFO] Port 9091 not active"
fi

echo "======================================"
echo "[OK] Security audit complete"