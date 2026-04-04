#!/bin/bash
# Start the trdagnt dashboard (builds frontend + starts backend)
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"

# Build frontend if needed
if [ ! -d "$DIR/frontend/dist" ] || [ "$1" = "--build" ]; then
    echo "[Dashboard] Building frontend..."
    cd "$DIR/frontend"
    npm run build
fi

# Start backend (serves both API and frontend static files)
echo "[Dashboard] Starting server at http://localhost:8080"
cd "$DIR/.."
python3 -m uvicorn dashboard.backend.main:app --host 0.0.0.0 --port 8080 "$@"
