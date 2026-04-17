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

instance_id=\$(aws ec2 describe-instances --filters "Name=tag:Name,Values=\$1" "Name=instance-state-name,Values=running" --query "Reservations[0].Instances[0].InstanceId" --output text)
echo "Connecting to \$1 (\$instance_id)"
aws ssm start-session --region us-west-2 --target "\$instance_id"
EOF
chown ubuntu.ubuntu /home/ubuntu/.local/bin/ssm
chmod 500 /home/ubuntu/.local/bin/ssm
