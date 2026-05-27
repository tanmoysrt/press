# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from datetime import datetime, timedelta
from typing import cast

import frappe

from press.ai_investigator.mcp import mcp
from press.ai_investigator.permissions import system_manager_only
from press.ai_investigator.redaction import redact

ALLOWED_DOCTYPES = {
	"Server",
	"Database Server",
	"Proxy Server",
	"Monitor Server",
	"Bench",
	"Site",
	"Agent Job",
	"Ansible Play",
	"Press Job",
	"Press Workflow",
	"Incident",
	"Cluster",
	"Release Group",
	"Operational Investigation",
}


def _assert_allowed(doctype: str) -> None:
	if doctype not in ALLOWED_DOCTYPES:
		frappe.throw(
			f"Doctype '{doctype}' is not in the AI Ops allowlist. "
			f"Allowed: {', '.join(sorted(ALLOWED_DOCTYPES))}"
		)


@mcp.tool()
@system_manager_only
def get_document(doctype: str, name: str) -> dict:
	"""Fetch a single document from an allowed doctype.

	Args:
		doctype: The Frappe doctype name.
		name: The document name.
	"""
	_assert_allowed(doctype)

	if not frappe.db.exists(doctype, name):
		frappe.throw(f"{doctype} '{name}' not found")

	doc = frappe.get_doc(doctype, name)
	return cast("dict", redact(doc.as_dict()))


@mcp.tool()
@system_manager_only
def list_documents(
	doctype: str,
	filters: dict | None = None,
	fields: list | None = None,
	limit: int = 20,
) -> list:
	"""List documents from an allowed doctype with optional filters.

	Args:
		doctype: The Frappe doctype name.
		filters: Optional filter dict (same format as frappe.get_all filters).
		fields: Optional list of fields to return. Defaults to name + status + creation.
		limit: Maximum number of results (capped at 100).
	"""
	_assert_allowed(doctype)

	limit = min(limit, 100)
	default_fields = ["name", "creation", "modified"]

	docs = frappe.get_all(
		doctype,
		filters=filters or {},
		fields=fields or default_fields,
		order_by="creation desc",
		limit=limit,
	)
	return cast("list", redact(docs))


@mcp.tool()
@system_manager_only
def get_document_versions(doctype: str, name: str, days: int = 30) -> list:
	"""Get field-change history for a document using Frappe version tracking.

	Args:
		doctype: The Frappe doctype name.
		name: The document name.
		days: How many days of history to return (default 30).
	"""
	_assert_allowed(doctype)

	since = datetime.now() - timedelta(days=days)
	versions = frappe.get_all(
		"Version",
		filters={
			"ref_doctype": doctype,
			"docname": name,
			"creation": (">=", since),
		},
		fields=["name", "creation", "owner", "data"],
		order_by="creation desc",
		limit=50,
	)

	result = []
	for v in versions:
		entry: dict = {
			"name": v.name,
			"creation": str(v.creation),
			"owner": v.owner,
		}
		if v.data:
			import json

			try:
				entry["changes"] = json.loads(v.data) if isinstance(v.data, str) else v.data
			except (json.JSONDecodeError, TypeError):
				entry["changes"] = v.data
		result.append(entry)

	return cast("list", redact(result))
