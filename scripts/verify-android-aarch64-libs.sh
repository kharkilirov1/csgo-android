#!/bin/sh
# Validate the native payload before Gradle can hide packaging mistakes in an
# otherwise installable APK.

set -eu

SRC=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
. "$SRC/scripts/android-aarch64-common.sh"

JNI=${1:-"$SRC/android/csgo-launcher/jniLibs/arm64-v8a"}
READELF=${READELF:-readelf}

if [ ! -d "$JNI" ]; then
	echo "error: native library directory does not exist: $JNI" >&2
	exit 1
fi

if ! command -v "$READELF" >/dev/null 2>&1; then
	echo "error: readelf is required to validate the native payload" >&2
	exit 1
fi

failed=0
rm -f "$JNI/.dependency-errors"

for library in $ANDROID_REQUIRED_LIBRARIES; do
	if [ ! -f "$JNI/$library" ]; then
		echo "error: missing required Android runtime module: $library" >&2
		failed=1
	fi
done

if [ "$failed" -ne 0 ]; then
	exit "$failed"
fi

for shared_object in "$JNI"/*.so; do
	library=$(basename "$shared_object")
	if ! android_is_required_library "$library"; then
		echo "error: undeclared Android runtime module: $library" >&2
		failed=1
	fi

	if ! elf_header=$("$READELF" -h "$shared_object" 2>/dev/null); then
		echo "error: $library is not a readable ELF shared object" >&2
		failed=1
		continue
	fi

	elf_class=$(printf '%s\n' "$elf_header" | sed -n 's/^[[:space:]]*Class:[[:space:]]*//p')
	if [ "$elf_class" != "ELF64" ]; then
		echo "error: $library is not ELF64 (Class: ${elf_class:-unknown})" >&2
		failed=1
	fi

	elf_data=$(printf '%s\n' "$elf_header" | sed -n 's/^[[:space:]]*Data:[[:space:]]*//p')
	case "$elf_data" in
		*little\ endian*) ;;
		*)
			echo "error: $library is not little-endian (Data: ${elf_data:-unknown})" >&2
			failed=1
			;;
	esac

	elf_type=$(printf '%s\n' "$elf_header" | sed -n 's/^[[:space:]]*Type:[[:space:]]*//p')
	case "$elf_type" in
		DYN*) ;;
		*)
			echo "error: $library is not ET_DYN (Type: ${elf_type:-unknown})" >&2
			failed=1
			;;
	esac

	machine=$(printf '%s\n' "$elf_header" | sed -n 's/^[[:space:]]*Machine:[[:space:]]*//p')
	case "$machine" in
		AArch64*) ;;
		*)
			echo "error: $library is not AArch64 (Machine: ${machine:-unknown})" >&2
			failed=1
			;;
	esac

	soname=$("$READELF" -d "$shared_object" 2>/dev/null |
		sed -n 's/.*(SONAME).*\[\([^]]*\)\].*/\1/p')
	if [ "$soname" != "$library" ]; then
		echo "error: $library has wrong or missing SONAME (${soname:-none})" >&2
		failed=1
	fi

	if "$READELF" -d "$shared_object" 2>/dev/null |
		grep -Eq '\(TEXTREL\)|FLAGS[^]]*TEXTREL'; then
		echo "error: $library contains text relocations" >&2
		failed=1
	fi

	stack_flags=$("$READELF" -lW "$shared_object" 2>/dev/null |
		awk '$1 == "GNU_STACK" { print $(NF - 1) }')
	if [ -z "$stack_flags" ]; then
		echo "error: $library has no GNU_STACK program header" >&2
		failed=1
	else
		case "$stack_flags" in
			*E*)
				echo "error: $library requests an executable stack ($stack_flags)" >&2
				failed=1
				;;
		esac
	fi

	load_alignments=$("$READELF" -lW "$shared_object" 2>/dev/null |
		awk '$1 == "LOAD" { print $NF }')
	if [ -z "$load_alignments" ]; then
		echo "error: $library has no ELF LOAD segments" >&2
		failed=1
	else
		for alignment in $load_alignments; do
			case "$alignment" in
				0x[0-9a-fA-F]*) alignment_value=$((alignment)) ;;
				*) alignment_value=0 ;;
			esac
			if [ "$alignment_value" -lt 16384 ]; then
				echo "error: $library LOAD alignment $alignment is below 16 KiB" >&2
				failed=1
				break
			fi
		done
	fi

	"$READELF" -d "$shared_object" 2>/dev/null |
		sed -n 's/.*Shared library: \[\([^]]*\)\].*/\1/p' |
		while IFS= read -r dependency; do
			if [ -f "$JNI/$dependency" ] || android_is_system_library "$dependency"; then
				continue
			fi
			echo "error: $library needs unpackaged dependency $dependency" >&2
			echo "$library -> $dependency" >> "$JNI/.dependency-errors"
		done
done

if [ -s "$JNI/.dependency-errors" ]; then
	failed=1
fi
rm -f "$JNI/.dependency-errors"

for interface_library in $ANDROID_REQUIRED_LIBRARIES; do
	case "$interface_library" in
		libSDL2.so|libc++_shared.so|libtier0.so|libsteam_api.so) continue ;;
	esac
	if ! "$READELF" -Ws "$JNI/$interface_library" 2>/dev/null |
		awk '$8 == "CreateInterface" && $7 != "UND" { found=1 } END { exit !found }'; then
		echo "error: $interface_library does not export CreateInterface" >&2
		failed=1
	fi
done

for launcher_export in \
	LauncherMainAndroid \
	Java_com_valvesoftware_ValveActivity2_setenv \
	Java_com_valvesoftware_ValveActivity2_setArgs \
	Java_com_valvesoftware_ValveActivity2_nativeOnActivityResult
do
	if ! "$READELF" -Ws "$JNI/liblauncher.so" 2>/dev/null |
		awk -v symbol="$launcher_export" \
		'$8 == symbol && $7 != "UND" { found=1 } END { exit !found }'; then
		echo "error: liblauncher.so does not export $launcher_export" >&2
		failed=1
	fi
done

for sdl_export in \
	Java_org_libsdl_app_SDLActivity_nativeSetupJNI \
	Java_org_libsdl_app_SDLActivity_nativeRunMain \
	Java_org_libsdl_app_SDLAudioManager_nativeSetupJNI \
	Java_org_libsdl_app_SDLControllerManager_nativeSetupJNI
do
	if ! "$READELF" -Ws "$JNI/libSDL2.so" 2>/dev/null |
		awk -v symbol="$sdl_export" \
		'$8 == symbol && $7 != "UND" { found=1 } END { exit !found }'; then
		echo "error: libSDL2.so does not export $sdl_export" >&2
		failed=1
	fi
done

if [ "$failed" -ne 0 ]; then
	exit "$failed"
fi

library_count=$(printf '%s\n' $ANDROID_REQUIRED_LIBRARIES | wc -l | tr -d ' ')
echo "Native payload verified: $library_count AArch64 libraries"
