#!/bin/bash
# Start MiroFish backend on port 5001, then our API on $PORT

set -e

echo "==> Starting MiroFish backend (port 5001)..."
cd /app/mirofish && python backend/run.py &
MIROFISH_PID=$!

# Wait for MiroFish to be ready
echo "==> Waiting for MiroFish..."
for i in $(seq 1 30); do
  if curl -s http://localhost:5001/health >/dev/null 2>&1; then
    echo "==> MiroFish ready."
    break
  fi
  sleep 2
done

echo "==> Starting SAI Tipster API (port ${PORT:-8080})..."
cd /app && python api_server.py
