#!/bin/bash
set -e

# Stop and disable the service before removal
if systemctl is-active --quiet prometheus.service; then
    systemctl stop prometheus.service
fi
systemctl disable prometheus.service 2>/dev/null || true
