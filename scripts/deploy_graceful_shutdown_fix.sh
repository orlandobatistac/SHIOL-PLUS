#!/bin/bash
# Deploy graceful shutdown improvements to production server
# This script fixes the issue where pipelines get stuck in "running" state
# when systemd restarts the service.

set -e  # Exit on error

echo "=========================================="
echo "Deploying Graceful Shutdown Fix"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Step 1: Copying updated systemd service file${NC}"
sudo cp /var/www/SHIOL-PLUS/deploy/shiolplus.service /etc/systemd/system/shiolplus.service
echo -e "${GREEN}✓ Service file updated${NC}"
echo ""

echo -e "${YELLOW}Step 2: Reloading systemd daemon${NC}"
sudo systemctl daemon-reload
echo -e "${GREEN}✓ Systemd daemon reloaded${NC}"
echo ""

echo -e "${YELLOW}Step 3: Restarting SHIOL+ service (will use new graceful shutdown)${NC}"
sudo systemctl restart shiolplus.service
echo -e "${GREEN}✓ Service restarted${NC}"
echo ""

echo -e "${YELLOW}Step 4: Checking service status${NC}"
sudo systemctl status shiolplus.service --no-pager | head -20
echo ""

echo -e "${YELLOW}Step 5: Verifying graceful shutdown configuration${NC}"
echo "Current TimeoutStopSec setting:"
systemctl show shiolplus.service -p TimeoutStopUSec
echo ""

echo -e "${GREEN}=========================================="
echo "Deployment Complete!"
echo "==========================================${NC}"
echo ""
echo "Changes implemented:"
echo "  1. Signal handlers for SIGTERM/SIGINT"
echo "  2. Recovery function for stale pipelines on startup"
echo "  3. Systemd timeout increased from 30s to 180s"
echo "  4. Pipeline tracking for graceful cleanup"
echo ""
echo "To monitor logs:"
echo "  journalctl -u shiolplus.service -f"
echo ""
echo "To check for stale pipelines:"
echo "  /root/.venv_shiolplus/bin/python -c \"from src.database import get_db_connection; conn = get_db_connection().__enter__(); cursor = conn.cursor(); cursor.execute('SELECT execution_id, start_time, status FROM pipeline_execution_logs WHERE status=\\\"running\\\" ORDER BY start_time DESC'); print(cursor.fetchall())\""
