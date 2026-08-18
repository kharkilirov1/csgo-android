#!/bin/bash
set -e
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_USER_HOME="$HOME/.android"
cd "$HOME/android-sdk"
yes | cmdline-tools/latest/bin/sdkmanager --licenses >/dev/null 2>&1 || true
cmdline-tools/latest/bin/sdkmanager --install "platforms;android-35" "build-tools;35.0.0" 2>&1 | tail -5
echo SDK_DONE
ls build-tools/ platforms/
