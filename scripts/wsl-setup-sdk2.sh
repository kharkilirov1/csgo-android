#!/bin/bash
set -e
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_USER_HOME="$HOME/.android"
cd "$HOME/android-sdk"
cmdline-tools/latest/bin/sdkmanager --install "platforms;android-35" 2>&1 | tail -8
echo PLATFORM_DONE
ls platforms/ 2>/dev/null || echo NO_PLATFORMS
