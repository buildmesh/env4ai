#!/bin/bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export APT_LISTCHANGES_FRONTEND=none
export NEEDRESTART_MODE=a

log() { echo "[gui] $*"; }

log "Updating system..."
apt-get update -y
apt-get upgrade -y

log "Installing X11, TigerVNC"
apt-get update
apt-get install -y \
    ubuntu-desktop-minimal \
    gnome-terminal dbus-x11 \
    tigervnc-standalone-server \
    tigervnc-common \
    libfuse2
apt-get clean
rm -rf /var/lib/apt/lists/*

log "Configuration X11, TigerVNC..."
runuser -l ubuntu -c 'mkdir /home/ubuntu/.vnc'
runuser -l ubuntu -c 'echo "vncpassword" | vncpasswd -f > /home/ubuntu/.vnc/passwd'
runuser -l ubuntu -c 'chmod 600 /home/ubuntu/.vnc/passwd'
runuser -l ubuntu -c 'cat > /home/ubuntu/.vnc/xstartup <<EOF
#!/bin/bash
export XDG_SESSION_TYPE=x11
export XDG_CURRENT_DESKTOP=GNOME
export GNOME_SHELL_SESSION_MODE=ubuntu
[ -x /etc/vnc/xstartup ] && exec /etc/vnc/xstartup
[ -r \$HOME/.Xresources ] && xrdb \$HOME/.Xresources
dbus-launch --exit-with-session gnome-session
EOF
chmod +x /home/ubuntu/.vnc/xstartup'
runuser -l ubuntu -c 'vncserver :1 -geometry 1920x1080 -depth 24'
runuser -l ubuntu -c 'mkdir -p /home/ubuntu/.config && echo yes > /home/ubuntu/.config/gnome-initial-setup-done'
echo "export LANG=en_US.UTF-8" >> /home/ubuntu/.profile
echo "export LC_ALL=en_US.UTF-8" >> /home/ubuntu/.profile
