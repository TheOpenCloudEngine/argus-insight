#!/bin/bash
set -e

# Create prometheus system user and group if they don't exist
if ! getent group prometheus >/dev/null 2>&1; then
    groupadd --system prometheus
fi

if ! getent passwd prometheus >/dev/null 2>&1; then
    useradd --system --no-create-home --shell /sbin/nologin \
        --gid prometheus prometheus
fi
