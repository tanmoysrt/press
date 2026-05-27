# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import re
from typing import overload

_REDACTED = "[REDACTED]"

# Dict keys that always have their value fully replaced when redacting a mapping.
_SENSITIVE_KEYS = frozenset(
	{
		"password",
		"passwd",
		"pwd",
		"api_key",
		"apikey",
		"api_secret",
		"secret",
		"token",
		"authorization",
		"auth_token",
		"private_key",
		"db_password",
	}
)

# Each tuple: (compiled_pattern, has_preserve_group)
# Patterns WITH a capture group 1 keep group(1) and replace the rest with [REDACTED].
# Patterns WITHOUT a capture group replace the entire match.
_PATTERNS: list[tuple[re.Pattern, bool]] = [
	# Authorization: Bearer/token <value>
	(re.compile(r"(Authorization:\s*\S+\s+)\S+", re.IGNORECASE), True),
	# bearer <token>
	(re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-._~+/]+=*"), True),
	# URL param: ?token=…  &api_key=… etc.
	(re.compile(r"(?i)([?&](token|api_?key|secret|password|passwd|pwd)=)[^&\s\"']+"), True),
	# JSON/config password field value
	(re.compile(r'(?i)("?(password|passwd|pwd|secret|api_?key)"?\s*[":=]\s*)["\']?[^"\'}\s,\n]+'), True),
	# Database connection URLs: mysql://user:PASS@host  # pragma: allowlist secret
	(
		re.compile(
			r"(?i)((?:mysql|postgresql|postgres|mariadb|mongodb)://[^:@\s]+:)[^@\s]+"
		),  # pragma: allowlist secret
		True,
	),
	# PEM private key blocks — no preserve group, entire block replaced
	(
		re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----.*?-----END [A-Z ]+ PRIVATE KEY-----", re.DOTALL),
		False,
	),
	# Cookie: header
	(re.compile(r"(?i)(Cookie:\s*)\S.*", re.IGNORECASE), True),
	# sid= cookie value
	(re.compile(r"(?i)(sid=)[^;\"'\s]+"), True),
]


def _redact_string(value: str) -> str:
	"""Apply all redaction patterns to a string."""
	for pattern, has_group in _PATTERNS:
		if has_group:
			value = pattern.sub(lambda m: m.group(1) + _REDACTED, value)
		else:
			value = pattern.sub(_REDACTED, value)
	return value


@overload
def redact(value: dict) -> dict: ...


@overload
def redact(value: list) -> list: ...


@overload
def redact(value: str) -> str: ...


@overload
def redact(value: object) -> object: ...


def redact(value: object) -> object:
	"""Recursively strip secrets from tool output before returning to MCP client."""
	if isinstance(value, str):
		return _redact_string(value)
	if isinstance(value, dict):
		result: dict = {}
		for k, v in value.items():
			if isinstance(k, str) and k.lower() in _SENSITIVE_KEYS:
				result[k] = _REDACTED if v is not None else None
			else:
				result[k] = redact(v)
		return result
	if isinstance(value, list):
		return [redact(item) for item in value]
	return value
