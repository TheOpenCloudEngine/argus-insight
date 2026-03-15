#!/bin/bash
set -e

if systemctl is-active --quiet alertmanager.service; then
    systemctl stop alertmanager.service
fi
systemctl disable alertmanager.service 2>/dev/null || true
