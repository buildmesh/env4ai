#!/usr/bin/env bash
# BUZZ_INSTALLER_START
set -Eeuo pipefail
umask 077
readonly BUZZ_RELEASE="v0.5.2"
readonly BUZZ_RELEASE_COMMIT="3e48f1b2365d326ee1c9582448d86a99b44ecd5d"
readonly BUZZ_IMAGE="ghcr.io/block/buzz@sha256:12763e38fd99fe8f4e63466a08ea8e3afbda4da0ebd1f51f0b57d78f9b082abe"
readonly PERSIST_ROOT="/mnt/buzz"
readonly DOCKER_DATA_ROOT="${PERSIST_ROOT}/docker"
readonly INSTALL_DIR="${PERSIST_ROOT}/app"
readonly COMPOSE_DIR="${INSTALL_DIR}/deploy/compose"
readonly OWNER_KEY_FILE="${PERSIST_ROOT}/secrets/owner-key"
readonly INSTALLED_SCRIPT="/usr/local/sbin/install-buzz-relay-ec2"
log() { printf '[buzz-install] %s\n' "$*"; }
fail() { printf '[buzz-install] ERROR: %s\n' "$*" >&2; exit 1; }
[[ "${EUID}" -eq 0 ]] || fail "run this script as root"
prepare_persistent_storage() {
  mkdir -p "${PERSIST_ROOT}"
  install -d -m 0711 "${DOCKER_DATA_ROOT}"
  install -d -m 0755 "${INSTALL_DIR}"
  install -d -m 0700 "$(dirname "${OWNER_KEY_FILE}")"
}
configure_docker_data_root() {
  local daemon_config="/etc/docker/daemon.json"
  install -d -m 0755 /etc/docker
  if [[ -e "${daemon_config}" ]]; then
    if ! grep -Eq '"data-root"[[:space:]]*:[[:space:]]*"/mnt/buzz/docker"' "${daemon_config}"; then
      fail "${daemon_config} already exists without data-root=${DOCKER_DATA_ROOT}; merge that setting explicitly and rerun"
    fi
  else
    cat >"${daemon_config}" <<JSON
{
  "data-root": "${DOCKER_DATA_ROOT}"
}
JSON
    chmod 0644 "${daemon_config}"
  fi
}
install_packages() {
  local command
  for command in docker git curl openssl; do
    command -v "${command}" >/dev/null 2>&1 || fail "required command not found: ${command}"
  done
  configure_docker_data_root
  systemctl enable docker
  systemctl restart docker
  local actual_docker_root
  actual_docker_root="$(docker info --format '{{.DockerRootDir}}')"
  [[ "${actual_docker_root}" == "${DOCKER_DATA_ROOT}" ]] || \
    fail "Docker is using ${actual_docker_root}, expected ${DOCKER_DATA_ROOT}"
  docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin is not installed"
  local compose_raw compose_major compose_minor
  compose_raw="$(docker compose version --short)"
  compose_raw="${compose_raw#v}"
  compose_major="${compose_raw%%.*}"
  compose_minor="${compose_raw#*.}"
  compose_minor="${compose_minor%%.*}"
  if (( compose_major < 2 || (compose_major == 2 && compose_minor < 24) )); then
    fail "Docker Compose 2.24.4 or newer is required; found ${compose_raw}"
  fi
}
relay_host() {
  local detected_host="${BUZZ_RELAY_HOST:-}"
  if [[ -z "${detected_host}" ]]; then
    detected_host="$(hostname -I | tr ' ' '\n' | awk '/^10\.[0-9]+\.[0-9]+\.[0-9]+$/ { print; exit }')"
  fi
  [[ "${detected_host}" =~ ^10\.([0-9]{1,3}\.){2}[0-9]{1,3}$ ]] || \
    fail "could not find an internal 10.x.x.x IPv4 address for BUZZ_RELAY_HOST"
  printf '%s' "${detected_host}"
}
checkout_release() {
  if [[ ! -d "${INSTALL_DIR}/.git" ]]; then
    git clone --branch "${BUZZ_RELEASE}" --depth 1 \
      https://github.com/block/buzz.git "${INSTALL_DIR}"
  else
    git -C "${INSTALL_DIR}" fetch --depth 1 origin "refs/tags/${BUZZ_RELEASE}:refs/tags/${BUZZ_RELEASE}"
    git -C "${INSTALL_DIR}" checkout --detach --force "${BUZZ_RELEASE}"
  fi
  local actual_commit
  actual_commit="$(git -C "${INSTALL_DIR}" rev-parse HEAD)"
  [[ "${actual_commit}" == "${BUZZ_RELEASE_COMMIT}" ]] || \
    fail "release tag resolved to unexpected commit ${actual_commit}"
}
random_hex() { openssl rand -hex 32; }
write_runtime_defaults() {
  [[ "${BUZZ_RELAY_HOST:-}" != *$'\n'* ]] || fail "BUZZ_RELAY_HOST must be a single line"
  [[ "${BUZZ_GUI_ORIGINS:-}" != *$'\n'* ]] || fail "BUZZ_GUI_ORIGINS must be a comma-separated single line"
  cat >/etc/default/buzz-relay <<DEFAULTS
BUZZ_COMPOSE_TLS=false
BUZZ_RELAY_HOST=${BUZZ_RELAY_HOST:-}
BUZZ_GUI_ORIGINS=${BUZZ_GUI_ORIGINS:-}
DEFAULTS
  chmod 0600 /etc/default/buzz-relay
}
refresh_network_config() {
  [[ -f "${COMPOSE_DIR}/.env" ]] || fail "${COMPOSE_DIR}/.env does not exist"
  local relay_host http_port relay_url media_url public_origin cors_origins tmp_env
  relay_host="$(relay_host)"
  http_port="$(sed -n 's/^BUZZ_HTTP_PORT=//p' "${COMPOSE_DIR}/.env")"
  http_port="${http_port:-3000}"
  [[ "${relay_host}" =~ ^[A-Za-z0-9.-]+$ ]] || fail "BUZZ_RELAY_HOST contains unsupported characters"
  [[ "${http_port}" =~ ^[0-9]+$ ]] || fail "BUZZ_HTTP_PORT must be numeric"
  relay_url="ws://${relay_host}:${http_port}"
  media_url="http://${relay_host}:${http_port}/media"
  public_origin="http://${relay_host}:${http_port}"
  cors_origins="${public_origin},http://localhost:1420,https://tauri.localhost,http://tauri.localhost"
  if [[ -n "${BUZZ_GUI_ORIGINS:-}" ]]; then
    [[ "${BUZZ_GUI_ORIGINS}" != *$'\n'* ]] || fail "BUZZ_GUI_ORIGINS must be a comma-separated single line"
    cors_origins="${cors_origins},${BUZZ_GUI_ORIGINS}"
  fi
  tmp_env="$(mktemp "${COMPOSE_DIR}/.env.network.XXXXXX")"
  awk \
    -v domain="${relay_host}" \
    -v relay_url="${relay_url}" \
    -v media_url="${media_url}" \
    -v cors_origins="${cors_origins}" '
      /^BUZZ_DOMAIN=/ { print "BUZZ_DOMAIN=" domain; next }
      /^RELAY_URL=/ { print "RELAY_URL=" relay_url; next }
      /^BUZZ_MEDIA_BASE_URL=/ { print "BUZZ_MEDIA_BASE_URL=" media_url; next }
      /^BUZZ_MEDIA_SERVER_DOMAIN=/ { print "BUZZ_MEDIA_SERVER_DOMAIN=" domain; next }
      /^BUZZ_CORS_ORIGINS=/ { print "BUZZ_CORS_ORIGINS=" cors_origins; next }
      { print }
    ' "${COMPOSE_DIR}/.env" >"${tmp_env}"
  chmod 0600 "${tmp_env}"
  mv -f "${tmp_env}" "${COMPOSE_DIR}/.env"
  log "configured private relay endpoint ${relay_url}"
}
write_initial_config() {
  if [[ -e "${COMPOSE_DIR}/.env" ]]; then
    if [[ ! -e /etc/default/buzz-relay ]]; then
      printf 'BUZZ_COMPOSE_TLS=false\n' >/etc/default/buzz-relay
      chmod 0600 /etc/default/buzz-relay
    fi
    return
  fi
  local relay_host relay_url media_url public_origin cors_origins http_port owner_pubkey owner_secret key_output
  relay_host="$(relay_host)"
  http_port="3000"
  [[ "${relay_host}" =~ ^[A-Za-z0-9.-]+$ ]] || fail "BUZZ_RELAY_HOST contains unsupported characters"
  relay_url="ws://${relay_host}:${http_port}"
  media_url="http://${relay_host}:${http_port}/media"
  public_origin="http://${relay_host}:${http_port}"
  cors_origins="${public_origin},http://localhost:1420,https://tauri.localhost,http://tauri.localhost"
  if [[ -n "${BUZZ_GUI_ORIGINS:-}" ]]; then
    [[ "${BUZZ_GUI_ORIGINS}" != *$'\n'* ]] || fail "BUZZ_GUI_ORIGINS must be a comma-separated single line"
    cors_origins="${cors_origins},${BUZZ_GUI_ORIGINS}"
  fi
  docker pull "${BUZZ_IMAGE}"
  owner_pubkey="${BUZZ_OWNER_PUBKEY:-}"
  if [[ -z "${owner_pubkey}" ]]; then
    key_output="$(docker run --rm --entrypoint /usr/local/bin/buzz-admin "${BUZZ_IMAGE}" generate-key)"
    owner_pubkey="$(awk '/Public key:/ {print $3}' <<<"${key_output}")"
    owner_secret="$(awk '/Secret key:/ {print $3}' <<<"${key_output}")"
    [[ "${owner_pubkey}" =~ ^[0-9a-f]{64}$ && "${owner_secret}" =~ ^[0-9a-f]{64}$ ]] || \
      fail "buzz-admin did not return a valid owner keypair"
    install -d -m 0700 "$(dirname "${OWNER_KEY_FILE}")"
    printf '%s\n' "${owner_secret}" >"${OWNER_KEY_FILE}"
    chmod 0600 "${OWNER_KEY_FILE}"
  fi
  [[ "${owner_pubkey}" =~ ^[0-9a-fA-F]{64}$ ]] || fail "BUZZ_OWNER_PUBKEY must be 64 hex characters"
  cat >"${COMPOSE_DIR}/.env" <<ENV
BUZZ_IMAGE=${BUZZ_IMAGE}
BUZZ_DOMAIN=${relay_host}
RELAY_URL=${relay_url}
BUZZ_MEDIA_BASE_URL=${media_url}
BUZZ_MEDIA_SERVER_DOMAIN=${relay_host}
BUZZ_CORS_ORIGINS=${cors_origins}
BUZZ_REQUIRE_AUTH_TOKEN=true
BUZZ_REQUIRE_RELAY_MEMBERSHIP=true
BUZZ_ALLOW_NIP_OA_AUTH=true
BUZZ_AUTO_MIGRATE=true
BUZZ_GIT_CONFORMANCE_PROBE=true
RUST_LOG=buzz_relay=info,buzz_db=info,buzz_auth=info,buzz_pubsub=info,tower_http=info
RELAY_OWNER_PUBKEY=${owner_pubkey,,}
BUZZ_RELAY_PRIVATE_KEY=$(random_hex)
BUZZ_GIT_HOOK_HMAC_SECRET=$(random_hex)
POSTGRES_DB=buzz
POSTGRES_USER=buzz
POSTGRES_PASSWORD=$(random_hex)
REDIS_PASSWORD=$(random_hex)
BUZZ_S3_ACCESS_KEY=$(random_hex)
BUZZ_S3_SECRET_KEY=$(random_hex)
BUZZ_S3_BUCKET=buzz-media
BUZZ_S3_ADDRESSING_STYLE=path
BUZZ_HTTP_PORT=${http_port}
CADDY_HTTP_PORT=80
CADDY_HTTPS_PORT=443
ENV
  chmod 0600 "${COMPOSE_DIR}/.env"
  printf 'BUZZ_COMPOSE_TLS=false\n' >/etc/default/buzz-relay
  chmod 0600 /etc/default/buzz-relay
}
install_service() {
  local staged_script
  staged_script="$(mktemp)"
  {
    printf '#!/usr/bin/env bash\n'
    sed -n '/^# BUZZ_INSTALLER_START$/,$p' "$0"
  } >"${staged_script}"
  install -m 0755 "${staged_script}" "${INSTALLED_SCRIPT}"
  rm -f "${staged_script}"
  cat >/etc/systemd/system/buzz-relay.service <<UNIT
[Unit]
Description=Buzz relay Docker Compose stack
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target
[Service]
Type=oneshot
RemainAfterExit=yes
EnvironmentFile=/etc/default/buzz-relay
WorkingDirectory=${COMPOSE_DIR}
ExecStartPre=${INSTALLED_SCRIPT} --refresh-network
ExecStart=${COMPOSE_DIR}/run.sh start
ExecStop=${COMPOSE_DIR}/run.sh stop
TimeoutStartSec=600
TimeoutStopSec=180
[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable buzz-relay.service
}
verify_relay() {
  local port health_url attempt
  source /etc/default/buzz-relay
  port="$(sed -n 's/^BUZZ_HTTP_PORT=//p' "${COMPOSE_DIR}/.env")"
  health_url="http://127.0.0.1:${port}/_readiness"
  for attempt in $(seq 1 60); do
    if curl -fsS --max-time 5 "${health_url}" | grep -q '"status":"ready"'; then
      log "relay is ready at ${health_url}"
      return
    fi
    sleep 5
  done
  docker compose --env-file "${COMPOSE_DIR}/.env" -f "${COMPOSE_DIR}/compose.yml" logs --tail=100 relay >&2 || true
  fail "relay did not become ready at ${health_url}"
}
main() {
  log "checking persistent EBS storage"
  prepare_persistent_storage
  log "installing prerequisites"
  install_packages
  log "checking out ${BUZZ_RELEASE}"
  checkout_release
  write_initial_config
  write_runtime_defaults
  refresh_network_config
  install_service
  log "starting relay"
  systemctl restart buzz-relay.service
  verify_relay
  log "installation complete; preserve ${COMPOSE_DIR}/.env and ${OWNER_KEY_FILE} (if generated)"
}
case "${1:-}" in
  --refresh-network)
    refresh_network_config
    ;;
  "")
    main
    ;;
  *)
    fail "unknown argument: $1"
    ;;
esac
