#!/bin/sh
set -e

echo "Starting Boxwatchr..."

mkdir -p /etc/rspamd/local.d

if [ -z "$RSPAMD_PASSWORD" ]; then
    echo "ERROR: RSPAMD_PASSWORD is not set. Please set it in your .env file."
    exit 1
fi

echo "Generating rspamd password hash..."
RSPAMD_HASH=$(rspamadm pw -q -p "$RSPAMD_PASSWORD")

cat > /etc/rspamd/local.d/worker-controller.inc << EOF
# This file is generated automatically on container startup.
# Do not edit it manually. Set RSPAMD_PASSWORD in your .env file instead.
password = "$RSPAMD_HASH";
bind_socket = "*:11334";
EOF

echo "rspamd password configured successfully"

if [ -d "/config/rspamd/local.d" ]; then
    cp /config/rspamd/local.d/* /etc/rspamd/local.d/ 2>/dev/null || true
fi

echo "Launching supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf