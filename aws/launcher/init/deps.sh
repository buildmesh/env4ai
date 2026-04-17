#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
export NEEDRESTART_MODE=a

log() { echo "[deps] $*"; }

# ------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------
log "Installing packages..."

apt-get update -y
apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    make \
    unzip
apt-get clean
rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------
# SSM convenience script
# ------------------------------------------------------------
log "Adding 'ssm' convenience script..."

mkdir -p /home/ubuntu/.local/bin
chown ubuntu.ubuntu /home/ubuntu/.local/bin
echo 'PATH="$HOME/.local/bin:$PATH"' >> /home/ubuntu/.bashrc
cat > "/home/ubuntu/.local/bin/ssm" << EOF
#!/bin/sh
set -eu

if [ "\$#" -ne 1 ] || [ -z "\$1" ]; then
    echo "Usage: ssm <environment-name>" >&2
    exit 1
fi

environment_name="\$1"
configured_region=\$(aws configure get region 2>/dev/null || true)
region=\$(printf '%s' "\${AWS_REGION:-\${AWS_DEFAULT_REGION:-\$configured_region}}" | tr -d '[:space:]')

if [ -z "\$region" ]; then
    echo "Unable to resolve AWS region. Set AWS_REGION, AWS_DEFAULT_REGION, or configure the AWS CLI region." >&2
    exit 1
fi

instance_id=\$(aws ec2 describe-instances \
    --region "\$region" \
    --filters "Name=tag:Name,Values=\$environment_name" "Name=instance-state-name,Values=running" \
    --query "Reservations[0].Instances[0].InstanceId" \
    --output text)

if [ -z "\$instance_id" ] || [ "\$instance_id" = "None" ] || [ "\$instance_id" = "null" ]; then
    echo "Unable to find a running instance named '\$environment_name'." >&2
    exit 1
fi

echo "Connecting to \$environment_name (\$instance_id)"
exec aws ssm start-session --region "\$region" --target "\$instance_id"
EOF
chown ubuntu.ubuntu /home/ubuntu/.local/bin/ssm
chmod 500 /home/ubuntu/.local/bin/ssm
