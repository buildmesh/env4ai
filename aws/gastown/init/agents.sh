#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
export NEEDRESTART_MODE=a

log() { printf '[agents] %s\n' "$*"; }

# Install Codex
log "Installing Codex..."
sudo -E npm i -g @openai/codex

# Install Beads
log "Installing Beads..."
export CGO_ENABLED=1
sudo -u ubuntu -H bash -lc 'cd /home/ubuntu && /usr/local/go/bin/go install github.com/steveyegge/beads/cmd/bd@latest'

# Add Google's signing key + repo (modern keyring approach)
log "Installing Google Chrome..."
sudo install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
  | sudo gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg
sudo chmod a+r /etc/apt/keyrings/google-chrome.gpg

echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" \
  | sudo tee /etc/apt/sources.list.d/google-chrome.list >/dev/null

# Install Chrome
sudo -E apt-get update </dev/null
sudo -E apt-get install -y google-chrome-stable </dev/null
echo "export ROD_CHROME_BIN=/usr/bin/google-chrome" >> /home/ubuntu/.bashrc

# Install Rodney
log "Installing Rodney..."
sudo -u ubuntu -H bash -lc 'cd /tmp && git clone https://github.com/simonw/rodney.git'
sudo -u ubuntu -H bash -lc 'cd /tmp/rodney && /usr/local/go/bin/go build -buildvcs=false -o rodney . && sudo mv -i rodney /usr/bin'

# Install Showboat
log "Installing Showboat..."
sudo -u ubuntu -H bash -lc 'uv tool install showboat'

echo "export PATH=\"/home/ubuntu/.local/bin:/home/ubuntu/go/bin:$PATH\"" >> /home/ubuntu/.bashrc
export PATH="/home/ubuntu/.local/bin:/home/ubuntu/go/bin:$PATH"
