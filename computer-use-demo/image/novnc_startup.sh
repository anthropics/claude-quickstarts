#!/bin/bash
echo "starting noVNC"

# Function to check port availability
check_port() {
    local port=$1
    if lsof -i :$port >/dev/null 2>&1; then
        return 1  # Port is in use
    else
        return 0  # Port is available
    fi
}

# Find an available port starting from 5900
find_available_port() {
    local port=5900
    while ! check_port $port; do
        ((port++))
    done
    echo $port
}

# Dynamically assign the VNC server port
VNC_PORT=$(find_available_port)

# Start noVNC with explicit websocket settings
/opt/noVNC/utils/novnc_proxy \
    --vnc localhost:$VNC_PORT \
    --listen 6080 \
    --web /opt/noVNC \
    > /tmp/novnc.log 2>&1 &

# Wait for noVNC to start
timeout=10
while [ $timeout -gt 0 ]; do
    if netstat -tuln | grep -q ":6080 "; then
        break
    fi
    sleep 1
    ((timeout--))
done

echo "noVNC started successfully"
