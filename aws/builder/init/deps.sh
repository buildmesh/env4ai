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

sudo -E apt-get update -y
sudo -E apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    jq \
    libicu-dev \
    ripgrep \
    sqlite3 \
    unzip \
    xz-utils \
    build-essential

