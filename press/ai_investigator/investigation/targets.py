# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import re

import frappe


def _related_from_site(site_name: str) -> dict:
	"""Resolve bench, server, database_server, cluster from a site name."""
	row = frappe.db.get_value(
		"Site",
		site_name,
		["bench", "server", "database_server", "cluster"],
		as_dict=True,
	)
	return row or {}


def _related_from_server(server_name: str) -> dict:
	"""Resolve cluster from a server name."""
	cluster = frappe.db.get_value("Server", server_name, "cluster")
	return {"cluster": cluster} if cluster else {}


def _related_from_bench(bench_name: str) -> dict:
	"""Resolve server and cluster from a bench."""
	row = frappe.db.get_value("Bench", bench_name, ["server", "cluster"], as_dict=True)
	return row or {}


def _extract_site_from_query(query: str) -> str | None:
	"""Try to find a site name (something.example.com) in the query."""
	if not query:
		return None
	match = re.search(r"\b([\w-]+\.[\w.-]+\.[a-z]{2,})\b", query)
	return match.group(1) if match else None


def _resolve_from_explicit(target_doctype: str, target_name: str) -> dict:
	"""Resolve target dict when explicit doctype + name are provided."""
	related: dict = {}
	if target_doctype == "Site":
		related = _related_from_site(target_name)
	elif target_doctype == "Server":
		related = _related_from_server(target_name)
	elif target_doctype == "Bench":
		related = _related_from_bench(target_name)
	return {"target_doctype": target_doctype, "target_name": target_name, "related": related}


def resolve(
	query: str | None = None,
	incident=None,
	target_doctype: str | None = None,
	target_name: str | None = None,
) -> dict:
	"""Resolve the primary target and its related resources.

	Returns dict with target_doctype, target_name, related dict.
	"""
	if target_doctype and target_name:
		return _resolve_from_explicit(target_doctype, target_name)

	if incident is not None:
		server = incident.get("server") or incident.get("name")
		if server:
			return {
				"target_doctype": "Server",
				"target_name": server,
				"related": _related_from_server(server),
			}

	if query:
		site_name = _extract_site_from_query(query)
		if site_name and frappe.db.exists("Site", site_name):
			return {
				"target_doctype": "Site",
				"target_name": site_name,
				"related": _related_from_site(site_name),
			}

	return {"target_doctype": None, "target_name": None, "related": {}}
