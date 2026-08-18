package com.valvesoftware;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.zip.CRC32;

/**
 * Validates the user-supplied CS:GO weapon scripts before native startup.
 *
 * The launcher intentionally does not ship Valve game data.  This class only
 * indexes loose files and standard VPKs already present below the selected mod
 * directory; it never downloads, extracts, or repairs proprietary content.
 */
public final class GameContentValidator {
	private static final String WEAPON_MANIFEST = "scripts/weapon_manifest.txt";
	private static final String REQUIRED_WEAPON = "weapon_healthshot";
	private static final String REFERENCE_GAME_VERSION = "1.36.0.2";
	private static final String CONTRACT_SHA256 =
		"3d0463a142e614a1cd79cde97b470e538ea111bc2a11501a925b86306ae6051e";
	private static final String[] CONTRACT_WEAPONS = {
		"weapon_ak47", "weapon_aug", "weapon_awp", "weapon_bizon", "weapon_c4",
		"weapon_deagle", "weapon_decoy", "weapon_elite", "weapon_famas",
		"weapon_fiveseven", "weapon_flashbang", "weapon_g3sg1", "weapon_galilar",
		"weapon_glock", "weapon_healthshot", "weapon_hegrenade", "weapon_hkp2000",
		"weapon_incgrenade", "weapon_knife", "weapon_knifegg", "weapon_m249",
		"weapon_m4a1", "weapon_mac10", "weapon_mag7", "weapon_molotov",
		"weapon_mp7", "weapon_mp9", "weapon_negev", "weapon_nova", "weapon_p250",
		"weapon_p90", "weapon_sawedoff", "weapon_scar20", "weapon_sg556",
		"weapon_smokegrenade", "weapon_ssg08", "weapon_tagrenade", "weapon_taser",
		"weapon_tec9", "weapon_ump45", "weapon_xm1014"
	};
	private static final Set<String> CONTRACT_WEAPON_SET = Collections.unmodifiableSet(
		new LinkedHashSet<String>(Arrays.asList(CONTRACT_WEAPONS)));
	private static final String COMPUTED_CONTRACT_SHA256 =
		computeContractSha256(CONTRACT_WEAPON_SET);

	static {
		if (!CONTRACT_SHA256.equals(COMPUTED_CONTRACT_SHA256))
			throw new IllegalStateException("Android game-content contract digest mismatch");
	}
	private static final int MAX_MANIFEST_BYTES = 1024 * 1024;
	private static final int MAX_WEAPON_SCRIPT_BYTES = 8 * 1024 * 1024;
	private static final int MAX_KEYVALUES_DEPTH = 64;
	private static final int MAX_VPK_TREE_BYTES = 64 * 1024 * 1024;
	private static final long VPK_SIGNATURE = 0x55AA1234L;
	private static final int VPK_INLINE_ARCHIVE = 0x7FFF;
	private static final int VPK_ENTRY_TERMINATOR = 0xFFFF;
	private static final int VPK_ARCHIVE_MD5_ENTRY_BYTES = 28;
	private static final int VPK_SELF_HASH_BYTES = 48;
	private static final SecureRandom TOKEN_RANDOM = new SecureRandom();
	private static final Object PREPARED_VALIDATION_LOCK = new Object();
	private static String preparedValidationPath;
	private static String preparedValidationFingerprint;
	private static String preparedValidationToken;
	private static Result preparedValidationResult;

	public enum Status {
		OK,
		INVALID_CONTENT_ARCHIVE,
		UNSUPPORTED_AUTOMATIC_OVERLAY,
		MISSING_WEAPON_MANIFEST,
		INVALID_WEAPON_MANIFEST,
		MISSING_REQUIRED_WEAPON_SCRIPT,
		INCOMPATIBLE_WEAPON_MANIFEST,
		MISSING_LISTED_WEAPON_SCRIPT,
		INVALID_LISTED_WEAPON_SCRIPT
	}

	public static final class Result {
		private final Status status;
		private final String diagnostic;
		private final int weaponScriptCount;
		private final String validatedCanonicalPath;
		private final String validatedFingerprint;

		private Result(Status status, String diagnostic, int weaponScriptCount,
			String validatedCanonicalPath, String validatedFingerprint) {
			this.status = status;
			this.diagnostic = diagnostic;
			this.weaponScriptCount = weaponScriptCount;
			this.validatedCanonicalPath = validatedCanonicalPath;
			this.validatedFingerprint = validatedFingerprint;
		}

		public boolean isValid() {
			return status == Status.OK;
		}

		public Status getStatus() {
			return status;
		}

		public String getDiagnostic() {
			return diagnostic;
		}

		public int getWeaponScriptCount() {
			return weaponScriptCount;
		}
	}

	private static final class ContentIndex {
		private final File modDirectory;
		private final List<VpkIndex> vpks = new ArrayList<VpkIndex>();
		private final List<String> rejectedVpks = new ArrayList<String>();

