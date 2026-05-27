# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe


@frappe.whitelist()
def start_investigation(
	query: str | None = None,
	incident_name: str | None = None,
	target_doctype: str | None = None,
	target_name: str | None = None,
	from_time: str | None = None,
	to_time: str | None = None,
) -> str:
	"""Create and enqueue a new investigation. Returns investigation name."""
	frappe.only_for("System Manager")
	from press.ai_investigator.investigation import runner

	return runner.start_investigation(
		query=query,
		incident_name=incident_name,
		target_doctype=target_doctype,
		target_name=target_name,
		from_time=from_time,
		to_time=to_time,
		source="Dashboard",
	)


@frappe.whitelist()
def get_investigation_logs(investigation_name: str) -> list:
	"""Return all log entries for an investigation."""
	frappe.only_for("System Manager")
	if not frappe.db.exists("Operational Investigation", investigation_name):
		frappe.throw(f"Investigation '{investigation_name}' not found")
	return frappe.get_all(
		"Operational Investigation Log",
		filters={"investigation": investigation_name},
		fields=["name", "type", "title", "content", "data_json", "timestamp"],
		order_by="timestamp asc",
		limit=200,
	)


@frappe.whitelist()
def continue_investigation(investigation_name: str, instruction: str) -> dict:
	"""Add a follow-up instruction to an existing investigation."""
	frappe.only_for("System Manager")
	from press.ai_investigator.investigation import runner

	return runner.continue_investigation(investigation_name, instruction)


@frappe.whitelist()
def finalize_rca(investigation_name: str) -> dict:
	"""Generate and return the RCA markdown for a completed investigation."""
	frappe.only_for("System Manager")
	from press.ai_investigator.investigation import rca

	markdown = rca.finalize_rca(investigation_name)
	return {"rca_markdown": markdown}


@frappe.whitelist()
def plan_bench_restart(bench: str, investigation_name: str, reason: str) -> dict:
	"""Create a bench restart action plan. Returns plan dict with approval_token."""
	frappe.only_for("System Manager")
	from press.ai_investigator.investigation import actions

	return actions.plan_action(
		investigation_name=investigation_name,
		action="restart_bench",
		target_doctype="Bench",
		target_name=bench,
		reason=reason,
		expected_impact="Brief downtime (~30s) while workers restart",
	)


@frappe.whitelist()
def execute_action_plan(investigation_name: str, action_id: str, approval_token: str) -> dict:
	"""Execute a pending action plan after approval."""
	frappe.only_for("System Manager")
	from press.ai_investigator.investigation import actions

	return actions.execute_action_plan(investigation_name, action_id, approval_token)
