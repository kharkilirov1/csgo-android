#!/bin/bash
set -e
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
export ANDROID_NDK_HOME=/opt/android-ndk-r20b
export NDK_HOME=/opt/android-ndk-r20b
export ANDROID_HOME="$HOME/android-sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export GRADLE_USER_HOME="$HOME/csgo-src/.gradle"
export ANDROID_USER_HOME="$GRADLE_USER_HOME/android-user"
cd "$HOME/csgo-src/android/csgo-launcher"
printf 'sdk.dir=%s\n' "$ANDROID_HOME" > local.properties
cat local.properties
bash ./gradlew --no-daemon --stacktrace assembleDebug 2>&1 | tail -25
echo GRADLE_DONE
APK="$HOME/csgo-src/android/csgo-launcher/app/build/outputs/apk/debug/app-debug.apk"
ls -la "$APK" 2>/dev/null && echo APK_EXISTS
