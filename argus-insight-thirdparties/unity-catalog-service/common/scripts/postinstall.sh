#!/bin/bash
set -e

# Create data directories with proper ownership
mkdir -p /var/lib/unity-catalog/data
chown -R unitycatalog:unitycatalog /var/lib/unity-catalog

# Ensure config directory ownership
chown -R root:unitycatalog /etc/unity-catalog
chmod 750 /etc/unity-catalog

# Ensure log directory
mkdir -p /var/log/unity-catalog
chown -R unitycatalog:unitycatalog /var/log/unity-catalog

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable unitycatalog-server.service

echo "Unity Catalog Server installed successfully."
echo "Start with: systemctl start unitycatalog-server"
