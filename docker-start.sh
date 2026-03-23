 #!/bin/bash
  echo "==> Starting SAI Tipster API (port ${PORT:-8080})..."
  cd /app && python api_server.py
