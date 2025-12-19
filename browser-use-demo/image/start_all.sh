#!/bin/bash

set -e

export DISPLAY=:${DISPLAY_NUM}
./xvfb_startup.sh
./tint2_startup.sh  # Keep taskbar for window management
./mutter_startup.sh  # Keep window manager for controls
./x11vnc_startup.sh