		ContentIndex(File modDirectory) {
			this.modDirectory = modDirectory;
			File[] candidates = modDirectory == null ? null : modDirectory.listFiles();
			if (candidates == null)
				return;
			Map<String, File> exactFiles = new LinkedHashMap<String, File>();
			for (File candidate : candidates) {
				if (candidate.isFile())
					exactFiles.put(candidate.getName(), candidate);
			}
			// CBaseFileSystem::AddSearchPath scans pak01..pak98 and stops at the
			// first gap.  Do not accidentally validate backup/addon VPKs that the
			// Android native path will never mount.
			for (int index = 1; index < 99; ++index) {
				String name = String.format(Locale.ROOT, "pak%02d_dir.vpk", index);
				File candidate = exactFiles.get(name);
				if (candidate == null)
					break;
				try {
					vpks.add(VpkIndex.open(candidate));
				} catch (IOException error) {
					rejectedVpks.add(candidate.getName() + " (" + error.getMessage() + ")");
					break;
				}
			}
		}

		byte[] read(String resourcePath, int maximumBytes) {
			if (modDirectory == null || !modDirectory.isDirectory())
				return null;
			String normalized = normalizeResourcePath(resourcePath);
			if (normalized == null)
				return null;
			// FindFile() checks mounted VPKs before loose search paths.
			for (VpkIndex vpk : vpks) {
				VpkEntry entry = vpk.entries.get(normalized);
				if (entry == null)
					continue;
				try {
					return entry.read(maximumBytes);
				} catch (IOException ignored) {
					return null;
				}
			}
			File loose = new File(modDirectory, normalized.replace('/', File.separatorChar));
			return readLoose(loose, maximumBytes);
		}

		boolean contains(String resourcePath) {
			if (modDirectory == null || !modDirectory.isDirectory())
				return false;
			String normalized = normalizeResourcePath(resourcePath);
			if (normalized == null)
				return false;
			for (VpkIndex vpk : vpks) {
				if (vpk.entries.containsKey(normalized))
					return true;
			}
			return new File(modDirectory,
				normalized.replace('/', File.separatorChar)).isFile();
		}

		String rejectedVpkSummary() {
			if (rejectedVpks.isEmpty())
				return "";
			return "; unreadable VPK indexes: " + join(rejectedVpks, ", ");
		}

		boolean hasRejectedVpks() {
			return !rejectedVpks.isEmpty();
		}
	}

	private static final class VpkIndex {
		final Map<String, VpkEntry> entries;

		VpkIndex(Map<String, VpkEntry> entries) {
			this.entries = entries;
		}

		static VpkIndex open(File directoryVpk) throws IOException {
			try (RandomAccessFile input = new RandomAccessFile(directoryVpk, "r")) {
				long fileLength = input.length();
				if (fileLength < 12)
					throw new IOException("truncated header");
				if (readU32(input) != VPK_SIGNATURE)
					throw new IOException("wrong signature");
				long version = readU32(input);
				if (version != 1 && version != 2)
					throw new IOException("unsupported version " + version);
				long treeSize = readU32(input);
				long fileDataSize;
				long archiveMd5Size = 0;
				long otherMd5Size = 0;
				long signatureSize = 0;
				int headerSize;
				if (version == 2) {
					if (fileLength < 28)
						throw new IOException("truncated v2 header");
					fileDataSize = readU32(input);
					archiveMd5Size = readU32(input);
					otherMd5Size = readU32(input);
					signatureSize = readU32(input);
					headerSize = 28;
				} else {
					fileDataSize = fileLength - 12 - treeSize;
					headerSize = 12;
				}
				if (treeSize <= 0 || treeSize > MAX_VPK_TREE_BYTES ||
					treeSize > Integer.MAX_VALUE || treeSize > fileLength - headerSize)
					throw new IOException("invalid directory tree size " + treeSize);
				long inlineDataStart = checkedAdd(headerSize, treeSize,
					"directory tree end");
				if (fileDataSize < 0 || fileDataSize > fileLength - inlineDataStart)
					throw new IOException("invalid inline data size " + fileDataSize);
				if (version == 2) {
					if (archiveMd5Size % VPK_ARCHIVE_MD5_ENTRY_BYTES != 0)
						throw new IOException("invalid archive MD5 section size " + archiveMd5Size);
					if (otherMd5Size != 0 && otherMd5Size != VPK_SELF_HASH_BYTES)
						throw new IOException("invalid self-hash section size " + otherMd5Size);
					if (signatureSize != 0 && signatureSize < 8)
						throw new IOException("truncated signature section");

					long expectedLength = checkedAdd(inlineDataStart, fileDataSize,
						"inline data end");
					expectedLength = checkedAdd(expectedLength, archiveMd5Size,
						"archive MD5 section end");
					expectedLength = checkedAdd(expectedLength, otherMd5Size,
						"self-hash section end");
					long signatureStart = expectedLength;
					expectedLength = checkedAdd(expectedLength, signatureSize,
						"signature section end");
					if (expectedLength != fileLength)
						throw new IOException("v2 section sizes do not match file length");
					validateSignatureSection(input, signatureStart, signatureSize);
				}

				byte[] tree = new byte[(int)treeSize];
				input.seek(headerSize);
				input.readFully(tree);
				Cursor cursor = new Cursor(tree);
				Map<String, VpkEntry> entries = new LinkedHashMap<String, VpkEntry>();
				Set<String> extensionGroups = new LinkedHashSet<String>();
				while (true) {
					String extension = cursor.readString();
					if (extension.length() == 0)
						break;
					if (!extensionGroups.add(extension))
						throw new IOException("duplicate extension group " + extension);
					Set<String> directoryGroups = new LinkedHashSet<String>();
					while (true) {
						String directory = cursor.readString();
						if (directory.length() == 0)
							break;
						if (!directoryGroups.add(directory))
							throw new IOException("duplicate directory group " + directory +
								" in extension " + extension);
						while (true) {
							String stem = cursor.readString();
							if (stem.length() == 0)
								break;
							long crc32 = cursor.readU32();
							int preloadLength = cursor.readU16();
							int archiveIndex = cursor.readU16();
							if (archiveIndex == VPK_ENTRY_TERMINATOR)
								throw new IOException("reserved archive index 0xffff");
							long offset = cursor.readU32();
							long length = cursor.readU32();
							if (cursor.readU16() != VPK_ENTRY_TERMINATOR)
								throw new IOException("wrong entry terminator");
							String rawPath = (" ".equals(directory) ? "" : directory + "/") +
								stem + (" ".equals(extension) ? "" : "." + extension);
							String path = normalizeResourcePath(rawPath);
							if (path == null)
								throw new IOException("unsafe entry path " + rawPath);
							boolean required = isContractResourcePath(path);
							if (required && !rawPath.equals(path))
								throw new IOException("noncanonical contract entry path " + rawPath);
							byte[] preload = required ? cursor.readBytes(preloadLength) : null;
							if (!required)
								cursor.skip(preloadLength);
							if (required) {
								if (entries.containsKey(path))
									throw new IOException("duplicate contract entry path " + rawPath);
								entries.put(path, new VpkEntry(directoryVpk, inlineDataStart,
									fileDataSize, archiveIndex, offset, length, preload, crc32));
							}
						}
					}
				}
				if (!cursor.atEnd())
					throw new IOException("unexpected bytes after directory tree");
				return new VpkIndex(entries);
			}
		}
	}

