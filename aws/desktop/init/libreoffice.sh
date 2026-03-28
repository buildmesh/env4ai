log() { echo "[libreoffice] $*"; }

log "Installing LibreOffice..."
apt-get update
apt-get install -y --no-install-recommends libreoffice
apt-get clean
rm -rf /var/lib/apt/lists/*
