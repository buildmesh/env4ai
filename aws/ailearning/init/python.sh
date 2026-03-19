#!/usr/bin/env bash
set -euo pipefail

log() { printf '[python] %s\n' "$*"; }

# Install uv and python
VERSION="0.9.21"
ASSET="uv-x86_64-unknown-linux-gnu.tar.gz"
BASE_URL="https://github.com/astral-sh/uv/releases/download/${VERSION}"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cd "$TMP"

log "Downloading uv ${VERSION}..."
curl -fL -o "${ASSET}" "${BASE_URL}/${ASSET}"
curl -fL -o "${ASSET}.sha256" "${BASE_URL}/${ASSET}.sha256"

log "Verifying checksum..."
sha256sum -c "${ASSET}.sha256"

log "Extracting..."
tar -xzf "${ASSET}"

log "Installing to /usr/local/bin..."
sudo install -m 0755 ./uv*/uv /usr/local/bin/uv

# uvx is bundled in newer releases; install if present
if ls ./uv*/uvx >/dev/null 2>&1; then
  sudo install -m 0755 ./uv*/uvx /usr/local/bin/uvx
fi

log "Done:"
uv --version

uv python install 3.11
