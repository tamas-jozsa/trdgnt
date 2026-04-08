#!/bin/bash
# Setup script for trdagnt dashboard auto-start
# Run this to enable the dashboard to start automatically on boot

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.tjozsa.trdagnt-dashboard"
PLIST_FILE="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

echo "=== trdagnt Dashboard Auto-start Setup ==="
echo ""

# Check if trdagnt is in /etc/hosts
if ! grep -q "trdagnt" /etc/hosts 2>/dev/null; then
    echo "Adding 'trdagnt' hostname to /etc/hosts..."
    echo "This requires sudo access. Please enter your password if prompted."
    sudo sh -c 'echo "127.0.0.1	trdagnt" >> /etc/hosts'
    echo "✓ Added trdagnt -> 127.0.0.1 to /etc/hosts"
else
    echo "✓ trdagnt hostname already exists in /etc/hosts"
fi

echo ""

# Unload existing agent if present (to update it)
if launchctl list | grep -q "$PLIST_NAME"; then
    echo "Unloading existing LaunchAgent..."
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
fi

# Load the LaunchAgent
echo "Loading LaunchAgent: $PLIST_NAME"
launchctl load -w "$PLIST_FILE"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "The dashboard will now:"
echo "  • Start automatically when you log in"
echo "  • Restart if it crashes"
echo "  • Be available at: http://trdagnt:8888"
echo ""
echo "To start it now without rebooting:"
echo "  launchctl start $PLIST_NAME"
echo ""
echo "To disable auto-start:"
echo "  launchctl unload -w $PLIST_FILE"
