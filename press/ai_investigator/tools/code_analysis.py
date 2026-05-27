# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import re
from typing import cast

import frappe
import requests

from press.ai_investigator.mcp import mcp
from press.ai_investigator.permissions import system_manager_only
from press.ai_investigator.redaction import redact

BAD_PATTERNS = [
	r"frappe\.get_doc\s*\(",
	r"frappe\.db\.get_value\s*\(",
	r"frappe\.db\.get_all\s*\(",
	r"frappe\.db\.sql\s*\(",
	r"requests\.get\(",
	r"requests\.post\(",
	r"for .+ in .+\.items\b",
]

_PATTERN_LABELS = {
	r"frappe\.get_doc\s*\(": "frappe.get_doc() call — potential N+1 query risk",
	r"frappe\.db\.get_value\s*\(": "frappe.db.get_value() call — potential N+1 query risk",
	r"frappe\.db\.get_all\s*\(": "frappe.db.get_all() call — potential N+1 query risk",
	r"frappe\.db\.sql\s*\(": "frappe.db.sql() call — unbounded query risk",
	r"requests\.get\(": "Synchronous HTTP requests.get() in request path",
	r"requests\.post\(": "Synchronous HTTP requests.post() in request path",
	r"for .+ in .+\.items\b": "Large child table iteration pattern",
}


def _get_bench_app_info(bench: str, app: str) -> dict:
	"""Fetch app source and release metadata for an app on a bench."""
	rows = frappe.get_all(
		"Bench App",
		filters={"parent": bench, "parenttype": "Bench", "app": app},
		fields=["source", "release"],
		limit=1,
	)
	if not rows:
		return {}
	row = rows[0]
	source = (
		frappe.db.get_value(
			"App Source",
			row["source"],
			["repository_url", "branch", "repository_owner", "repository"],
			as_dict=True,
		)
		or {}
	)
	commit_hash = frappe.db.get_value("App Release", row["release"], "hash") or ""
	return {
		"app": app,
		"source": row["source"],
		"release": row["release"],
		"repository_url": source.get("repository_url", ""),
		"branch": source.get("branch", ""),
		"repository_owner": source.get("repository_owner", ""),
		"repository": source.get("repository", ""),
		"commit_hash": commit_hash,
	}


def _parse_endpoint(endpoint_path: str) -> tuple[str, str, str]:
	"""Parse an API endpoint path into (app, file_path, function_name)."""
	path = endpoint_path.lstrip("/")

	if path.startswith("api/method/"):
		method_path = path[len("api/method/") :]
		segments = method_path.split(".")
		app = segments[0] if segments else ""
		function = segments[-1] if segments else ""
		file_path = "/".join(segments[:-1]) + ".py" if len(segments) > 1 else ""
		return (app, file_path, function)

	if path.startswith("api/resource/"):
		doctype_raw = path[len("api/resource/") :]
		doctype = doctype_raw.replace("%20", " ")
		return ("", "", doctype)

	return ("", path, "")


def _fetch_github_file(owner: str, repo: str, path: str, sha: str) -> str:
	"""Fetch raw file content from GitHub at a specific commit SHA."""
	token = frappe.db.get_single_value("Press Settings", "agent_github_access_token") or ""
	url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={sha}"
	headers = {"Accept": "application/vnd.github.v3.raw"}
	if token:
		headers["Authorization"] = f"Bearer {token}"
	response = requests.get(url, headers=headers, timeout=15)
	if response.status_code != 200:
		return ""
	return response.text


def _extract_function_source(source_text: str, function_name: str) -> tuple[str, int, int]:
	"""Extract the source lines of a named function from Python source text."""
	lines = source_text.splitlines()
	start_index = -1
	start_indent = -1

	for i, line in enumerate(lines):
		stripped = line.lstrip()
		indent = len(line) - len(stripped)
		if stripped.startswith(f"def {function_name}("):
			start_index = i
			start_indent = indent
			break

	if start_index == -1:
		return ("", 0, 0)

	end_index = len(lines)
	for i in range(start_index + 1, len(lines)):
		line = lines[i]
		stripped = line.lstrip()
		if not stripped:
			continue
		indent = len(line) - len(stripped)
		if indent <= start_indent and (stripped.startswith("def ") or stripped.startswith("class ")):
			end_index = i
			break

	extracted = "\n".join(lines[start_index:end_index])
	return (extracted, start_index + 1, end_index)


def _detect_bad_patterns(source_text: str) -> list[str]:
	"""Return list of bad pattern strings found in the source text."""
	findings = []
	for pattern in BAD_PATTERNS:
		if re.search(pattern, source_text):
			findings.append(pattern)
	return findings


