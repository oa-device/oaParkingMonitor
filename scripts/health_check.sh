#!/bin/bash
# Health check script for oaParkingMonitor

# Default settings
HOST="localhost"
PORT="9091"
TIMEOUT=10

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --host HOST      Host to check (default: localhost)"
            echo "  --port PORT      Port to check (default: 9091)"
            echo "  --timeout SECS   Request timeout (default: 10)"
            echo "  -h, --help       Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

URL="http://${HOST}:${PORT}/health"

echo "🔍 Checking oaParkingMonitor health..."
echo "   URL: $URL"
echo "   Timeout: ${TIMEOUT}s"
echo ""

# Check if service is responding
if ! curl -s --connect-timeout "$TIMEOUT" --max-time "$TIMEOUT" "$URL" > /dev/null; then
    echo "❌ Service not responding at $URL"
    exit 1
fi

# Get health status
RESPONSE=$(curl -s --connect-timeout "$TIMEOUT" --max-time "$TIMEOUT" "$URL")

if [ $? -ne 0 ]; then
    echo "❌ Failed to get health status"
    exit 1
fi

# Parse JSON response (basic parsing)
STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
UPTIME=$(echo "$RESPONSE" | grep -o '"uptime":[0-9.]*' | cut -d':' -f2)
VERSION=$(echo "$RESPONSE" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)

echo "📊 Health Status:"
echo "   Status: $STATUS"
echo "   Version: $VERSION"
echo "   Uptime: ${UPTIME}s"

# Check if healthy
if [ "$STATUS" = "healthy" ]; then
    echo ""
    echo "✅ Service is healthy!"
    
    # Get additional metrics if available
    FPS=$(echo "$RESPONSE" | grep -o '"current_fps":[0-9.]*' | cut -d':' -f2)
    SPACES=$(echo "$RESPONSE" | grep -o '"parking_spaces_monitored":[0-9]*' | cut -d':' -f2)
    
    if [ -n "$FPS" ] && [ -n "$SPACES" ]; then
        echo "   FPS: $FPS"
        echo "   Parking spaces: $SPACES"
    fi
    
    exit 0
else
    echo ""
    echo "❌ Service is not healthy!"
    echo "   Full response: $RESPONSE"
    exit 1
fi