# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from datetime import datetime, timedelta
from typing import cast

import frappe

from press.ai_investigator.investigation import runner
from press.ai_investigator.mcp import mcp
from press.ai_investigator.permissions import system_manager_only
from press.ai_investigator.redaction import redact


def _default_window(hours: int = 1) -> tuple[str, str]:
	now = datetime.now()
	return str(now - timedelta(hours=hours)), str(now)


def _investigation_result(investigation_name: str) -> dict:
	"""Build the return dict from a completed investigation doc."""
	doc = frappe.get_doc("Operational Investigation", investigation_name)
	logs = frappe.get_all(
		"Operational Investigation Log",
		filters={"investigation": investigation_name, "type": "finding"},
		fields=["title", "content", "data_json"],
		order_by="timestamp asc",
		limit=20,
	)
	findings = [
		{"type": log.get("data_json", {}).get("evidence_type", "observation"), "text": log.title}
		for log in logs
	]

	return {
		"investigation": doc.name,
		"incident": doc.incident,
		"status": doc.status,
		"affected": {
			"site": doc.affected_site,
			"server": doc.affected_server,
			"bench": doc.affected_bench,
		},
		"time_window": {"from": str(doc.from_time), "to": str(doc.to_time)},
		"findings": findings,
		"primary_cause": doc.primary_cause or "",
		"confidence": doc.confidence or 0.0,
		"summary": doc.summary or "",
	}


@mcp.tool()
@system_manager_only
def investigate_incident(incident_name: str) -> dict:
	"""Start or fetch an investigation for an incident.

	Creates an Operational Investigation, runs the first pass in background,
	and returns a reference to the investigation with initial results.

	Args:
		incident_name: Incident document name (e.g. INC-0001).
	"""
	if not frappe.db.exists("Incident", incident_name):
		frappe.throw(f"Incident '{incident_name}' not found")

	investigation_name = runner.start_investigation(incident_name=incident_name, source="MCP")
	return cast("dict", redact(_investigation_result(investigation_name)))


@mcp.tool()
@system_manager_only
def investigate(
	query: str,
	target_doctype: str | None = None,
	target_name: str | None = None,
	from_time: str | None = None,
	to_time: str | None = None,
) -> dict:
	"""Start a free-form investigation by natural language query.

	Args:
		query: Natural language description of what to investigate.
		target_doctype: Optional — Site, Server, or Bench.
		target_name: Optional — name of the target document.
		from_time: Optional start time (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: Optional end time (ISO: YYYY-MM-DD HH:MM:SS).
	"""
	investigation_name = runner.start_investigation(
		query=query,
		target_doctype=target_doctype,
		target_name=target_name,
		from_time=from_time,
		to_time=to_time,
		source="MCP",
	)
	return cast("dict", redact(_investigation_result(investigation_name)))


@mcp.tool()
@system_manager_only
def check_site_performance(site: str, from_time: str | None = None, to_time: str | None = None) -> dict:
	"""Run a site performance investigation.

	Args:
		site: Site name.
		from_time: Optional start time (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: Optional end time (ISO: YYYY-MM-DD HH:MM:SS).
	"""
	if not frappe.db.exists("Site", site):
		frappe.throw(f"Site '{site}' not found")

	ft, tt = from_time, to_time
	if not ft or not tt:
		ft, tt = _default_window(hours=1)

	investigation_name = runner.start_investigation(
		query=f"Check performance for site {site}",
		target_doctype="Site",
		target_name=site,
		from_time=ft,
		to_time=tt,
		source="MCP",
	)
	return cast("dict", redact(_investigation_result(investigation_name)))


@mcp.tool()
@system_manager_only
def check_server_performance(server: str, from_time: str | None = None, to_time: str | None = None) -> dict:
	"""Run a server performance investigation.

	Args:
		server: Server name.
		from_time: Optional start time (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: Optional end time (ISO: YYYY-MM-DD HH:MM:SS).
	"""
	if not frappe.db.exists("Server", server):
		frappe.throw(f"Server '{server}' not found")

	ft, tt = from_time, to_time
	if not ft or not tt:
		ft, tt = _default_window(hours=1)

	investigation_name = runner.start_investigation(
		query=f"Check performance for server {server}",
		target_doctype="Server",
		target_name=server,
		from_time=ft,
		to_time=tt,
		source="MCP",
	)
	return cast("dict", redact(_investigation_result(investigation_name)))


@mcp.tool()
@system_manager_only
def check_bench_health(bench: str, from_time: str | None = None, to_time: str | None = None) -> dict:
	"""Run a bench health investigation.

	Args:
		bench: Bench name.
		from_time: Optional start time (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: Optional end time (ISO: YYYY-MM-DD HH:MM:SS).
	"""
	if not frappe.db.exists("Bench", bench):
		frappe.throw(f"Bench '{bench}' not found")

	ft, tt = from_time, to_time
	if not ft or not tt:
		ft, tt = _default_window(hours=1)

	investigation_name = runner.start_investigation(
		query=f"Check health of bench {bench}",
		target_doctype="Bench",
		target_name=bench,
		from_time=ft,
		to_time=tt,
		source="MCP",
	)
	return cast("dict", redact(_investigation_result(investigation_name)))


@mcp.tool()
@system_manager_only
def explain_downtime(target_doctype: str, target_name: str, from_time: str, to_time: str) -> dict:
	"""Investigate downtime for a site or server over a time window.

	Args:
		target_doctype: Site or Server.
		target_name: Name of the resource.
		from_time: Start of downtime window (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: End of downtime window (ISO: YYYY-MM-DD HH:MM:SS).
	"""
	allowed = {"Site", "Server"}
	if target_doctype not in allowed:
		frappe.throw(f"target_doctype must be one of: {', '.join(allowed)}")

	investigation_name = runner.start_investigation(
		query=f"Explain downtime for {target_doctype} {target_name}",
		target_doctype=target_doctype,
		target_name=target_name,
		from_time=from_time,
		to_time=to_time,
		source="MCP",
	)
	return cast("dict", redact(_investigation_result(investigation_name)))


@mcp.tool()
@system_manager_only
def check_recent_changes(
	target_doctype: str,
	target_name: str,
	from_time: str | None = None,
	to_time: str | None = None,
) -> dict:
	"""Investigate recent changes for a resource.

	Args:
		target_doctype: Site, Server, or Bench.
		target_name: Name of the resource.
		from_time: Optional start time (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: Optional end time (ISO: YYYY-MM-DD HH:MM:SS).
	"""
	ft, tt = from_time, to_time
	if not ft or not tt:
		ft, tt = _default_window(hours=24)

	investigation_name = runner.start_investigation(
		query=f"Check recent changes for {target_doctype} {target_name}",
		target_doctype=target_doctype,
		target_name=target_name,
		from_time=ft,
		to_time=tt,
		source="MCP",
	)
	return cast("dict", redact(_investigation_result(investigation_name)))
