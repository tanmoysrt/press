# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import contextlib
import json

import frappe


def get_client():
	"""Return an Anthropic client configured from Press Settings."""
	try:
		import anthropic
	except ImportError as e:
		frappe.throw("anthropic package not installed. Run: pip install anthropic", exc=e)

	settings = frappe.get_single("Press Settings")
	custom_headers = {}
	with contextlib.suppress(json.JSONDecodeError):
		custom_headers = json.loads(settings.get("anthropic_custom_headers_json") or "{}")

	return anthropic.Anthropic(
		api_key=settings.get_password("anthropic_api_key") or "",
		base_url=settings.get("anthropic_base_url") or None,
		default_headers=custom_headers or None,
	)


def get_model(tier: str = "sonnet") -> str:
	"""Return the configured model ID for a given tier (opus/sonnet/haiku)."""
	settings = frappe.get_single("Press Settings")
	field_map = {
		"opus": "anthropic_default_opus_model",
		"sonnet": "anthropic_default_sonnet_model",
		"haiku": "anthropic_default_haiku_model",
	}
	field = field_map.get(tier, "anthropic_default_sonnet_model")
	return settings.get(field) or f"claude-{tier}-4-5"
