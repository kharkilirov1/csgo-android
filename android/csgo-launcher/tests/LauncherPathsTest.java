package com.valvesoftware;

import java.io.File;
import java.nio.file.Files;

public final class LauncherPathsTest {
	private static void assertEquals(String expected, String actual) {
		if (!expected.equals(actual))
			throw new AssertionError("Expected " + expected + ", got " + actual);
	}

	public static void main(String[] args) throws Exception {
		File root = Files.createTempDirectory("csgo-launcher-paths").toFile();
		File mod = new File(root, "csgo");
		if (!mod.mkdir() || !new File(mod, "gameinfo.txt").createNewFile())
			throw new AssertionError("Failed to create path test fixture");

		String expectedRoot = root.getCanonicalPath();
		assertEquals(expectedRoot, LauncherPaths.resolveGameRoot(root.getPath(), "csgo"));
		assertEquals(expectedRoot, LauncherPaths.resolveGameRoot(mod.getPath(), "csgo"));
		assertEquals("/sdcard/srceng",
			LauncherPaths.normalizeSelectedPath("  /sdcard//srceng///  "));
		assertEquals("/", LauncherPaths.normalizeSelectedPath("///"));
		if (!LauncherPaths.hasGameInfo(mod))
			throw new AssertionError("Mod directory must expose gameinfo.txt");
	}
}
