#!/bin/bash
set -e
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_USER_HOME="$HOME/.android"
cd "$HOME/android-sdk"
cmdline-tools/latest/bin/sdkmanager --install "build-tools;34.0.0" 2>&1 | tail -3
echo BT34_DONE
ls build-tools/