	private static long checkedAdd(long left, long right, String field)
		throws IOException {
		if (left < 0 || right < 0 || left > Long.MAX_VALUE - right)
			throw new IOException("overflow computing " + field);
		return left + right;
	}

	private static void validateSignatureSection(RandomAccessFile input,
		long signatureStart, long signatureSize) throws IOException {
		if (signatureSize == 0)
			return;
		input.seek(signatureStart);
		long publicKeySize = readU32(input);
		if (publicKeySize == 0 || publicKeySize > signatureSize - 8)
			throw new IOException("invalid VPK public-key size " + publicKeySize);
		long signatureLengthOffset = checkedAdd(signatureStart,
			checkedAdd(4, publicKeySize, "VPK public-key end"),
			"VPK signature length offset");
		input.seek(signatureLengthOffset);
		long encodedSignatureSize = readU32(input);
		long encodedSectionSize = checkedAdd(8,
			checkedAdd(publicKeySize, encodedSignatureSize, "VPK signature payload"),
			"VPK signature section");
		if (encodedSignatureSize == 0 || encodedSectionSize != signatureSize)
			throw new IOException("invalid VPK signature payload size " +
				encodedSignatureSize);
	}

	private static final class VpkEntry {
		final File directoryVpk;
		final long inlineDataStart;
		final long inlineDataSize;
		final int archiveIndex;
		final long offset;
		final long length;
		final byte[] preload;
		final long crc32;

		VpkEntry(File directoryVpk, long inlineDataStart, long inlineDataSize,
			int archiveIndex, long offset, long length, byte[] preload, long crc32) {
			this.directoryVpk = directoryVpk;
			this.inlineDataStart = inlineDataStart;
			this.inlineDataSize = inlineDataSize;
			this.archiveIndex = archiveIndex;
			this.offset = offset;
			this.length = length;
			this.preload = preload;
			this.crc32 = crc32;
		}

		byte[] read(int maximumBytes) throws IOException {
			long totalLength = preload.length + length;
			if (totalLength <= 0 || totalLength > maximumBytes || totalLength > Integer.MAX_VALUE)
				return null;
			File dataFile;
			long dataOffset;
			if (archiveIndex == VPK_INLINE_ARCHIVE) {
				if (offset + length > inlineDataSize)
					return null;
				dataFile = directoryVpk;
				dataOffset = inlineDataStart + offset;
			} else {
				String name = directoryVpk.getName();
				String suffix = "_dir.vpk";
				if (!name.toLowerCase(Locale.ROOT).endsWith(suffix))
					return null;
				String base = name.substring(0, name.length() - suffix.length());
				dataFile = new File(directoryVpk.getParentFile(),
					String.format(Locale.ROOT, "%s_%03d.vpk", base, archiveIndex));
				dataOffset = offset;
			}
			if (!dataFile.isFile() || dataOffset < 0 || length < 0 ||
				dataOffset > dataFile.length() || length > dataFile.length() - dataOffset)
				return null;

			byte[] output = new byte[(int)totalLength];
			System.arraycopy(preload, 0, output, 0, preload.length);
			try (RandomAccessFile input = new RandomAccessFile(dataFile, "r")) {
				input.seek(dataOffset);
				input.readFully(output, preload.length, (int)length);
			}
			CRC32 actual = new CRC32();
			actual.update(output);
			return actual.getValue() == crc32 ? output : null;
		}
	}

