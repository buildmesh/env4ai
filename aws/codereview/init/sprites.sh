#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
export NEEDRESTART_MODE=a

log() { printf '[sprites] %s\n' "$*"; }

# Install fly.io sprites CLI
log "Installing fly.io sprites CLI..."
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
cd "$tmpdir"

URL="https://sprites-binaries.t3.storage.dev/client"
VERSION="v0.0.1-rc41"
OS="linux"
ARCH="amd64"
FILENAME="sprite-${OS}-${ARCH}.tar.gz"

curl -LO "${URL}/${VERSION}/${FILENAME}"
curl -LO "${URL}/${VERSION}/${FILENAME}.sha256"
sed "s|sprite-${OS}-${ARCH}/||" "${FILENAME}.sha256" | sha256sum -c

tar xzf ${FILENAME}
mv sprite /usr/local/bin/

