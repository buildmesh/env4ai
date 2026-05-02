#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
export NEEDRESTART_MODE=a

log() { echo "[deps] $*"; }

# ------------------------------------------------------------
# Upgrade
# ------------------------------------------------------------
log "Upgrading..."

apt-get update -y
apt-get upgrade -y

# ------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------
log "Installing packages..."

apt-get update -y
apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    make
apt-get clean
rm -rf /var/lib/apt/lists/*

