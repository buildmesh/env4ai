readonly VERSION="v0.52.3"
readonly REPO="cashapp/hermit"
readonly INSTALL_PATH="/usr/local/bin/hermit"

# SHA-256 values published in GitHub's v0.52.3 release metadata.
readonly SHA256_LINUX_AMD64="006ad4201d0df178a0b856d50cd2304379e24a532883602dba0333e15f0e92e8"
readonly SHA256_LINUX_ARM64="0673dd0a1c136901e972f88afd57e4b342c561479a9cc93cfa0891a86a0fea76"

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

if [[ "$(id -u)" -ne 0 ]]; then
    die "this script must be run as root"
fi

for command in curl sha256sum gzip install mktemp; do
    command -v "$command" >/dev/null 2>&1 ||
        die "required command not found: $command"
done

case "$(uname -s)" in
    Linux)
        os="linux"
        ;;
    *)
        die "unsupported operating system: $(uname -s)"
        ;;
esac

case "$(uname -m)" in
    x86_64|amd64)
        arch="amd64"
        expected_sha256="${SHA256_LINUX_AMD64}"
        ;;
    aarch64|arm64)
        arch="arm64"
        expected_sha256="${SHA256_LINUX_ARM64}"
        ;;
    *)
        die "unsupported CPU architecture: $(uname -m)"
        ;;
esac

artifact="hermit-${os}-${arch}.gz"
url="https://github.com/${REPO}/releases/download/${VERSION}/${artifact}"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

archive="${tmpdir}/${artifact}"
binary="${tmpdir}/hermit"

printf 'Installing Hermit %s\n' "$VERSION"
printf 'Platform: %s/%s\n' "$os" "$arch"
printf 'Source: %s\n' "$url"

# Download.
curl \
    --fail \
    --location \
    --silent \
    --show-error \
    --proto '=https' \
    --proto-redir '=https' \
    --tlsv1.2 \
    --retry 3 \
    --retry-delay 2 \
    --retry-all-errors \
    --connect-timeout 30 \
    --output "$archive" \
    "$url"

printf 'Verifying SHA-256...\n'

actual_sha256="$(sha256sum "$archive" | awk '{print $1}')"

if [[ "$actual_sha256" != "$expected_sha256" ]]; then
    printf 'SECURITY ERROR: Hermit checksum mismatch\n' >&2
    printf 'Expected: %s\n' "$expected_sha256" >&2
    printf 'Actual:   %s\n' "$actual_sha256" >&2
    exit 1
fi

printf 'SHA-256 verified.\n'

gzip --test "$archive"

gzip --decompress --stdout "$archive" > "$binary"
chmod 0755 "$binary"

printf 'Checking downloaded Hermit binary...\n'
"$binary" version

install \
    --owner=root \
    --group=root \
    --mode=0755 \
    "$binary" \
    "$INSTALL_PATH"

printf 'Installed Hermit to %s\n' "$INSTALL_PATH"

"$INSTALL_PATH" version

printf 'Hermit installation complete.\n'
