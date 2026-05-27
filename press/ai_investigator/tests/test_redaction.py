# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import unittest

from press.ai_investigator.redaction import redact

_REDACTED = "[REDACTED]"


class TestRedaction(unittest.TestCase):
	def test_bearer_token_stripped(self):
		result = redact("Authorization header: Bearer sk-abc123xyz")
		self.assertNotIn("sk-abc123xyz", result)
		self.assertIn(_REDACTED, result)

	def test_authorization_header_stripped(self):
		result = redact("Authorization: token myapikey:mysecret")
		self.assertNotIn("myapikey", result)
		self.assertIn(_REDACTED, result)

	def test_url_api_key_stripped(self):
		result = redact("https://api.example.com/data?api_key=supersecret&foo=bar")
		self.assertNotIn("supersecret", result)
		self.assertIn(_REDACTED, result)

	def test_password_field_stripped(self):
		result = redact('{"password": "hunter2", "user": "alice"}')
		self.assertNotIn("hunter2", result)
		self.assertIn(_REDACTED, result)

	def test_database_url_password_stripped(self):
		result = redact("mysql://user:hunter2@db.example.com:3306/mydb")
		self.assertNotIn("hunter2", result)
		self.assertIn(_REDACTED, result)

	def test_private_key_stripped(self):
		key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAK...\n-----END RSA PRIVATE KEY-----"  # pragma: allowlist secret
		result = redact(key)
		self.assertNotIn("MIIEowIBAAK", result)
		self.assertIn(_REDACTED, result)

	def test_cookie_header_stripped(self):
		result = redact("Cookie: sid=abcdef123456; csrftoken=xyz")  # pragma: allowlist secret
		self.assertNotIn("abcdef123456", result)  # pragma: allowlist secret

	def test_sid_cookie_stripped(self):
		result = redact("Set-Cookie: sid=mysessiontoken; Path=/")
		self.assertNotIn("mysessiontoken", result)
		self.assertIn(_REDACTED, result)

	def test_non_sensitive_strings_unchanged(self):
		safe = "site: test.frappe.cloud status: Active"
		self.assertEqual(redact(safe), safe)

	def test_nested_dict_redacted(self):
		data = {"config": {"password": "secret123"}, "name": "my-site"}  # pragma: allowlist secret
		result = redact(data)
		self.assertNotIn("secret123", str(result))
		self.assertEqual(result["name"], "my-site")

	def test_list_redacted(self):
		data = ["normal string", "password=letmein"]
		result = redact(data)
		self.assertNotIn("letmein", str(result))
		self.assertEqual(result[0], "normal string")

	def test_non_string_values_pass_through(self):
		self.assertEqual(redact(42), 42)
		self.assertIsNone(redact(None))
		self.assertEqual(redact(3.14), 3.14)
