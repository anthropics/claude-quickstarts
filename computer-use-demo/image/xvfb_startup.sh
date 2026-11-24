#!/bin/bash
set -e  # Exit on error

DPI=96
RES_AND_DEPTH=${WIDTH}x${HEIGHT}x24

# Function to check if Xvfb is already running. The lock file alone is not
# enough: it survives `docker stop` / `docker start`, so a restarted container
# would report a display that no longer exists. Ask the X server instead.
check_xvfb_running() {
    if [ -e /tmp/.X${DISPLAY_NUM}-lock ] && xdpyinfo >/dev/null 2>&1; then
        return 0  # Xvfb is already running
    else
        return 1  # Xvfb is not running
    fi
}

# Remove the lock and socket left behind by an earlier Xvfb that is gone,
# otherwise the new Xvfb refuses to start on the same display number.
remove_stale_xvfb_files() {
    rm -f /tmp/.X${DISPLAY_NUM}-lock /tmp/.X11-unix/X${DISPLAY_NUM}
}

# Function to check if Xvfb is ready
wait_for_xvfb() {
    local timeout=10
    local start_time=$(date +%s)
    while ! xdpyinfo >/dev/null 2>&1; do
        if [ $(($(date +%s) - start_time)) -gt $timeout ]; then
            echo "Xvfb failed to start within $timeout seconds" >&2
            return 1
        fi
        sleep 0.1
    done
    return 0
}

# Check if Xvfb is already running
if check_xvfb_running; then
    echo "Xvfb is already running on display ${DISPLAY}"
    exit 0
fi

remove_stale_xvfb_files

# Start Xvfb
Xvfb $DISPLAY -ac -screen 0 $RES_AND_DEPTH -retro -dpi $DPI -nolisten tcp -nolisten unix &
XVFB_PID=$!

# Wait for Xvfb to start
if wait_for_xvfb; then
    echo "Xvfb started successfully on display ${DISPLAY}"
    echo "Xvfb PID: $XVFB_PID"
else
    echo "Xvfb failed to start"
    kill $XVFB_PID
    exit 1
fi
