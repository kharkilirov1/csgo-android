#!/usr/bin/env bash
set -euo pipefail

cd /home/kharki/csgo-src
tmp_key="$(mktemp -d /tmp/csgo-release-key.XXXXXX)"
cleanup_key() {
  rm -rf "$tmp_key"
}
trap cleanup_key EXIT

password="$(head -c 48 /dev/urandom | base64 | tr -d '\n/=+' | head -c 32)"
keystore="$tmp_key/rc.p12"
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
keytool -genkeypair -noprompt -storetype PKCS12 -keystore "$keystore" \
  -storepass "$password" -keypass "$password" -alias rc \
  -dname 'CN=CSGO Android Ephemeral RC,O=Local Verification,C=US' \
  -keyalg RSA -keysize 3072 -validity 30 >/dev/null 2>&1
keytool -exportcert -keystore "$keystore" -storepass "$password" \
  -alias rc -file "$tmp_key/cert.der" >/dev/null 2>&1
read -r cert _ < <(sha256sum "$tmp_key/cert.der")
test -n "$cert"

export ANDROID_NDK_HOME=/opt/android-ndk-r20b
export NDK_HOME=/opt/android-ndk-r20b
export ANDROID_HOME=/home/kharki/android-sdk
export ANDROID_SDK_ROOT=/home/kharki/android-sdk
export CSGO_BUILD_VARIANT=release
export CSGO_VERSION_CODE=1029
export CSGO_VERSION_NAME=0.1.0-rc.1029.local
export CSGO_RELEASE_KEYSTORE="$keystore"
export CSGO_RELEASE_KEYSTORE_PASSWORD="$password"
export CSGO_RELEASE_KEY_ALIAS=rc
export CSGO_RELEASE_KEY_PASSWORD="$password"
export CSGO_RELEASE_CERT_SHA256="$cert"
export GRADLE_USER_HOME=/home/kharki/csgo-src/.gradle
export ANDROID_USER_HOME=/home/kharki/csgo-src/.gradle/android-user

bash scripts/build-apk-aarch64.sh >/tmp/csgo-release-1029.log 2>&1
apk=android/csgo-launcher/app/build/outputs/apk/release/app-release.apk
test -f "$apk"
grep -q 'Release APK verified:' /tmp/csgo-release-1029.log
cp "$apk" /mnt/c/Users/Kharki/AppData/Local/Temp/csgo-release-1029.apk
printf '%s\n' "$cert" >/tmp/csgo-release-1029.cert
sha256sum "$apk" >/tmp/csgo-release-1029.sha256
sync
