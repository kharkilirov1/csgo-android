package com.valvesoftware;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.ApplicationInfo;
import android.util.Log;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import com.valvesoftware.source.R;
import me.nillerusr.ExtractAssets;
import me.nillerusr.LauncherActivity;

public final class ValveActivity2 { // JNI bridge; intentionally not an Activity.
	public static final String EXTRA_ARGS = "argv";
	public static final String EXTRA_ENV = "env";
	public static final String EXTRA_GAME_PATH = "gamepath";
	private static final String EXTRA_BUNDLED_VPK_PATH = "bundled_vpk_path";
	private static final String EXTRA_STARTUP_ERROR = "startup_error";

	private static final String TAG = "SRCAPK";
	private static final String DEFAULT_GAME_DIR = "csgo";

	private ValveActivity2() {
	}

	public static native void setArgs(String args);
	public static native int setenv(String name, String value, int overwrite);

	private static String getGameDirectory(Intent intent) {
		String gameDirectory = intent.getStringExtra("gamedir");
		return gameDirectory == null || gameDirectory.trim().isEmpty()
			? DEFAULT_GAME_DIR : gameDirectory.trim();
	}

	/** Resolve either a selected content root or a directly selected csgo dir. */
	static String resolveGameRoot(Context context, Intent intent) {
		SharedPreferences preferences = context.getSharedPreferences("mod", 0);
		String selected = intent.getStringExtra(EXTRA_GAME_PATH);
		if (selected == null || selected.trim().isEmpty())
			selected = preferences.getString(EXTRA_GAME_PATH,
				LauncherActivity.getDefaultDir() + "/srceng");

		String gameDirectory = getGameDirectory(intent);
		File selectedFile = new File(selected.trim());
		if (LauncherPaths.hasGameInfo(selectedFile) &&
			selectedFile.getName().equalsIgnoreCase(gameDirectory)) {
			intent.putExtra("gamedir", selectedFile.getName());
		}

		String resolved = LauncherPaths.resolveGameRoot(selected, gameDirectory);
		intent.putExtra(EXTRA_GAME_PATH, resolved);
		preferences.edit().putString(EXTRA_GAME_PATH, resolved).apply();
		return resolved;
	}

	public static boolean preInit(Context context, Intent intent) {
		intent.removeExtra(EXTRA_STARTUP_ERROR);
		String gameRoot = resolveGameRoot(context, intent);
		File modDirectory = new File(gameRoot, getGameDirectory(intent));
		if (!LauncherPaths.hasGameInfo(modDirectory)) {
			intent.putExtra(EXTRA_STARTUP_ERROR,
				R.string.srceng_launcher_error_find_gameinfo);
			return false;
		}
		return prepareBundledExtras(context, intent) != null;
	}

	public static int getStartupErrorResource(Intent intent) {
		return intent.getIntExtra(EXTRA_STARTUP_ERROR,
			R.string.srceng_launcher_error_prepare_vpk);
	}

	private static File prepareBundledExtras(Context context, Intent intent) {
		String preparedPath = intent.getStringExtra(EXTRA_BUNDLED_VPK_PATH);
		if (preparedPath != null) {
			File prepared = new File(preparedPath);
			if (ExtractAssets.isValidVPK(prepared))
				return prepared;
		}

		File extracted = ExtractAssets.extractVPK(context, false);
		if (!ExtractAssets.isValidVPK(extracted)) {
			intent.removeExtra(EXTRA_BUNDLED_VPK_PATH);
			intent.putExtra(EXTRA_STARTUP_ERROR,
				R.string.srceng_launcher_error_prepare_vpk);
			return null;
		}

		intent.putExtra(EXTRA_BUNDLED_VPK_PATH,
			LauncherPaths.canonicalPath(extracted));
		return extracted;
	}

	private static String intentOrPreference(Intent intent, SharedPreferences preferences,
		String key, String defaultValue) {
		String value = intent.getStringExtra(key);
		return value == null ? preferences.getString(key, defaultValue) : value;
	}

	private static void applyUserEnvironment(Intent intent, SharedPreferences preferences) {
		String specification = intentOrPreference(intent, preferences, EXTRA_ENV,
			"LIBGL_USEVBO=0");
		try {
			for (LauncherEnvironment.Assignment assignment : LauncherEnvironment.parse(specification)) {
				setenv(assignment.name, assignment.value, 1);
				Log.i(TAG, "Applied environment variable " + assignment.name);
			}
		} catch (IllegalArgumentException error) {
			Log.e(TAG, "Invalid launcher environment: " + error.getMessage());
		}
	}

	private static void addExistingVPKs(List<String> output, String paths) {
		if (paths == null || paths.trim().isEmpty())
			return;

		for (String path : paths.split(",")) {
			File file = new File(path.trim());
			if (file.isFile())
				output.add(LauncherPaths.canonicalPath(file));
			else
				Log.w(TAG, "Ignoring missing VPK: " + path);
		}
	}

	private static String joinPaths(List<String> paths) {
		StringBuilder joined = new StringBuilder();
		for (String path : paths) {
			if (joined.length() > 0)
				joined.append(',');
			joined.append(path);
		}
		return joined.toString();
	}

	public static boolean initNatives(Context context, Intent intent) {
		SharedPreferences preferences = context.getSharedPreferences("mod", 0);
		ApplicationInfo applicationInfo = context.getApplicationInfo();
		String gameRoot = resolveGameRoot(context, intent);
		String gameDirectory = getGameDirectory(intent);
		String arguments = intentOrPreference(intent, preferences, EXTRA_ARGS, "-console");
		String gameLibraryDirectory = intent.getStringExtra("gamelibdir");
		File bundledExtras = prepareBundledExtras(context, intent);
		if (bundledExtras == null)
			return false;

		applyUserEnvironment(intent, preferences);
		if (gameLibraryDirectory != null && !gameLibraryDirectory.trim().isEmpty())
			setenv("APP_MOD_LIB", gameLibraryDirectory.trim(), 1);

		List<String> vpkPaths = new ArrayList<String>();
		addExistingVPKs(vpkPaths, intent.getStringExtra("vpk"));
		vpkPaths.add(LauncherPaths.canonicalPath(bundledExtras));

		String joinedVPKs = joinPaths(vpkPaths);
		Log.i(TAG, "Extra VPK count=" + vpkPaths.size());
		setenv("EXTRAS_VPK_PATH", joinedVPKs, 1);
		setenv("LANG", Locale.getDefault().toString(), 1);
		setenv("APP_DATA_PATH", applicationInfo.dataDir, 1);
		setenv("APP_LIB_PATH", applicationInfo.nativeLibraryDir, 1);
		setenv("VALVE_GAME_PATH", gameRoot, 1);

		arguments = "-game " + gameDirectory + " " + arguments;
		Log.i(TAG, "Launching game root=" + gameRoot + ", game=" + gameDirectory);
		setArgs(arguments);
		return true;
	}
}
