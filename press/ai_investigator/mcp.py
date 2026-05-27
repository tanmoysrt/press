# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe_mcp

mcp = frappe_mcp.MCP("frappe-cloud-investigator-mcp")


@mcp.register()
def handle_mcp():
	"""MCP endpoint for FC AI Ops. Restricted to System Manager."""
	import press.ai_investigator.tools.actions
	import press.ai_investigator.tools.code_analysis
	import press.ai_investigator.tools.documents
	import press.ai_investigator.tools.incidents
	import press.ai_investigator.tools.investigation
	import press.ai_investigator.tools.jobs
	import press.ai_investigator.tools.logs
	import press.ai_investigator.tools.metrics
	import press.ai_investigator.tools.ping  # noqa: F401
