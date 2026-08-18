#!/bin/bash
set -e
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_NDK_HOME=/opt/android-ndk-r20b
export NDK_HOME=/opt/android-ndk-r20b
export ANDROID_HOME="$HOME/android-sdk"
export ANDROID_SDK_ROOT="$HOME/android-sdk"
export CSGO_VERSION_CODE=999
export CSGO_VERSION_NAME=0.1.0-arm64-preview.local
export GRADLE_USER_HOME="$HOME/csgo-src/.gradle"
export ANDROID_USER_HOME="$GRADLE_USER_HOME/android-user"
cd "$HOME/csgo-src"
bash scripts/build-apk-aarch64.sh 2>&1 | tail -12
echo APK_DONE
