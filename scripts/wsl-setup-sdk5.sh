#!/bin/bash
set -e
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_USER_HOME="$HOME/.android"
sudo chown -R kharki:kharki "$HOME/android-sdk" 2>/dev/null || true
cd "$HOME/android-sdk"
rm -rf platforms/android-35
cmdline-tools/latest/bin/sdkmanager --install "platforms;android-35" 2>&1 | tail -3
echo "--- check ---"
ls platforms/android-35/android.jar 2>/dev/null && echo ANDROID_JAR_OK || echo JAR_MISSING