	private static final class Cursor {
		final byte[] data;
		int position;

		Cursor(byte[] data) {
			this.data = data;
		}

		boolean atEnd() {
			return position == data.length;
		}

		String readString() throws IOException {
			int start = position;
			while (position < data.length && data[position] != 0)
				++position;
			if (position >= data.length)
				throw new IOException("unterminated directory string");
			String value = new String(data, start, position - start,
				StandardCharsets.ISO_8859_1);
			++position;
			return value;
		}

		int readU16() throws IOException {
			ensureAvailable(2);
			int value = (data[position] & 0xff) | ((data[position + 1] & 0xff) << 8);
			position += 2;
			return value;
		}

		long readU32() throws IOException {
			ensureAvailable(4);
			long value = (data[position] & 0xffL) |
				((data[position + 1] & 0xffL) << 8) |
				((data[position + 2] & 0xffL) << 16) |
				((data[position + 3] & 0xffL) << 24);
			position += 4;
			return value;
		}

		byte[] readBytes(int count) throws IOException {
			ensureAvailable(count);
			byte[] value = Arrays.copyOfRange(data, position, position + count);
			position += count;
			return value;
		}

		void skip(int count) throws IOException {
			ensureAvailable(count);
			position += count;
		}

		void ensureAvailable(int count) throws IOException {
			if (count < 0 || position > data.length - count)
				throw new IOException("truncated directory tree");
		}
	}

	private GameContentValidator() {
	}

	public static String getContractSha256() {
		return COMPUTED_CONTRACT_SHA256;
	}

	/**
	 * Stores a successful worker-thread result behind a random process-local
	 * capability.  The capability is also bound to the canonical mod path, so
	 * copying an Intent token to another content root cannot authorize it.
	 */
	static String rememberSuccessfulValidation(File modDirectory, Result result) {
		if (result == null || !result.isValid())
			return null;
		String canonicalPath = canonicalDirectoryPath(modDirectory);
		String fingerprint = contentMetadataFingerprint(modDirectory);
		if (canonicalPath == null || fingerprint == null ||
			!canonicalPath.equals(result.validatedCanonicalPath) ||
			!fingerprint.equals(result.validatedFingerprint))
			return null;
		byte[] random = new byte[32];
		TOKEN_RANDOM.nextBytes(random);
		String token = hexadecimal(random);
		synchronized (PREPARED_VALIDATION_LOCK) {
			preparedValidationPath = canonicalPath;
			preparedValidationFingerprint = fingerprint;
			preparedValidationToken = token;
			preparedValidationResult = result;
		}
		return token;
	}

	/** Returns the cached result only when both the path and capability match. */
	static Result findPreparedValidation(File modDirectory, String token) {
		if (token == null)
			return null;
		String canonicalPath = canonicalDirectoryPath(modDirectory);
		String fingerprint = contentMetadataFingerprint(modDirectory);
		if (canonicalPath == null || fingerprint == null)
			return null;
		synchronized (PREPARED_VALIDATION_LOCK) {
			if (!canonicalPath.equals(preparedValidationPath) ||
				!fingerprint.equals(preparedValidationFingerprint) ||
				preparedValidationToken == null ||
				!MessageDigest.isEqual(token.getBytes(StandardCharsets.UTF_8),
					preparedValidationToken.getBytes(StandardCharsets.UTF_8)))
				return null;
			return preparedValidationResult;
		}
	}

	private static String canonicalDirectoryPath(File directory) {
		if (directory == null)
			return null;
		try {
			return directory.getCanonicalPath();
		} catch (IOException ignored) {
			return null;
		}
	}

