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
  | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
  | sudo tee /etc/apt/sources.list.d/nodesource.list > /dev/null

sudo -E apt-get update -y
sudo -E apt-get install -y nodejs
node -v
npm -v

# ------------------------------------------------------------
# Go
# ------------------------------------------------------------
log "Installing Go..."
curl -fL -o /tmp/go1.24.7.linux-amd64.tar.gz https://go.dev/dl/go1.24.7.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf /tmp/go1.24.7.linux-amd64.tar.gz
export PATH="/usr/local/go/bin:$PATH"
echo "export PATH=\"/usr/local/go/bin:$PATH\"" >> /home/ubuntu/.bashrc
