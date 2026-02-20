#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
export NEEDRESTART_MODE=a

log() { printf '[agents] %s\n' "$*"; }

log "Installing Gas Town..."

sudo -u ubuntu PATH="/home/ubuntu/.local/bin:/home/ubuntu/go/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin" -H bash -lc 'cd /home/ubuntu && git clone https://github.com/steveyegge/gastown.git && cd gastown && make install'

export PATH="$PATH:/home/ubuntu/.local/bin"
echo "export PATH=\"$PATH:/home/ubuntu/.local/bin\"" >> /home/ubuntu/.bashrc

sudo bash -c 'curl -L https://github.com/dolthub/dolt/releases/latest/download/install.sh | bash'

