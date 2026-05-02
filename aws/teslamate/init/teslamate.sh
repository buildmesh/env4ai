#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
export NEEDRESTART_MODE=a

log() { printf '[teslamate] %s\n' "$*"; }

log "Installing Tesla Mate..."

DB_USER="teslamate"
DB_PASS=$(openssl rand -base64 24)
DB_NAME="teslamate"
ENCRYPTION_KEY=$(openssl rand -hex 32)
DATA_ROOT="/srv/teslamate"
COMPOSE_DIR="$DATA_ROOT/compose"
POSTGRES_DIR="$DATA_ROOT/postgres"
GRAFANA_DIR="$DATA_ROOT/grafana"
DATA_DEVICE=""    # Example: /dev/nvme1n1 or /dev/xvdf . Leave blank to use root disk only.
DATA_FSTYPE="ext4"

mkdir -p "$COMPOSE_DIR" "$POSTGRES_DIR" "$GRAFANA_DIR"
chown -R ubuntu:ubuntu "$DATA_ROOT"
chown 472:472 "$GRAFANA_DIR"

cat > "$COMPOSE_DIR/docker-compose.yml" <<EOF
services:
  database:
    image: postgres:17.9@sha256:bf7b099328817f46a5248cf0df4c9f03a4c64954b442a4fa796ae84e97b716c7
    platform: linux/amd64
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASS}
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - ${POSTGRES_DIR}:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME} || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 30s

  teslamate:
    image: teslamate/teslamate:3.0.0@sha256:f064d5b303a98b3ae72d26dac2e7a4adfa67d40c33a2f08f3cc1348d7494cd33
    platform: linux/amd64
    restart: unless-stopped
    environment:
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      DATABASE_USER: ${DB_USER}
      DATABASE_PASS: ${DB_PASS}
      DATABASE_NAME: ${DB_NAME}
      DATABASE_HOST: database
      DISABLE_MQTT: "true"
    ports:
      - "127.0.0.1:4000:4000"
    depends_on:
      database:
        condition: service_healthy
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL

  grafana:
    image: teslamate/grafana:3.0.0@sha256:e02d1f036dd10771ea04db2bafc483067a9dbb874d0b5137dda5a6fe539b77dc
    restart: unless-stopped
    environment:
      DATABASE_USER: ${DB_USER}
      DATABASE_PASS: ${DB_PASS}
      DATABASE_NAME: ${DB_NAME}
      DATABASE_HOST: database
    ports:
      - "127.0.0.1:3000:3000"
    volumes:
      - ${GRAFANA_DIR}:/var/lib/grafana
EOF

cd "$COMPOSE_DIR"
docker compose pull
