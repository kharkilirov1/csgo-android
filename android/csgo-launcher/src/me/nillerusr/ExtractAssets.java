package me.nillerusr;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.file.AtomicMoveNotSupportedException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;

public final class ExtractAssets {
	public static final String VPK_NAME = "extras_dir.vpk";
	public static final int PAK_VERSION = 9;
	private static final byte[] VPK_SIGNATURE = {
		(byte)0x34, (byte)0x12, (byte)0xaa, (byte)0x55
	};

	private ExtractAssets() {
	}

	public static boolean isValidVPK(File file) {
		if (file == null || !file.isFile() || file.length() <= VPK_SIGNATURE.length)
			return false;

		byte[] signature = new byte[VPK_SIGNATURE.length];
		try (FileInputStream input = new FileInputStream(file)) {
			int offset = 0;
			while (offset < signature.length) {
				int count = input.read(signature, offset, signature.length - offset);
				if (count < 0)
					return false;
				offset += count;
			}
		} catch (Exception error) {
			return false;
		}

		for (int index = 0; index < signature.length; ++index) {
			if (signature[index] != VPK_SIGNATURE[index])
				return false;
		}
		return true;
	}

	/**
	 * Materializes the bundled VPK into app-private storage for the native
	 * filesystem. The returned path is a normal POSIX path that AddVPKFile can
	 * open; content:// URIs cannot be consumed by the Source filesystem.
	 */
	public static File extractVPK(Context context, boolean force) {
		SharedPreferences preferences = context.getSharedPreferences("mod", 0);
		File destination = new File(context.getFilesDir(), VPK_NAME);
		if (!force && isValidVPK(destination) &&
			preferences.getInt("pakversion", 0) == PAK_VERSION) {
			return destination;
		}

		File temporary = new File(context.getFilesDir(), VPK_NAME + ".tmp");
		try {
			try (InputStream input = context.getAssets().open(VPK_NAME);
				 FileOutputStream output = new FileOutputStream(temporary)) {
				byte[] buffer = new byte[64 * 1024];
				for (int length = input.read(buffer); length >= 0; length = input.read(buffer)) {
					if (length > 0)
						output.write(buffer, 0, length);
				}
				output.getFD().sync();
			}

			if (!isValidVPK(temporary))
				throw new IllegalStateException("Bundled extras VPK is invalid");

			try {
				Files.move(temporary.toPath(), destination.toPath(),
					StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
			} catch (AtomicMoveNotSupportedException unsupported) {
				Files.move(temporary.toPath(), destination.toPath(),
					StandardCopyOption.REPLACE_EXISTING);
			}
			if (!isValidVPK(destination))
				throw new IllegalStateException("Installed extras VPK is invalid");
			preferences.edit().putInt("pakversion", PAK_VERSION).apply();
			return destination;
		} catch (Exception error) {
			Log.e("SRCAPK", "Failed to extract " + VPK_NAME, error);
			temporary.delete();
			return null;
		}
	}
}
