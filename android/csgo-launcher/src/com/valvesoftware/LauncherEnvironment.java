package com.valvesoftware;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Parses the launcher's compact NAME=value environment field. */
public final class LauncherEnvironment {
	public static final class Assignment {
		public final String name;
		public final String value;

		Assignment(String name, String value) {
			this.name = name;
			this.value = value;
		}
	}

	private LauncherEnvironment() {
	}

	public static List<Assignment> parse(String input) {
		if (input == null || input.trim().isEmpty())
			return Collections.emptyList();

		List<String> tokens = tokenize(input);
		List<Assignment> assignments = new ArrayList<Assignment>(tokens.size());
		for (String token : tokens) {
			int separator = token.indexOf('=');
			if (separator <= 0)
				throw new IllegalArgumentException("Expected NAME=value, got: " + token);

			String name = token.substring(0, separator);
			if (!isValidName(name))
				throw new IllegalArgumentException("Invalid environment variable name: " + name);

			assignments.add(new Assignment(name, token.substring(separator + 1)));
		}
		return assignments;
	}

	private static List<String> tokenize(String input) {
		List<String> result = new ArrayList<String>();
		StringBuilder token = new StringBuilder();
		char quote = 0;
		boolean escaped = false;

		for (int i = 0; i < input.length(); ++i) {
			char c = input.charAt(i);
			if (escaped) {
				token.append(c);
				escaped = false;
				continue;
			}

			if (c == '\\' && quote != '\'') {
				escaped = true;
				continue;
			}

			if (quote != 0) {
				if (c == quote)
					quote = 0;
				else
					token.append(c);
				continue;
			}

			if (c == '\'' || c == '"') {
				quote = c;
				continue;
			}

			if (Character.isWhitespace(c) || c == ';') {
				if (token.length() > 0) {
					result.add(token.toString());
					token.setLength(0);
				}
				continue;
			}

			token.append(c);
		}

		if (escaped)
			token.append('\\');
		if (quote != 0)
			throw new IllegalArgumentException("Unterminated quote in environment field");
		if (token.length() > 0)
			result.add(token.toString());

		return result;
	}

	private static boolean isValidName(String name) {
		if (name.isEmpty() || !(name.charAt(0) == '_' || isAsciiLetter(name.charAt(0))))
			return false;

		for (int i = 1; i < name.length(); ++i) {
			char c = name.charAt(i);
			if (!(c == '_' || isAsciiLetter(c) || (c >= '0' && c <= '9')))
				return false;
		}
		return true;
	}

	private static boolean isAsciiLetter(char c) {
		return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
	}
}
