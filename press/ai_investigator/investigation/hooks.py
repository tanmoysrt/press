# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe


def has_investigation(incident_name: str) -> bool:
	"""Return True if a non-failed investigation already exists for this incident."""
	return bool(
		frappe.db.exists(
			"Operational Investigation",
			{"incident": incident_name, "status": ["not in", ["Failed"]]},
		)
	)


def poll_active_incidents() -> None:
	"""Scheduler hook — start investigation for any unattended active incident."""
	if not frappe.db.get_single_value("Press Settings", "ai_investigator_enabled"):
		return

	active = frappe.get_all(
		"Incident",
		filters={"status": ["in", ["Investigating", "Acknowledged"]]},
		fields=["name"],
		limit=50,
	)
	for inc in active:
		if not has_investigation(inc.name):
			frappe.enqueue(
				"press.ai_investigator.investigation.runner.start_investigation",
				incident_name=inc.name,
				source="Scheduler",
				queue="long",
				timeout=600,
			)


def on_incident_created(doc, method=None) -> None:
	"""Doc event hook — start investigation when a new incident is inserted."""
	if not frappe.db.get_single_value("Press Settings", "ai_investigator_enabled"):
		return
	if not has_investigation(doc.name):
		frappe.enqueue(
			"press.ai_investigator.investigation.runner.start_investigation",
			incident_name=doc.name,
			source="Incident Hook",
			queue="long",
			timeout=600,
		)
