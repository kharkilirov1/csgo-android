#!/bin/bash
set -e
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
mkdir -p "$HOME/.android"
chmod -R u+rwx "$HOME/.android" 2>/dev/null || true
export ANDROID_USER_HOME="$HOME/.android"
cd "$HOME/android-sdk"
# clean broken platform install
rm -rf platforms/android-35
cmdline-tools/latest/bin/sdkmanager --uninstall "platforms;android-35" 2>&1 | tail -2 || true
cmdline-tools/latest/bin/sdkmanager --install "platforms;android-35" 2>&1 | tail -4
echo "--- check ---"
ls -la platforms/android-35/ 2>/dev/null | head -8
ls platforms/android-35/android.jar 2>/dev/null && echo ANDROID_JAR_OK
