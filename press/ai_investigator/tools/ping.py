# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe

from press.ai_investigator.mcp import mcp
from press.ai_investigator.permissions import system_manager_only


@mcp.tool()
@system_manager_only
def ping() -> dict:
	"""Verify MCP connection and confirm System Manager access."""
	return {"status": "ok", "site": frappe.local.site}
