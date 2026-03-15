#!/bin/bash
set -e

# Create data directories with proper ownership
mkdir -p /var/lib/prometheus/alertmanager
chown -R prometheus:prometheus /var/lib/prometheus/alertmanager

# Ensure config directory ownership
chown -R root:prometheus /etc/prometheus
chmod 750 /etc/prometheus

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable alertmanager.service

echo "Prometheus Alertmanager installed successfully."
echo "Start with: systemctl start alertmanager"
