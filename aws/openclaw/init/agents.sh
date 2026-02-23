#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
export NEEDRESTART_MODE=a

log() { printf '[agents] %s\n' "$*"; }

# Install Codex CLI
log "Installing Codex CLI..."
npm i -g @openai/codex

# Install Claude Code
log "Installing Claude Code..."
sudo -u ubuntu -H bash -lc 'curl -fsSL https://claude.ai/install.sh | bash'
echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/ubuntu/.bashrc
