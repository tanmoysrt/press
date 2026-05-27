# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta

import frappe

from press.ai_investigator import guardrails
from press.ai_investigator.investigation import evidence

ACTION_EXPIRY_MINUTES = 15


def plan_action(
	investigation_name: str,
	action: str,
	target_doctype: str,
	target_name: str,
	reason: str,
	expected_impact: str,
) -> dict:
	"""Create an action_plan log entry and return the plan display dict."""
	guardrails.check_action(action)

	token = secrets.token_hex(16)
	token_hash = hashlib.sha256(token.encode()).hexdigest()
	expires_at = datetime.now() + timedelta(minutes=ACTION_EXPIRY_MINUTES)

	data = {
		"action": action,
		"target_doctype": target_doctype,
		"target_name": target_name,
		"reason": reason,
		"expected_impact": expected_impact,
		"status": "pending_approval",
		"approval_token_hash": token_hash,
		"expires_at": str(expires_at),
		"approved_by": None,
		"executed_at": None,
		"result": None,
	}
	evidence.append_log(
		investigation_name,
		"action_plan",
		f"Action: {action} {target_name}",
		data=data,
	)

	log_name = frappe.db.get_value(
		"Operational Investigation Log",
		{
			"investigation": investigation_name,
			"type": "action_plan",
			"title": f"Action: {action} {target_name}",
		},
		"name",
		order_by="timestamp desc",
	)

	return {
		"action_id": log_name,
		"action": action,
		"target_doctype": target_doctype,
		"target_name": target_name,
		"reason": reason,
		"expected_impact": expected_impact,
		"expires_at": str(expires_at),
		"approval_token": token,
		"instructions": (
			f'To approve: execute_action_plan("{investigation_name}", "{log_name}", approval_token)'
		),
	}


def execute_action_plan(investigation_name: str, action_id: str, approval_token: str) -> dict:
	"""Validate, approve, and execute an action plan."""
	frappe.only_for("System Manager")
	log_doc = _load_and_validate_plan(action_id, investigation_name)
	data = log_doc.data_json or {}
	_verify_token(data, approval_token)
	guardrails.check_action(data["action"])
	_validate_target_state(data)
	_mark_approved(log_doc, data)
	result = _dispatch_action(data)
	_mark_executed(log_doc, data, result)
	evidence.append_log(
		investigation_name,
		"action_result",
		f"Action executed: {data['action']} {data['target_name']}",
		content=str(result),
		data={
			"action": data["action"],
			"target_name": data["target_name"],
			"result": str(result),
		},
	)
	frappe.db.set_value("Operational Investigation", investigation_name, "status", "Action Taken")
	frappe.db.commit()
	return {"action_id": action_id, "status": "executed", "result": str(result)}


def _load_and_validate_plan(action_id: str, investigation_name: str):
	"""Load log entry and check status + expiry."""
	if not frappe.db.exists("Operational Investigation Log", action_id):
		frappe.throw(f"Action plan '{action_id}' not found")
	log_doc = frappe.get_doc("Operational Investigation Log", action_id)
	if log_doc.investigation != investigation_name:
		frappe.throw("Action plan does not belong to this investigation")
	data = log_doc.data_json or {}
	if data.get("status") != "pending_approval":
		frappe.throw(f"Action plan status is '{data.get('status')}', expected pending_approval")
	expires_at = datetime.fromisoformat(data["expires_at"])
	if datetime.now() > expires_at:
		frappe.throw("Action plan has expired")
	return log_doc


def _verify_token(data: dict, approval_token: str) -> None:
	"""Hash provided token and compare to stored hash."""
	provided_hash = hashlib.sha256(approval_token.encode()).hexdigest()
	if provided_hash != data.get("approval_token_hash", ""):
		frappe.throw("Invalid approval token")


def _validate_target_state(data: dict) -> None:
	"""Re-read target doc and confirm it still exists."""
	target_doctype = data.get("target_doctype", "")
	target_name = data.get("target_name", "")
	if not frappe.db.exists(target_doctype, target_name):
		frappe.throw(f"{target_doctype} '{target_name}' no longer exists")


def _mark_approved(log_doc, data: dict) -> None:
	"""Update log data_json with approved_by."""
	data["approved_by"] = frappe.session.user
	data["status"] = "approved"
	log_doc.db_set("data_json", json.dumps(data), update_modified=False)
	frappe.db.commit()


def _dispatch_action(data: dict) -> str:
	"""Call the appropriate FC API and return a result string."""
	action = data["action"]
	target_name = data["target_name"]
	target_doctype = data.get("target_doctype", "")
	dispatch = {
		"restart_bench": lambda: frappe.get_doc("Bench", target_name).restart(),
		"reboot_app_server": lambda: frappe.get_doc("Server", target_name).reboot(),
		"activate_site": lambda: frappe.get_doc("Site", target_name).activate(),
	}
	fn = dispatch.get(action)
	if fn is None:
		frappe.throw(f"No executor for action '{action}'")
		return ""
	fn()
	return f"{action} on {target_doctype} {target_name} completed"


def _mark_executed(log_doc, data: dict, result: str) -> None:
	"""Update log data_json with execution details."""
	data["status"] = "executed"
	data["executed_at"] = str(datetime.now())
	data["result"] = result
	log_doc.db_set("data_json", json.dumps(data), update_modified=False)
