#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
export NEEDRESTART_MODE=a

log() { echo "[go] $*"; }

# ------------------------------------------------------------
# Go
# ------------------------------------------------------------
log "Installing Go..."
curl -fL -o /tmp/go1.24.7.linux-amd64.tar.gz https://go.dev/dl/go1.24.7.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf /tmp/go1.24.7.linux-amd64.tar.gz
export PATH="/usr/local/go/bin:$PATH"
echo 'export PATH="/usr/local/go/bin:$PATH"' >> /home/ubuntu/.bashrc
