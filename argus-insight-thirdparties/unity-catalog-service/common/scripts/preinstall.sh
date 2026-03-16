#!/bin/bash
set -e

# Create unitycatalog system user and group if they don't exist
if ! getent group unitycatalog >/dev/null 2>&1; then
    groupadd --system unitycatalog
fi

if ! getent passwd unitycatalog >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /sbin/nologin \
        --gid unitycatalog unitycatalog
fi
