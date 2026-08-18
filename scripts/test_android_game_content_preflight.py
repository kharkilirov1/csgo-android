#!/usr/bin/env python3
"""Compile and run the pure-Java external game-content preflight tests."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = (
    ROOT
    / "android/csgo-launcher/src/com/valvesoftware/GameContentValidator.java"
)
TEST = ROOT / "android/csgo-launcher/tests/GameContentValidatorTest.java"


def main() -> int:
    javac = shutil.which("javac")
    java = shutil.which("java")
    if not javac or not java:
        print("FAIL: javac and java are required for game-content preflight tests")
        return 1

    with tempfile.TemporaryDirectory(prefix="csgo-game-content-test-") as output:
        compile_result = subprocess.run(
            [
                javac,
                "--release",
                "8",
                "-encoding",
                "UTF-8",
                "-d",
                output,
                str(VALIDATOR),
                str(TEST),
            ],
            cwd=ROOT,
            check=False,
        )
        if compile_result.returncode != 0:
            return compile_result.returncode
        return subprocess.run(
            [java, "-cp", output, "com.valvesoftware.GameContentValidatorTest"],
            cwd=ROOT,
            check=False,
        ).returncode


if __name__ == "__main__":
    sys.exit(main())
