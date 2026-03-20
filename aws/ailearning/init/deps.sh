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
    gnupg \
    lsb-release \
    git \
    jq \
    libicu-dev \
    python3 \
    python3-pip \
    python3-venv \
    ripgrep \
    sqlite3 \
    unzip \
    xz-utils \
    build-essential

# ------------------------------------------------------------
# NodeJS
# ------------------------------------------------------------
log "Installing nodejs, npm..."

curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
  | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
  | tee /etc/apt/sources.list.d/nodesource.list > /dev/null

apt-get update -y
apt-get install -y nodejs
node -v
npm -v

