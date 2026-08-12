#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
export NEEDRESTART_MODE=a

log() { echo "[deps] $*"; }

# ------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------
log "Installing packages..."

apt-get update -y
apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gzip \
    unzip

echo "sudo -iu ubuntu" > /usr/local/bin/s
chmod +x /usr/local/bin/s
