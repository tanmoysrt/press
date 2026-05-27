# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from datetime import datetime, timedelta
from typing import cast

import frappe

from press.ai_investigator.mcp import mcp
from press.ai_investigator.permissions import system_manager_only
from press.ai_investigator.redaction import redact

# Only direct DB columns — child tables excluded.
_INCIDENT_LIST_FIELDS = [
	"name",
	"server",
	"cluster",
	"status",
	"type",
	"subject",
	"likely_cause",
	"investigation",
	"resolved_by",
	"resolved_at",
	"confirmed_at",
	"creation",
	"modified",
]


def _get_suggestions(doc, fieldname: str) -> list[str]:
	"""Extract suggestion titles from a child table field."""
	return [row.title for row in (doc.get(fieldname) or []) if row.title]


def _get_alert_rows(doc) -> list[dict]:
	return [
		{
			"alert": row.alert,
			"resource_type": row.resource_type,
			"resource": row.resource,
			"subtype": row.subtype,
		}
		for row in (doc.alerts or [])
	]


def _get_update_rows(doc) -> list[dict]:
	return [
		{
			"update": row.update,
			"creation": str(row.creation) if row.creation else None,
		}
		for row in (doc.updates or [])
	]


@mcp.tool()
@system_manager_only
def get_incident_details(incident_name: str) -> dict:
	"""Fetch full details of a single incident including alerts, updates, and suggestions.

	Args:
		incident_name: The name of the Incident document (e.g. INC-0001).
	"""
	if not frappe.db.exists("Incident", incident_name):
		frappe.throw(f"Incident {incident_name} not found")

	doc = frappe.get_doc("Incident", incident_name)

	result = {field: doc.get(field) for field in _INCIDENT_LIST_FIELDS if doc.get(field) is not None}
	result["description"] = doc.description
	result["alerts"] = _get_alert_rows(doc)
	result["updates"] = _get_update_rows(doc)
	result["corrective_suggestions"] = _get_suggestions(doc, "corrective_suggestions")
	result["preventive_suggestions"] = _get_suggestions(doc, "preventive_suggestions")

	return cast("dict", redact(result))


@mcp.tool()
@system_manager_only
def get_active_incidents(cluster: str | None = None) -> list:
	"""List all currently active (non-resolved) incidents.

	Args:
		cluster: Optional cluster name to filter by.
	"""
	filters: dict = {"status": ("in", ["Confirmed", "Validating", "Investigating"])}
	if cluster:
		filters["cluster"] = cluster

	incidents = frappe.get_all(
		"Incident",
		filters=filters,
		fields=_INCIDENT_LIST_FIELDS,
		order_by="creation desc",
		limit=100,
	)
	return cast("list", redact(incidents))


@mcp.tool()
@system_manager_only
def get_incident_history(target_doctype: str, target_name: str, days: int = 7) -> list:
	"""Get past incidents for a server or cluster within the last N days.

	Args:
		target_doctype: Doctype of the target — Server or Cluster.
		target_name: Name of the target document.
		days: How many days back to search (default 7).
	"""
	allowed = {"Server", "Cluster"}
	if target_doctype not in allowed:
		frappe.throw(f"target_doctype must be one of: {', '.join(allowed)}")

	since = datetime.now() - timedelta(days=days)
	filters: dict = {
		"creation": (">=", since),
		"status": ("in", ["Confirmed", "Validating", "Investigating", "Resolved", "Auto-Resolved"]),
	}

	if target_doctype == "Server":
		filters["server"] = target_name
	elif target_doctype == "Cluster":
		filters["cluster"] = target_name

	incidents = frappe.get_all(
		"Incident",
		filters=filters,
		fields=_INCIDENT_LIST_FIELDS,
		order_by="creation desc",
		limit=50,
	)
	return cast("list", redact(incidents))
