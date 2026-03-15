#!/bin/bash
set -e

if systemctl is-active --quiet pushgateway.service; then
    systemctl stop pushgateway.service
fi
systemctl disable pushgateway.service 2>/dev/null || true