def _resolve_doctype_file(doctype: str) -> tuple[str, str]:
	"""Resolve a DocType name to its (app, file_path) on disk."""
	module = frappe.db.get_value("DocType", doctype, "module") or ""
	app = frappe.db.get_value("Module Def", module, "app_name") or "" if module else ""
	if not app or not module:
		return ("", "")
	module_path = module.lower().replace(" ", "_")
	doctype_path = doctype.lower().replace(" ", "_")
	file_path = f"{app}/{module_path}/doctype/{doctype_path}/{doctype_path}.py"
	return (app, file_path)


@mcp.tool()
@system_manager_only
def get_bench_app_info(bench: str, app: str) -> dict:
	"""Fetch app source and release info for an app deployed on a bench."""
	if not frappe.db.exists("Bench", bench):
		return cast("dict", redact({"error": f"Bench '{bench}' not found"}))
	info = _get_bench_app_info(bench, app)
	if not info:
		return cast("dict", redact({"error": f"App '{app}' not found on bench '{bench}'"}))
	return cast("dict", redact(info))


@mcp.tool()
@system_manager_only
def get_app_source_file(site: str, app: str, file_path: str) -> str:
	"""Fetch source file content from the git host at the commit deployed on a site."""
	bench = frappe.db.get_value("Site", site, "bench")
	if not bench:
		return cast("str", redact(f"Site '{site}' not found"))

	info = _get_bench_app_info(bench, app)
	if not info.get("repository_owner") or not info.get("repository") or not info.get("commit_hash"):
		return cast("str", redact(f"App '{app}' source info incomplete for site '{site}'"))

	content = _fetch_github_file(info["repository_owner"], info["repository"], file_path, info["commit_hash"])
	return cast("str", redact(content or "File not found"))


@mcp.tool()
@system_manager_only
def resolve_endpoint_source(site: str, endpoint_path: str) -> dict:
	"""Resolve the source file and function for an API endpoint on a site."""
	app, file_path, function = _parse_endpoint(endpoint_path)

	if not app and function and function[:1].isupper():
		app, file_path = _resolve_doctype_file(function)

	if not app:
		return cast("dict", redact({"error": "Cannot resolve app from endpoint"}))

	bench = frappe.db.get_value("Site", site, "bench")
	if not bench:
		return cast("dict", redact({"error": f"Site '{site}' not found"}))

	info = _get_bench_app_info(bench, app)
	if not info.get("repository_owner") or not info.get("repository") or not info.get("commit_hash"):
		return cast("dict", redact({"error": f"App '{app}' source info incomplete"}))

	source_text = _fetch_github_file(
		info["repository_owner"], info["repository"], file_path, info["commit_hash"]
	)
	fn_source, line_start, line_end = _extract_function_source(source_text, function)

	return cast(
		"dict",
		redact(
			{
				"app": app,
				"file_path": file_path,
				"function": function,
				"repo_url": info["repository_url"],
				"commit": info["commit_hash"][:7],
				"source": fn_source[:3000],
				"line_start": line_start,
				"line_end": line_end,
			}
		),
	)


@mcp.tool()
@system_manager_only
def analyze_slow_endpoint(site: str, endpoint_path: str, from_time: str, to_time: str) -> dict:
	"""Analyze the source code of the slowest endpoint on a site."""
	resolved_path = endpoint_path or _detect_slowest_endpoint(site, from_time, to_time)
	if not resolved_path:
		return cast("dict", redact({"error": "No slow APIs found"}))

	result = resolve_endpoint_source(site, resolved_path)
	if result.get("error"):
		return cast("dict", redact(result))

	detected = _detect_bad_patterns(result.get("source", ""))
	bad_patterns = [_PATTERN_LABELS.get(p, p) for p in detected]

	return cast(
		"dict",
		redact(
			{
				"endpoint": resolved_path,
				"app": result.get("app"),
				"file": result.get("file_path"),
				"function": result.get("function"),
				"commit": result.get("commit"),
				"bad_patterns": bad_patterns,
				"source_preview": result.get("source", "")[:500],
			}
		),
	)


def _detect_slowest_endpoint(site: str, from_time: str, to_time: str) -> str:
	"""Return the path of the slowest API endpoint, or empty string if none found."""
	from press.ai_investigator.tools.logs import get_slow_apis

	slow_apis = get_slow_apis(site=site, from_time=from_time, to_time=to_time)
	if slow_apis and isinstance(slow_apis, list) and not slow_apis[0].get("error"):
		return slow_apis[0].get("path", "")
	return ""
