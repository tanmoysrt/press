# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from typing import cast

import frappe

from press.ai_investigator.mcp import mcp
from press.ai_investigator.permissions import system_manager_only
from press.ai_investigator.redaction import redact

_JOB_LIST_FIELDS = [
	"name",
	"job_type",
	"status",
	"site",
	"bench",
	"server",
	"start",
	"end",
	"duration",
	"creation",
]
_JOB_DETAIL_FIELDS = [*_JOB_LIST_FIELDS, "output", "traceback", "request_data"]


def _normalise_status(jobs: list) -> list:
	"""Map 'Undelivered' → 'Pending' for display consistency."""
	for job in jobs:
		if job.get("status") == "Undelivered":
			job["status"] = "Pending"
	return jobs


@mcp.tool()
@system_manager_only
def get_recent_jobs(
	target_doctype: str,
	target_name: str,
	from_time: str,
	to_time: str,
	status: str | None = None,
) -> list:
	"""Get agent jobs for a resource within a time window.

	Args:
		target_doctype: Doctype of the target — Site, Bench, or Server.
		target_name: Name of the target resource.
		from_time: Start of time window (ISO format: YYYY-MM-DD HH:MM:SS).
		to_time: End of time window (ISO format: YYYY-MM-DD HH:MM:SS).
		status: Optional status filter (Pending, Running, Success, Failure).
	"""
	field_map = {"Site": "site", "Bench": "bench", "Server": "server"}
	if target_doctype not in field_map:
		frappe.throw(f"target_doctype must be one of: {', '.join(field_map)}")

	filters: dict = {
		field_map[target_doctype]: target_name,
		"creation": ("between", [from_time, to_time]),
	}
	if status:
		filters["status"] = status

	jobs = frappe.get_all(
		"Agent Job",
		filters=filters,
		fields=_JOB_LIST_FIELDS,
		order_by="creation desc",
		limit=50,
	)
	return cast("list", redact(_normalise_status(jobs)))


@mcp.tool()
@system_manager_only
def get_job_details(job_name: str) -> dict:
	"""Fetch full output and step-by-step log for a single agent job.

	Args:
		job_name: The Agent Job document name.
	"""
	if not frappe.db.exists("Agent Job", job_name):
		frappe.throw(f"Agent Job '{job_name}' not found")

	job = frappe.get_doc("Agent Job", job_name)
	result = {field: job.get(field) for field in _JOB_DETAIL_FIELDS if job.get(field) is not None}

	result["steps"] = frappe.get_all(
		"Agent Job Step",
		filters={"agent_job": job_name},
		fields=["step_name", "status", "output", "traceback", "start", "end", "duration"],
		order_by="idx asc",
	)

	if result.get("status") == "Undelivered":
		result["status"] = "Pending"

	return cast("dict", redact(result))


@mcp.tool()
@system_manager_only
def get_site_jobs(site: str, limit: int = 20, status: str | None = None) -> list:
	"""List recent agent jobs for a site.

	Args:
		site: Site name (e.g. customer.example.com).
		limit: Maximum results to return (capped at 100).
		status: Optional status filter.
	"""
	limit = min(limit, 100)
	filters: dict = {"site": site}
	if status:
		filters["status"] = status

	jobs = frappe.get_all(
		"Agent Job",
		filters=filters,
		fields=_JOB_LIST_FIELDS,
		order_by="creation desc",
		limit=limit,
	)
	return cast("list", redact(_normalise_status(jobs)))


@mcp.tool()
@system_manager_only
def get_server_jobs(server: str, limit: int = 20, status: str | None = None) -> list:
	"""List recent agent jobs for a server.

	Args:
		server: Server name.
		limit: Maximum results to return (capped at 100).
		status: Optional status filter.
	"""
	limit = min(limit, 100)
	filters: dict = {"server": server}
	if status:
		filters["status"] = status

	jobs = frappe.get_all(
		"Agent Job",
		filters=filters,
		fields=_JOB_LIST_FIELDS,
		order_by="creation desc",
		limit=limit,
	)
	return cast("list", redact(_normalise_status(jobs)))


@mcp.tool()
@system_manager_only
def get_bench_jobs(bench: str, limit: int = 20, status: str | None = None) -> list:
	"""List recent agent jobs for a bench.

	Args:
		bench: Bench name.
		limit: Maximum results to return (capped at 100).
		status: Optional status filter.
	"""
	limit = min(limit, 100)
	filters: dict = {"bench": bench}
	if status:
		filters["status"] = status

	jobs = frappe.get_all(
		"Agent Job",
		filters=filters,
		fields=_JOB_LIST_FIELDS,
		order_by="creation desc",
		limit=limit,
	)
	return cast("list", redact(_normalise_status(jobs)))


@mcp.tool()
@system_manager_only
def get_bench_processes(server: str) -> dict:
	"""Fetch supervisor process status for all benches on a server.

	Args:
		server: Server name.
	"""
	benches = frappe.get_all("Bench", filters={"server": server, "status": "Active"}, pluck="name", limit=20)
	result = {}
	for bench_name in benches:
		try:
			bench_doc = frappe.get_doc("Bench", bench_name)
			processes = bench_doc.supervisorctl_status()
			result[bench_name] = [
				{"name": p.get("name", ""), "status": p.get("status", ""), "pid": p.get("pid")}
				for p in (processes or [])
			]
		except Exception as exc:
			result[bench_name] = [{"error": str(exc)}]
	return cast("dict", redact(result))


@mcp.tool()
@system_manager_only
def list_processes(server: str) -> list:
	"""List supervisor process statuses across all active benches on a server.

	Args:
		server: Server name.
	"""
	benches = frappe.get_all("Bench", filters={"server": server, "status": "Active"}, pluck="name", limit=20)
	all_processes = []
	for bench_name in benches:
		try:
			bench_doc = frappe.get_doc("Bench", bench_name)
			processes = bench_doc.supervisorctl_status()
			for p in processes or []:
				all_processes.append(
					{
						"bench": bench_name,
						"name": p.get("name", ""),
						"status": p.get("status", ""),
						"pid": p.get("pid"),
					}
				)
		except Exception:
			pass
	return cast("list", redact(all_processes))
