# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from datetime import datetime

import frappe


def append_log(
	investigation_name: str,
	log_type: str,
	title: str,
	content: str = "",
	data: dict | None = None,
) -> None:
	"""Append one event to the investigation log."""
	doc = frappe.get_doc(
		{
			"doctype": "Operational Investigation Log",
			"investigation": investigation_name,
			"type": log_type,
			"title": title[:140] if title else "",
			"content": content,
			"data_json": data,
			"timestamp": datetime.now(),
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()


def log_tool_call(
	investigation_name: str,
	tool_name: str,
	input_data: dict,
	output_summary: str,
	duration_ms: int,
	status: str,
) -> None:
	"""Record a tool call event."""
	append_log(
		investigation_name,
		"tool_call",
		tool_name,
		data={
			"input": input_data,
			"output_summary": output_summary[:500] if output_summary else "",
			"duration_ms": duration_ms,
			"status": status,
		},
	)


def log_finding(
	investigation_name: str,
	title: str,
	content: str,
	evidence_type: str,
	confidence: float,
) -> None:
	"""Record a finding."""
	append_log(
		investigation_name,
		"finding",
		title,
		content,
		data={"evidence_type": evidence_type, "confidence": confidence},
	)


def log_hypothesis(
	investigation_name: str,
	title: str,
	confidence: float,
	evidence: str,
	next_check: str | None = None,
) -> None:
	"""Record a hypothesis."""
	append_log(
		investigation_name,
		"hypothesis",
		title,
		evidence,
		data={"confidence": confidence, "next_check": next_check},
	)
