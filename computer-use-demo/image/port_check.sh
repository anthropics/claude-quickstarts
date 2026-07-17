#!/bin/bash

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -i :$port >/dev/null 2>&1; then
        return 1  # Port is in use
    else
        return 0  # Port is available
    fi
}

# Function to find an available port starting from a given port
find_available_port() {
    local start_port=$1
    local port=$start_port
    while ! check_port $port; do
        ((port++))
    done
    echo $port
}

# Main script
if [ $# -ne 1 ]; then
    echo "Usage: $0 <start_port>"
    exit 1
fi

start_port=$1
available_port=$(find_available_port $start_port)
echo $available_port