	/**
	 * Cheap UI-safe metadata snapshot.  It stats the native automatic-overlay
	 * state, canonical pak sequence, and fixed weapon-script closure; it never
	 * reads VPK or script payloads.
	 */
	private static String contentMetadataFingerprint(File modDirectory) {
		if (modDirectory == null || !modDirectory.isDirectory())
			return null;
		try {
			MessageDigest digest = MessageDigest.getInstance("SHA-256");
			updateAutomaticOverlayMetadataDigest(digest, modDirectory);
			updateMetadataDigest(digest, "gameinfo.txt",
				new File(modDirectory, "gameinfo.txt"));
			File[] rootFiles = modDirectory.listFiles();
			if (rootFiles == null)
				return null;
			Map<String, File> exactFiles = new LinkedHashMap<String, File>();
			for (File file : rootFiles) {
				if (file.isFile())
					exactFiles.put(file.getName(), file);
			}
			for (int index = 1; index < 99; ++index) {
				String base = String.format(Locale.ROOT, "pak%02d", index);
				File directoryVpk = exactFiles.get(base + "_dir.vpk");
				if (directoryVpk == null)
					break;
				updateMetadataDigest(digest, base + "_dir.vpk", directoryVpk);
				List<String> chunks = new ArrayList<String>();
				for (String name : exactFiles.keySet()) {
					if (isCanonicalExternalChunk(base, name))
						chunks.add(name);
				}
				Collections.sort(chunks);
				for (String chunk : chunks)
					updateMetadataDigest(digest, chunk, exactFiles.get(chunk));
			}
			updateMetadataDigest(digest, WEAPON_MANIFEST,
				new File(modDirectory, WEAPON_MANIFEST.replace('/', File.separatorChar)));
			for (String weapon : CONTRACT_WEAPONS) {
				String base = "scripts/" + weapon;
				updateMetadataDigest(digest, base + ".txt", new File(modDirectory,
					(base + ".txt").replace('/', File.separatorChar)));
				updateMetadataDigest(digest, base + ".ctx", new File(modDirectory,
					(base + ".ctx").replace('/', File.separatorChar)));
			}
			return hexadecimal(digest.digest());
		} catch (NoSuchAlgorithmException impossible) {
			throw new IllegalStateException("SHA-256 is unavailable", impossible);
		}
	}

	/** Mirrors the automatic sibling search paths in basefilesystem.cpp. */
	private static File mountedAutomaticOverlay(File modDirectory) {
		File parent = modDirectory == null ? null : modDirectory.getParentFile();
		if (parent == null)
			return null;

		File overlay = new File(parent, "xlsppatch");
		if (overlay.exists())
			return overlay;
		overlay = new File(parent, "update");
		if (overlay.exists())
			return overlay;

		for (int index = 1; index <= 99; ++index) {
			overlay = new File(parent, "csgo_dlc" + index);
			if (!overlay.exists())
				break;
			if (new File(overlay, "dlc_disabled.txt").exists())
				break;
			return overlay;
		}
		return null;
	}

	private static void updateAutomaticOverlayMetadataDigest(MessageDigest digest,
		File modDirectory) {
		File parent = modDirectory.getParentFile();
		if (parent == null)
			return;
		updatePathMetadataDigest(digest, "overlay/xlsppatch",
			new File(parent, "xlsppatch"));
		updatePathMetadataDigest(digest, "overlay/update", new File(parent, "update"));
		for (int index = 1; index <= 99; ++index) {
			String label = "overlay/csgo_dlc" + index;
			File dlc = new File(parent, "csgo_dlc" + index);
			updatePathMetadataDigest(digest, label, dlc);
			if (!dlc.exists())
				break;
			File disabled = new File(dlc, "dlc_disabled.txt");
			updatePathMetadataDigest(digest, label + "/dlc_disabled.txt", disabled);
			if (disabled.exists())
				break;
		}
	}

	private static boolean isCanonicalExternalChunk(String base, String name) {
		String prefix = base + "_";
		String suffix = ".vpk";
		if (!name.startsWith(prefix) || !name.endsWith(suffix))
			return false;
		String digits = name.substring(prefix.length(), name.length() - suffix.length());
		if (digits.length() < 3 || digits.length() > 5 ||
			(digits.length() > 3 && digits.charAt(0) == '0'))
			return false;
		int archiveIndex = 0;
		for (int index = 0; index < digits.length(); ++index) {
			char character = digits.charAt(index);
			if (character < '0' || character > '9')
				return false;
			archiveIndex = archiveIndex * 10 + character - '0';
		}
		return archiveIndex <= 65534;
	}

	private static void updateMetadataDigest(MessageDigest digest, String label,
		File file) {
		digest.update(label.getBytes(StandardCharsets.UTF_8));
		digest.update((byte)0);
		if (file != null && file.isFile()) {
			digest.update(Long.toString(file.length()).getBytes(StandardCharsets.US_ASCII));
			digest.update((byte)':');
			digest.update(Long.toString(file.lastModified()).getBytes(StandardCharsets.US_ASCII));
		} else {
			digest.update((byte)'!');
		}
		digest.update((byte)'\n');
	}

	private static void updatePathMetadataDigest(MessageDigest digest, String label,
		File file) {
		digest.update(label.getBytes(StandardCharsets.UTF_8));
		digest.update((byte)0);
		if (file == null || !file.exists()) {
			digest.update((byte)'!');
		} else {
			digest.update((byte)(file.isDirectory() ? 'D' : file.isFile() ? 'F' : 'O'));
			digest.update((byte)':');
			digest.update(Long.toString(file.length()).getBytes(StandardCharsets.US_ASCII));
			digest.update((byte)':');
			digest.update(Long.toString(file.lastModified()).getBytes(StandardCharsets.US_ASCII));
		}
		digest.update((byte)'\n');
	}

