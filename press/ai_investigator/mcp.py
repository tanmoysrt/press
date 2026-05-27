# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe_mcp

mcp = frappe_mcp.MCP("frappe-cloud-investigator-mcp")


@mcp.register()
def handle_mcp():
	"""MCP endpoint for FC AI Ops. Restricted to System Manager."""

	# Phase 0
	import press.ai_investigator.tools.documents

	# Phase 1
	import press.ai_investigator.tools.incidents
	import press.ai_investigator.tools.jobs
	import press.ai_investigator.tools.ping

	_ = press.ai_investigator.tools.documents
	_ = press.ai_investigator.tools.incidents
	_ = press.ai_investigator.tools.jobs
	_ = press.ai_investigator.tools.ping
