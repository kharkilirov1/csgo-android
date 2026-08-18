package com.valvesoftware;

import java.io.File;
import java.io.IOException;

/** Pure-Java path rules shared by the launcher bridge and host-side tests. */
public final class LauncherPaths {
	private LauncherPaths() {
	}

	public static boolean hasGameInfo(File directory) {
		return directory != null && new File(directory, "gameinfo.txt").isFile();
	}

	public static String canonicalPath(File path) {
		try {
			return path.getCanonicalPath();
		} catch (IOException ignored) {
			return path.getAbsolutePath();
		}
	}

	/** Keep user-visible Android paths stable and free of redundant separators. */
	public static String normalizeSelectedPath(String selected) {
		String normalized = selected == null ? "" : selected.trim().replaceAll("/{2,}", "/");
		while (normalized.length() > 1 && normalized.endsWith("/"))
			normalized = normalized.substring(0, normalized.length() - 1);
		return normalized;
	}

	/** Accept either the content root or the mod directory itself. */
	public static String resolveGameRoot(String selected, String gameDirectory) {
		File root = new File(normalizeSelectedPath(selected));
		if (hasGameInfo(root) && root.getName().equalsIgnoreCase(gameDirectory) &&
			root.getParentFile() != null) {
			root = root.getParentFile();
		}
		return canonicalPath(root);
	}
}