	private static String hexadecimal(byte[] bytes) {
		char[] alphabet = "0123456789abcdef".toCharArray();
		StringBuilder output = new StringBuilder(bytes.length * 2);
		for (byte value : bytes) {
			output.append(alphabet[(value >>> 4) & 0xf]);
			output.append(alphabet[value & 0xf]);
		}
		return output.toString();
	}

	public static Result validate(File modDirectory) {
		String validatedCanonicalPath = canonicalDirectoryPath(modDirectory);
		String initialFingerprint = contentMetadataFingerprint(modDirectory);
		if (validatedCanonicalPath == null || initialFingerprint == null) {
			return failure(Status.INVALID_CONTENT_ARCHIVE,
				"selected game content directory cannot be fingerprinted");
		}
		File automaticOverlay = mountedAutomaticOverlay(modDirectory);
		if (automaticOverlay != null) {
			return failure(Status.UNSUPPORTED_AUTOMATIC_OVERLAY,
				"native automatically mounts sibling overlay before csgo: " +
				automaticOverlay.getAbsolutePath());
		}
		ContentIndex content = new ContentIndex(modDirectory);
		if (content.hasRejectedVpks()) {
			return failure(Status.INVALID_CONTENT_ARCHIVE,
				"mounted VPK index is invalid" + content.rejectedVpkSummary());
		}
		byte[] manifestBytes = content.read(WEAPON_MANIFEST, MAX_MANIFEST_BYTES);
		if (manifestBytes == null) {
			return failure(Status.MISSING_WEAPON_MANIFEST,
				WEAPON_MANIFEST + " is missing or unreadable" + content.rejectedVpkSummary());
		}

		Set<String> weaponNames;
		try {
			weaponNames = parseWeaponManifest(new String(manifestBytes, StandardCharsets.UTF_8));
		} catch (IllegalArgumentException error) {
			return failure(Status.INVALID_WEAPON_MANIFEST,
				WEAPON_MANIFEST + " is invalid: " + error.getMessage());
		}
		if (weaponNames.isEmpty()) {
			return failure(Status.INVALID_WEAPON_MANIFEST,
				WEAPON_MANIFEST + " does not list any weapon scripts");
		}
		if (!weaponNames.contains(REQUIRED_WEAPON)) {
			return failure(Status.MISSING_REQUIRED_WEAPON_SCRIPT,
				WEAPON_MANIFEST + " does not declare scripts/" + REQUIRED_WEAPON +
				".txt (required by this engine build)");
		}
		if (!weaponNames.equals(CONTRACT_WEAPON_SET)) {
			List<String> missingFromManifest = new ArrayList<String>(CONTRACT_WEAPON_SET);
			missingFromManifest.removeAll(weaponNames);
			List<String> unexpected = new ArrayList<String>(weaponNames);
			unexpected.removeAll(CONTRACT_WEAPON_SET);
			return failure(Status.INCOMPATIBLE_WEAPON_MANIFEST,
				"weapon manifest does not match CS:GO " + REFERENCE_GAME_VERSION +
				" contract (missing: " + summarize(missingFromManifest) +
				"; unexpected: " + summarize(unexpected) + ")");
		}

		List<String> missing = new ArrayList<String>();
		List<String> invalid = new ArrayList<String>();
		for (String weaponName : weaponNames) {
			String base = "scripts/" + weaponName;
			String textPath = base + ".txt";
			byte[] scriptBytes = content.read(textPath, MAX_WEAPON_SCRIPT_BYTES);
			if (scriptBytes == null) {
				if (content.contains(textPath)) {
					invalid.add(textPath + " is empty, oversized, corrupt, or unreadable");
				} else if (content.contains(base + ".ctx")) {
					invalid.add(base + ".ctx is encrypted and cannot be verified; " +
						"provide the plaintext " + textPath);
				} else {
					missing.add(textPath);
				}
				continue;
			}
			try {
				validateWeaponScript(new String(scriptBytes, StandardCharsets.UTF_8));
			} catch (IllegalArgumentException error) {
				invalid.add(textPath + " is invalid: " + error.getMessage());
			}
		}
		if (!invalid.isEmpty()) {
			int shown = Math.min(5, invalid.size());
			String diagnostic = "invalid " + invalid.size() + " weapon script(s): " +
				join(invalid.subList(0, shown), ", ");
			if (invalid.size() > shown)
				diagnostic += ", ...";
			return failure(Status.INVALID_LISTED_WEAPON_SCRIPT, diagnostic);
		}
		if (!missing.isEmpty()) {
			int shown = Math.min(5, missing.size());
			String diagnostic = "missing " + missing.size() + " weapon script(s): " +
				join(missing.subList(0, shown), ", ");
			if (missing.size() > shown)
				diagnostic += ", ...";
			return failure(Status.MISSING_LISTED_WEAPON_SCRIPT, diagnostic);
		}

		automaticOverlay = mountedAutomaticOverlay(modDirectory);
		if (automaticOverlay != null) {
			return failure(Status.UNSUPPORTED_AUTOMATIC_OVERLAY,
				"native automatically mounts sibling overlay before csgo: " +
				automaticOverlay.getAbsolutePath());
		}
		String validatedFingerprint = contentMetadataFingerprint(modDirectory);
		if (validatedFingerprint == null ||
			!initialFingerprint.equals(validatedFingerprint)) {
			return failure(Status.INVALID_CONTENT_ARCHIVE,
				"game content metadata changed during validation");
		}
		return new Result(Status.OK,
			"validated " + weaponNames.size() + " weapon script(s)", weaponNames.size(),
			validatedCanonicalPath, validatedFingerprint);
	}

