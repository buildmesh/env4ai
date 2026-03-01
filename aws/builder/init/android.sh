#!/usr/bin/env bash
set -euo pipefail

export ANDROID_TOOLS_URL="https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
export ANDROID_TOOLS_SHA256="2d2d50857e4eb553af5a6dc3ad507a17adf43d115264b1afc116f95c92e5e258"
export ANDROID_TOOLS_ARCHIVE="/tmp/commandlinetools-linux-11076708_latest.zip"

# Install JDK 21
apt-get update
apt-get install -y openjdk-21-jdk
echo "export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64" >> /home/ubuntu/.bashrc
echo 'export PATH="$JAVA_HOME/bin:$PATH"' >> /home/ubuntu/.bashrc
#source /home/user/.bashrc
#java -version

# Install Android SDK
export ANDROID_SDK_ROOT="/home/ubuntu/Android/Sdk"
sudo -u ubuntu -H -E bash -lc 'mkdir -p "$ANDROID_SDK_ROOT/cmdline-tools"'
sudo -u ubuntu -H -E bash -lc 'curl -fsSL "$ANDROID_TOOLS_URL" -o "$ANDROID_TOOLS_ARCHIVE"'
# Reason: fail setup if command-line tools artifact does not match trusted digest.
echo "${ANDROID_TOOLS_SHA256}  ${ANDROID_TOOLS_ARCHIVE}" | sha256sum -c -
sudo -u ubuntu -H -E bash -lc 'unzip -q "$ANDROID_TOOLS_ARCHIVE" -d /tmp'
sudo -u ubuntu -H -E bash -lc 'mv /tmp/cmdline-tools "$ANDROID_SDK_ROOT/cmdline-tools/latest"'
sudo -u ubuntu -H -E bash -lc 'echo "export ANDROID_SDK_ROOT=\$HOME/Android/Sdk" >> $HOME/.bashrc'
sudo -u ubuntu -H -E bash -lc 'echo "export ANDROID_HOME=\$ANDROID_SDK_ROOT" >> $HOME/.bashrc'
sudo -u ubuntu -H -E bash -lc 'echo "export PATH=\"\$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:\$ANDROID_SDK_ROOT/platform-tools:\$JAVA_HOME/bin:\$PATH\"" >> $HOME/.bashrc'
sudo -u ubuntu -H -E bash -lc 'yes | $ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager --licenses'
sudo -u ubuntu -H -E bash -lc '$ANDROID_SDK_ROOT/cmdline-tools/latest/bin/sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"'

# Cleanup
apt-get clean
rm -rf /var/lib/apt/lists/*
rm -f "$ANDROID_TOOLS_ARCHIVE"
rm -rf /tmp/cmdline-tools
