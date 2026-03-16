#!/bin/bash
set -e

# Stop and disable the service before removal
if systemctl is-active --quiet unitycatalog-server.service; then
    systemctl stop unitycatalog-server.service
fi
systemctl disable unitycatalog-server.service 2>/dev/null || true