	private static Result failure(Status status, String diagnostic) {
		return new Result(status, diagnostic, 0, null, null);
	}

	private static String summarize(List<String> values) {
		if (values.isEmpty())
			return "none";
		int shown = Math.min(5, values.size());
		String summary = join(values.subList(0, shown), ", ");
		return values.size() > shown ? summary + ", ..." : summary;
	}

	private static String computeContractSha256(Set<String> names) {
		try {
			MessageDigest digest = MessageDigest.getInstance("SHA-256");
			List<String> sorted = new ArrayList<String>(names);
			Collections.sort(sorted);
			for (String name : sorted) {
				digest.update(name.getBytes(StandardCharsets.UTF_8));
				digest.update((byte)'\n');
			}
			char[] hexadecimal = "0123456789abcdef".toCharArray();
			byte[] bytes = digest.digest();
			StringBuilder output = new StringBuilder(bytes.length * 2);
			for (byte value : bytes) {
				output.append(hexadecimal[(value >>> 4) & 0xf]);
				output.append(hexadecimal[value & 0xf]);
			}
			return output.toString();
		} catch (NoSuchAlgorithmException impossible) {
			throw new IllegalStateException("SHA-256 is unavailable", impossible);
		}
	}

	private static Set<String> parseWeaponManifest(String source) {
		List<String> tokens = tokenizeKeyValues(source);
		if (tokens.size() < 3 || !"{".equals(tokens.get(1)))
			throw new IllegalArgumentException("expected a KeyValues root block");
		Set<String> weaponNames = new LinkedHashSet<String>();
		int index = 2;
		boolean closed = false;
		while (index < tokens.size()) {
			String key = tokens.get(index++);
			if ("}".equals(key)) {
				closed = true;
				break;
			}
			if ("{".equals(key) || index >= tokens.size())
				throw new IllegalArgumentException("malformed root entry");
			String value = tokens.get(index++);
			if ("{".equals(value) || "}".equals(value))
				throw new IllegalArgumentException("entry " + key + " has no value");
			if (!"file".equalsIgnoreCase(key))
				throw new IllegalArgumentException("expected file entry, got " + key);
			String weaponName = weaponBaseName(value);
			if (weaponName == null)
				throw new IllegalArgumentException("unsafe weapon script path " + value);
			weaponNames.add(weaponName);
		}
		if (!closed || index != tokens.size())
			throw new IllegalArgumentException("unbalanced or trailing KeyValues data");
		return weaponNames;
	}

	private static final class KeyValuesBlock {
		final int nextIndex;
		final boolean hasNonEmptyScalar;

		KeyValuesBlock(int nextIndex, boolean hasNonEmptyScalar) {
			this.nextIndex = nextIndex;
			this.hasNonEmptyScalar = hasNonEmptyScalar;
		}
	}

	private static void validateWeaponScript(String source) {
		List<String> tokens = tokenizeKeyValues(source);
		if (tokens.size() < 4 || !"WeaponData".equals(tokens.get(0)) ||
			!"{".equals(tokens.get(1)))
			throw new IllegalArgumentException("expected a WeaponData root block");
		KeyValuesBlock root = parseKeyValuesBlock(tokens, 2, 0);
		if (root.nextIndex != tokens.size())
			throw new IllegalArgumentException("trailing KeyValues data");
		if (!root.hasNonEmptyScalar)
			throw new IllegalArgumentException("WeaponData block has no non-empty values");
	}

	private static KeyValuesBlock parseKeyValuesBlock(List<String> tokens, int index,
		int depth) {
		if (depth >= MAX_KEYVALUES_DEPTH)
			throw new IllegalArgumentException("KeyValues nesting depth exceeds " +
				MAX_KEYVALUES_DEPTH);
		boolean hasNonEmptyScalar = false;
		while (index < tokens.size()) {
			String key = tokens.get(index++);
			if ("}".equals(key))
				return new KeyValuesBlock(index, hasNonEmptyScalar);
			if ("{".equals(key) || index >= tokens.size())
				throw new IllegalArgumentException("malformed KeyValues entry");
			String value = tokens.get(index++);
			if ("}".equals(value))
				throw new IllegalArgumentException("entry " + key + " has no value");
			if ("{".equals(value)) {
				KeyValuesBlock child = parseKeyValuesBlock(tokens, index, depth + 1);
				index = child.nextIndex;
				hasNonEmptyScalar |= child.hasNonEmptyScalar;
			} else if (value.length() > 0) {
				hasNonEmptyScalar = true;
			}
			if (index < tokens.size() && isKeyValuesConditional(tokens.get(index)))
				++index;
		}
		throw new IllegalArgumentException("unbalanced KeyValues block");
	}

