#!/bin/sh
set -e

echo "Starting boxwatchr..."

mkdir -p /etc/rspamd/local.d
mkdir -p /app/data/redis

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

if [ -d "/app/config/rspamd/local.d" ]; then
    cp /app/config/rspamd/local.d/* /etc/rspamd/local.d/ 2>/dev/null || true
fi

cat > /etc/rspamd/local.d/classifier-bayes.conf << 'EOF'
backend = "redis";
new_schema = true;
EOF

cat > /etc/rspamd/local.d/redis.conf << 'EOF'
servers = "127.0.0.1";
EOF

cat > /etc/rspamd/local.d/options.inc << 'EOF'
dns {
    nameserver = ["127.0.0.1:5335"];
}
EOF

echo "Launching supervisord..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf