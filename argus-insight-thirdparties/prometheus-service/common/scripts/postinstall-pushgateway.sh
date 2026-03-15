#!/bin/bash
set -e

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable pushgateway.service

echo "Prometheus Pushgateway installed successfully."
echo "Start with: systemctl start pushgateway"
