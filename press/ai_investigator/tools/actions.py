# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import cast

import frappe

from press.ai_investigator.investigation import actions as action_runner
from press.ai_investigator.mcp import mcp
from press.ai_investigator.permissions import system_manager_only
from press.ai_investigator.redaction import redact


@mcp.tool()
@system_manager_only
def plan_restart_bench(bench: str, investigation_name: str, reason: str) -> dict:
	"""Plan a bench restart action requiring human approval.

	Args:
		bench: Bench name to restart.
		investigation_name: Operational Investigation name.
		reason: Why this action is needed.
	"""
	if not frappe.db.exists("Bench", bench):
		frappe.throw(f"Bench '{bench}' not found")
	plan = action_runner.plan_action(
		investigation_name=investigation_name,
		action="restart_bench",
		target_doctype="Bench",
		target_name=bench,
		reason=reason,
		expected_impact="Brief downtime (~30s) while workers restart",
	)
	return cast("dict", redact(plan))


@mcp.tool()
@system_manager_only
def plan_reboot_app_server(server: str, investigation_name: str, reason: str) -> dict:
	"""Plan an app server reboot requiring human approval.

	Args:
		server: Server name to reboot.
		investigation_name: Operational Investigation name.
		reason: Why this action is needed.
	"""
	if not frappe.db.exists("Server", server):
		frappe.throw(f"Server '{server}' not found")
	plan = action_runner.plan_action(
		investigation_name=investigation_name,
		action="reboot_app_server",
		target_doctype="Server",
		target_name=server,
		reason=reason,
		expected_impact="Server reboot — expect 1-3 min downtime",
	)
	return cast("dict", redact(plan))


@mcp.tool()
@system_manager_only
def plan_activate_site(site: str, investigation_name: str, reason: str) -> dict:
	"""Plan a site activation requiring human approval.

	Args:
		site: Site name to activate.
		investigation_name: Operational Investigation name.
		reason: Why this action is needed.
	"""
	if not frappe.db.exists("Site", site):
		frappe.throw(f"Site '{site}' not found")
	plan = action_runner.plan_action(
		investigation_name=investigation_name,
		action="activate_site",
		target_doctype="Site",
		target_name=site,
		reason=reason,
		expected_impact="Site will be brought back online",
	)
	return cast("dict", redact(plan))


@mcp.tool()
@system_manager_only
def execute_action_plan(investigation_name: str, action_id: str, approval_token: str) -> dict:
	"""Execute a pending action plan after human approval.

	Args:
		investigation_name: Operational Investigation name.
		action_id: Action plan log entry name (e.g. OIL-2026-00042).
		approval_token: Token shown when plan was created.
	"""
	result = action_runner.execute_action_plan(investigation_name, action_id, approval_token)
	return cast("dict", redact(result))