	private static boolean isKeyValuesConditional(String token) {
		return token.length() >= 2 && token.charAt(0) == '[' &&
			token.charAt(token.length() - 1) == ']';
	}

	private static List<String> tokenizeKeyValues(String source) {
		List<String> tokens = new ArrayList<String>();
		int position = source.length() > 0 && source.charAt(0) == '\ufeff' ? 1 : 0;
		while (position < source.length()) {
			char current = source.charAt(position);
			if (Character.isWhitespace(current)) {
				++position;
				continue;
			}
			if (current == '/' && position + 1 < source.length() &&
				source.charAt(position + 1) == '/') {
				position += 2;
				while (position < source.length() && source.charAt(position) != '\n')
					++position;
				continue;
			}
			if (current == '{' || current == '}') {
				tokens.add(String.valueOf(current));
				++position;
				continue;
			}
			if (current == '"') {
				++position;
				StringBuilder value = new StringBuilder();
				boolean closed = false;
				while (position < source.length()) {
					char character = source.charAt(position++);
					if (character == '"') {
						closed = true;
						break;
					}
					if (character == '\\' && position < source.length()) {
						char escaped = source.charAt(position++);
						if (escaped == 'n')
							value.append('\n');
						else if (escaped == 't')
							value.append('\t');
						else
							value.append(escaped);
					} else {
						value.append(character);
					}
				}
				if (!closed)
					throw new IllegalArgumentException("unterminated quoted string");
				tokens.add(value.toString());
				continue;
			}

			int start = position;
			while (position < source.length()) {
				char character = source.charAt(position);
				if (Character.isWhitespace(character) || character == '{' || character == '}')
					break;
				++position;
			}
			if (start == position)
				throw new IllegalArgumentException("unexpected character at " + position);
			tokens.add(source.substring(start, position));
		}
		return tokens;
	}

	private static String weaponBaseName(String manifestPath) {
		String normalized = normalizeResourcePath(manifestPath);
		if (normalized == null)
			return null;
		int slash = normalized.lastIndexOf('/');
		String name = slash < 0 ? normalized : normalized.substring(slash + 1);
		int dot = name.lastIndexOf('.');
		if (dot > 0)
			name = name.substring(0, dot);
		if (name.length() == 0)
			return null;
		for (int index = 0; index < name.length(); ++index) {
			char character = name.charAt(index);
			if (!(character >= 'a' && character <= 'z') &&
				!(character >= '0' && character <= '9') && character != '_')
				return null;
		}
		return name;
	}

	private static boolean isContractResourcePath(String path) {
		if (WEAPON_MANIFEST.equals(path))
			return true;
		if (!path.startsWith("scripts/") ||
			(!path.endsWith(".txt") && !path.endsWith(".ctx")))
			return false;
		int slash = path.lastIndexOf('/');
		int dot = path.lastIndexOf('.');
		return dot > slash && CONTRACT_WEAPON_SET.contains(path.substring(slash + 1, dot));
	}

	private static String normalizeResourcePath(String resourcePath) {
		if (resourcePath == null)
			return null;
		String value = resourcePath.trim().replace('\\', '/');
		if (value.length() == 0 || value.startsWith("/") || value.indexOf(':') >= 0 ||
			value.indexOf('\0') >= 0)
			return null;
		String[] parts = value.split("/");
		StringBuilder normalized = new StringBuilder();
		for (String part : parts) {
			if (part.length() == 0 || ".".equals(part) || "..".equals(part))
				return null;
			if (normalized.length() > 0)
				normalized.append('/');
			normalized.append(part.toLowerCase(Locale.ROOT));
		}
		return normalized.toString();
	}

	private static byte[] readLoose(File file, int maximumBytes) {
		if (file == null || !file.isFile() || file.length() <= 0 ||
			file.length() > maximumBytes || file.length() > Integer.MAX_VALUE)
			return null;
		try (FileInputStream input = new FileInputStream(file)) {
			ByteArrayOutputStream output = new ByteArrayOutputStream((int)file.length());
			byte[] buffer = new byte[16 * 1024];
			for (int count = input.read(buffer); count >= 0; count = input.read(buffer)) {
				if (count > 0) {
					if (output.size() > maximumBytes - count)
						return null;
					output.write(buffer, 0, count);
				}
			}
			return output.toByteArray();
		} catch (IOException ignored) {
			return null;
		}
	}

	private static long readU32(RandomAccessFile input) throws IOException {
		return (input.readUnsignedByte() & 0xffL) |
			((input.readUnsignedByte() & 0xffL) << 8) |
			((input.readUnsignedByte() & 0xffL) << 16) |
			((input.readUnsignedByte() & 0xffL) << 24);
	}

	private static String join(List<String> values, String separator) {
		StringBuilder output = new StringBuilder();
		for (String value : values) {
			if (output.length() > 0)
				output.append(separator);
			output.append(value);
		}
		return output.toString();
	}
}
