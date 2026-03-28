#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
export NEEDRESTART_MODE=a

log() { printf '[agents] %s\n' "$*"; }

# Install Codex
log "Installing Codex..."
runuser -l ubuntu -c '. "/home/ubuntu/.nvm/nvm.sh" && npm i -g @openai/codex'

# Install Claude Code
log "Installing Claude Code..."
runuser -l ubuntu -c 'curl -fsSL https://claude.ai/install.sh | bash'

echo 'export PATH="/home/ubuntu/.local/bin:$PATH"' >> /home/ubuntu/.bashrc
