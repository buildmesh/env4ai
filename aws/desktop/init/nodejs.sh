log() { echo "[nodejs] $*"; }

log "Installing NVM..."
export USER_HOME=/home/ubuntu
export NVM_DIR="$USER_HOME/.nvm"
runuser -u ubuntu -- bash <<EOF
git clone https://github.com/nvm-sh/nvm.git "$NVM_DIR"
cd "$NVM_DIR" && git checkout v0.40.3
echo 'export NVM_DIR="$USER_HOME/.nvm"' >> ~/.bashrc
echo '[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"' >> ~/.bashrc
EOF

log "Installing NodeJS"
runuser -u ubuntu -- bash <<EOF
. "$NVM_DIR/nvm.sh"
nvm install --lts
nvm use --lts
EOF
