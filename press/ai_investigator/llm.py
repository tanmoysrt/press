# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import contextlib
import json

import frappe


def get_client():
	settings = frappe.get_single("Press Settings")
	provider = settings.get("ai_ops_default_provider") or "Anthropic"

	if provider == "OpenAI":
		try:
			import openai
		except ImportError as e:
			frappe.throw("openai package not installed. Run: pip install openai", exc=e)

		return openai.OpenAI(
			api_key=settings.get_password("ai_ops_openai_api_key") or "",
			base_url=settings.get("ai_ops_openai_base_url") or None,
		)

	if provider in ("Anthropic", "Anthropic Compatible"):
		try:
			import anthropic
		except ImportError as e:
			frappe.throw("anthropic package not installed. Run: pip install anthropic", exc=e)

		default_model = settings.get("ai_ops_default_model") or ""

		model_map = {
			"opus": "ai_ops_anthropic_default_opus_model",
			"sonnet": "ai_ops_anthropic_default_sonnet_model",
			"haiku": "ai_ops_anthropic_default_haiku_model",
		}

		model_field = model_map.get(default_model)
		custom_headers = {}

		with contextlib.suppress(json.JSONDecodeError):
			custom_headers = json.loads(settings.get("ai_ops_anthropic_custom_headers_json") or "{}")

		client = anthropic.Anthropic(
			api_key=settings.get_password("ai_ops_anthropic_api_key") or "",
			base_url=settings.get("ai_ops_anthropic_base_url") or None,
			default_headers=custom_headers or None,
		)

		client.default_model = settings.get(model_field) if model_field else default_model
		return client

	frappe.throw(f"Unknown AI Ops provider: {provider}")
	return None
