#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
export NEEDRESTART_MODE=a

log() { printf '[aws_ssm] %s\n' "$*"; }

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
cd "$tmpdir"

# Import AWS SSM Session Manager PGP public key
log "Importing AWS SSM Session Manager PGP public key..."
# AWS Session Manager Plugin PGP Public Key
# Source: https://docs.aws.amazon.com/systems-manager/latest/userguide/install-plugin-linux-verify-signature.html
# Retrieved: 2026-04-14
# Key ID: 2C4D4AFF6F6757EE
# Expected fingerprint: 7959 6371 24CE 093A D501 D47A 2C4D 4AFF 6F67 57EE
cat <<'EOF' | gpg --import
-----BEGIN PGP PUBLIC KEY BLOCK-----

mFIEZ5ERQxMIKoZIzj0DAQcCAwQjuZy+IjFoYg57sLTGhF3aZLBaGpzB+gY6j7Ix
P7NqbpXyjVj8a+dy79gSd64OEaMxUb7vw/jug+CfRXwVGRMNtIBBV1MgU1NNIFNl
c3Npb24gTWFuYWdlciA8c2Vzc2lvbi1tYW5hZ2VyLXBsdWdpbi1zaWduZXJAYW1h
em9uLmNvbT4gKEFXUyBTeXN0ZW1zIE1hbmFnZXIgU2Vzc2lvbiBNYW5hZ2VyIFBs
dWdpbiBMaW51eCBTaWduZXIgS2V5KYkBAAQQEwgAqAUCZ5ERQ4EcQVdTIFNTTSBT
ZXNzaW9uIE1hbmFnZXIgPHNlc3Npb24tbWFuYWdlci1wbHVnaW4tc2lnbmVyQGFt
YXpvbi5jb20+IChBV1MgU3lzdGVtcyBNYW5hZ2VyIFNlc3Npb24gTWFuYWdlciBQ
bHVnaW4gTGludXggU2lnbmVyIEtleSkWIQR5WWNxJM4JOtUB1HosTUr/b2dX7gIe
AwIbAwIVCAAKCRAsTUr/b2dX7rO1AQCa1kig3lQ78W/QHGU76uHx3XAyv0tfpE9U
oQBCIwFLSgEA3PDHt3lZ+s6m9JLGJsy+Cp5ZFzpiF6RgluR/2gA861M=
=2DQm
-----END PGP PUBLIC KEY BLOCK-----
EOF

KEY_ID="2C4D4AFF6F6757EE"
EXPECTED_FPR="7959637124CE093AD501D47A2C4D4AFF6F6757EE"

ACTUAL_FPR=$(gpg --fingerprint "$KEY_ID" | grep -A 1 "pub" | tail -n 1 | tr -d '[:space:]')

if [ "$ACTUAL_FPR" != "$EXPECTED_FPR" ]; then
  echo "Unexpected AWS Session Manager plugin PGP fingerprint: $ACTUAL_FPR" >&2
  exit 1
fi

# Download and verify deb package
log "Downloading and verifying AWS Session Manager plugin deb package..."

curl -o "session-manager-plugin.deb" "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb"
curl -o "session-manager-plugin.deb.sig" "https://s3.amazonaws.com/session-manager-downloads/plugin/latest/ubuntu_64bit/session-manager-plugin.deb.sig"

gpg --batch --verify session-manager-plugin.deb.sig session-manager-plugin.deb

if [ $? -ne 0 ]; then
    echo "Signature verification failed!"
    exit 1
fi

# Install deb package
log "Installing AWS Session Manager plugin..."

dpkg -i session-manager-plugin.deb

