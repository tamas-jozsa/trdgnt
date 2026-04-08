#!/bin/bash
# Disable trdagnt dashboard auto-start

PLIST_NAME="com.tjozsa.trdagnt-dashboard"
PLIST_FILE="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo "Disabling trdagnt dashboard auto-start..."

if launchctl list | grep -q "$PLIST_NAME"; then
    launchctl unload -w "$PLIST_FILE"
    echo "✓ Auto-start disabled"
else
    echo "LaunchAgent was not loaded"
fi

echo ""
echo "To re-enable auto-start, run: ./setup-autostart.sh"
