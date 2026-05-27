# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe


def record_tool_call(
	tool_name: str,
	user: str,
	input_summary: str,
	status: str,
	duration_ms: int,
) -> None:
	"""Record every MCP tool call for traceability."""
	frappe.logger("ai_investigator").info(
		f"tool_call | tool={tool_name} user={user} status={status} duration_ms={duration_ms} | {input_summary}"
	)
