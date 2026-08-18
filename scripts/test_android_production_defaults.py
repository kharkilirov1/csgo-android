#!/usr/bin/env python3
"""Keep the Android launcher on production-safe first-run defaults."""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "android/csgo-launcher/src/me/nillerusr/LauncherActivity.java"
VALVE_ACTIVITY = ROOT / "android/csgo-launcher/src/com/valvesoftware/ValveActivity2.java"
LAYOUT = ROOT / "android/csgo-launcher/res/layout/activity_launcher.xml"


def main() -> int:
    launcher = LAUNCHER.read_text(encoding="utf-8", errors="replace")
    valve_activity = VALVE_ACTIVITY.read_text(encoding="utf-8", errors="replace")
    layout = LAYOUT.read_text(encoding="utf-8", errors="replace")

    failures = []
    if 'mPref.getString("argv", "")' not in launcher:
        failures.append("LauncherActivity must default argv to an empty string")
    if 'PREF_PRODUCTION_ARGS_MIGRATED' not in launcher:
        failures.append("LauncherActivity must version the legacy -console migration")
    if '!mPref.getBoolean(PREF_PRODUCTION_ARGS_MIGRATED, false)' not in launcher:
        failures.append("LauncherActivity must run the legacy argv migration once")
    if '"-console".equals(arguments.trim())' not in launcher:
        failures.append("LauncherActivity must clear the former -console default on upgrade")
    if 'putBoolean(PREF_PRODUCTION_ARGS_MIGRATED, true)' not in launcher:
        failures.append("LauncherActivity must persist completion of the argv migration")
    if 'intentOrPreference(intent, preferences, EXTRA_ARGS, "")' not in valve_activity:
        failures.append("ValveActivity2 must default startup arguments to an empty string")
    if 'android:text="-console"' in layout:
        failures.append("launcher layout must not prefill -console")
    if 'android:layout_marginBottom="400dp"' in layout:
        failures.append("launcher layout must not contain the temporary 400dp footer offset")

    if failures:
        print("FAIL: Android launcher still has diagnostic/development defaults")
        print("\n".join(failures))
        return 1

    print("PASS: Android launcher uses production-safe defaults")
    return 0


if __name__ == "__main__":
    sys.exit(main())
