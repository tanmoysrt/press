# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from datetime import datetime
from typing import cast

import frappe
import requests
from frappe.utils.password import get_decrypted_password

from press.ai_investigator.mcp import mcp
from press.ai_investigator.permissions import system_manager_only
from press.ai_investigator.redaction import redact
from press.press.report.mariadb_slow_queries.mariadb_slow_queries import (
	execute as execute_slow_queries,
)

_SITE_LOG_TYPES = {"frappe.log", "error.log", "database.log", "scheduler.log", "worker.log"}
_BENCH_LOG_TYPES = {"frappe.log", "error.log", "worker.log"}


def _get_log_server_url_and_auth() -> tuple[str, str]:
	log_server = frappe.db.get_single_value("Press Settings", "log_server")
	if not log_server:
		frappe.throw("Log server not configured in Press Settings")
	password = get_decrypted_password("Log Server", log_server, "kibana_password")
	return f"https://{log_server}/elasticsearch/filebeat-*/_search", password


def _ts_ms(dt_str: str) -> int:
	return int(datetime.fromisoformat(dt_str).timestamp() * 1000)


@mcp.tool()
@system_manager_only
def get_site_error_logs(site: str, from_time: str, to_time: str, limit: int = 100) -> list:
	"""Fetch error log entries for a site from Elasticsearch.

	Args:
		site: Site name.
		from_time: Start of window (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: End of window (ISO: YYYY-MM-DD HH:MM:SS).
		limit: Max entries (capped at 500).
	"""
	limit = min(limit, 500)
	try:
		url, password = _get_log_server_url_and_auth()
		query = {
			"size": limit,
			"sort": [{"@timestamp": "desc"}],
			"query": {
				"bool": {
					"filter": [
						{"match_phrase": {"json.site": site}},
						{"match_phrase": {"json.transaction_type": "log"}},
						{"range": {"@timestamp": {"gte": _ts_ms(from_time), "lte": _ts_ms(to_time)}}},
					]
				}
			},
		}
		response = requests.post(url, json=query, auth=("frappe", password), timeout=15)
		hits = response.json().get("hits", {}).get("hits", [])
		entries = [
			{
				"timestamp": h.get("_source", {}).get("@timestamp"),
				"level": h.get("_source", {}).get("json", {}).get("level"),
				"message": h.get("_source", {}).get("json", {}).get("message", "")[:500],
			}
			for h in hits
		]
		return cast("list", redact(entries))
	except Exception as exc:
		return cast("list", redact([{"error": str(exc)}]))


@mcp.tool()
@system_manager_only
def get_site_log(site: str, log_type: str, from_time: str, to_time: str, limit: int = 100) -> str:
	"""Fetch raw log file content from the agent for a site.

	Args:
		site: Site name.
		log_type: One of frappe.log, error.log, database.log, scheduler.log, worker.log.
		from_time: Used for context only — agent returns the current log file.
		to_time: Used for context only.
		limit: Max lines to return (capped at 500).
	"""
	if log_type not in _SITE_LOG_TYPES:
		frappe.throw(f"log_type must be one of: {', '.join(sorted(_SITE_LOG_TYPES))}")

	limit = min(limit, 500)
	try:
		site_doc = frappe.get_doc("Site", site)
		raw = site_doc.get_server_log(log_type)
		if isinstance(raw, list):
			raw = "\n".join(str(line) for line in raw[:limit])
		elif isinstance(raw, str):
			lines = raw.splitlines()
			raw = "\n".join(lines[-limit:])
		return cast("str", redact(raw or ""))
	except Exception as exc:
		return cast("str", redact(f"Error fetching log: {exc}"))


@mcp.tool()
@system_manager_only
def get_bench_log(bench: str, log_type: str, from_time: str, to_time: str, limit: int = 100) -> str:
	"""Fetch raw log file content from the agent for a bench.

	Args:
		bench: Bench name.
		log_type: One of frappe.log, error.log, worker.log.
		from_time: Used for context only.
		to_time: Used for context only.
		limit: Max lines to return (capped at 500).
	"""
	if log_type not in _BENCH_LOG_TYPES:
		frappe.throw(f"log_type must be one of: {', '.join(sorted(_BENCH_LOG_TYPES))}")

	limit = min(limit, 500)
	try:
		bench_doc = frappe.get_doc("Bench", bench)
		raw = bench_doc.get_server_log(log_type)
		if isinstance(raw, list):
			raw = "\n".join(str(line) for line in raw[:limit])
		elif isinstance(raw, str):
			lines = raw.splitlines()
			raw = "\n".join(lines[-limit:])
		return cast("str", redact(raw or ""))
	except Exception as exc:
		return cast("str", redact(f"Error fetching log: {exc}"))


@mcp.tool()
@system_manager_only
def get_slow_queries(
	site: str,
	from_time: str,
	to_time: str,
	search_pattern: str | None = None,
	max_lines: int = 100,
) -> list:
	"""Fetch slow query log entries for a site.

	Args:
		site: Site name.
		from_time: Start of window (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: End of window (ISO: YYYY-MM-DD HH:MM:SS).
		search_pattern: Optional regex pattern to filter queries.
		max_lines: Max entries to return (capped at 500).
	"""
	max_lines = min(max_lines, 500)
	try:
		filters = frappe._dict(
			site=site,
			start_datetime=datetime.fromisoformat(from_time),
			stop_datetime=datetime.fromisoformat(to_time),
			pattern=search_pattern or ".*",
			max_lines=max_lines,
		)
		_, data = execute_slow_queries(filters)
		results = [
			{
				"query": row.get("query", "")[:300],
				"count": row.get("count"),
				"duration": row.get("duration"),
				"rows_examined": row.get("rows_examined"),
			}
			for row in (data or [])
		]
		return cast("list", redact(results))
	except Exception as exc:
		return cast("list", redact([{"error": str(exc)}]))


@mcp.tool()
@system_manager_only
def get_slow_apis(site: str, from_time: str, to_time: str, threshold_ms: int | None = None) -> list:
	"""Fetch slow API paths from Elasticsearch for a site.

	Args:
		site: Site name.
		from_time: Start of window (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: End of window (ISO: YYYY-MM-DD HH:MM:SS).
		threshold_ms: Minimum average duration in ms to include (default 1000).
	"""
	threshold = threshold_ms or 1000
	try:
		url, password = _get_log_server_url_and_auth()
		query = {
			"size": 0,
			"query": {
				"bool": {
					"filter": [
						{"match_phrase": {"json.transaction_type": "request"}},
						{"match_phrase": {"json.site": site}},
						{"range": {"@timestamp": {"gte": _ts_ms(from_time), "lte": _ts_ms(to_time)}}},
					]
				}
			},
			"aggs": {
				"by_path": {
					"terms": {"field": "json.request.path", "size": 20},
					"aggs": {
						"avg_duration": {"avg": {"field": "json.duration"}},
						"max_duration": {"max": {"field": "json.duration"}},
						"count": {"value_count": {"field": "json.duration"}},
					},
				}
			},
		}
		response = requests.post(url, json=query, auth=("frappe", password), timeout=15)
		buckets = response.json().get("aggregations", {}).get("by_path", {}).get("buckets", [])
		results = [
			{
				"path": b["key"],
				"count": b["count"]["value"],
				"avg_duration_ms": round(b["avg_duration"]["value"] or 0, 2),
				"max_duration_ms": round(b["max_duration"]["value"] or 0, 2),
			}
			for b in buckets
			if (b["avg_duration"]["value"] or 0) >= threshold
		]
		results.sort(key=lambda x: x["avg_duration_ms"], reverse=True)
		return cast("list", redact(results))
	except Exception as exc:
		return cast("list", redact([{"error": str(exc)}]))


@mcp.tool()
@system_manager_only
def get_frequent_slow_queries(site: str, from_time: str, to_time: str) -> list:
	"""Fetch the most frequently occurring slow query patterns for a site.

	Args:
		site: Site name.
		from_time: Start of window (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: End of window (ISO: YYYY-MM-DD HH:MM:SS).
	"""
	try:
		filters = frappe._dict(
			site=site,
			start_datetime=datetime.fromisoformat(from_time),
			stop_datetime=datetime.fromisoformat(to_time),
			pattern=".*",
			max_lines=500,
			normalize_slow_logs=True,
		)
		_, data = execute_slow_queries(filters)
		results = sorted(
			[
				{
					"normalized_query": row.get("query", "")[:300],
					"count": row.get("count"),
					"avg_duration": row.get("duration"),
				}
				for row in (data or [])
			],
			key=lambda x: x["count"] or 0,
			reverse=True,
		)[:20]
		return cast("list", redact(results))
	except Exception as exc:
		return cast("list", redact([{"error": str(exc)}]))


MAX_RAW_TIME_RANGE_HOURS = 24
MAX_ES_RESULT_SIZE = 500


@mcp.tool()
@system_manager_only
def query_elasticsearch_raw(
	index_pattern: str,
	query: dict,
	from_time: str | None = None,
	to_time: str | None = None,
	size: int = 100,
) -> dict:
	"""Run a raw Elasticsearch query for advanced log analysis.

	Args:
		index_pattern: Index pattern (e.g. filebeat-*).
		query: Elasticsearch query DSL dict.
		from_time: Optional start time (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: Optional end time (ISO: YYYY-MM-DD HH:MM:SS).
		size: Max results (capped at 500).
	"""
	size = min(size, MAX_ES_RESULT_SIZE)

	if from_time and to_time:
		from_dt = datetime.fromisoformat(from_time)
		to_dt = datetime.fromisoformat(to_time)
		hours = (to_dt - from_dt).total_seconds() / 3600
		if hours > MAX_RAW_TIME_RANGE_HOURS:
			frappe.throw(f"Time range exceeds {MAX_RAW_TIME_RANGE_HOURS}h limit")

	log_server = frappe.db.get_single_value("Press Settings", "log_server")
	if not log_server:
		return cast("dict", redact({"error": "log_server not configured"}))

	password = get_decrypted_password("Log Server", log_server, "kibana_password")
	index_pattern = index_pattern or "filebeat-*"
	url = f"https://{log_server}/elasticsearch/{index_pattern}/_search"
	payload = {**query, "size": size}
	try:
		response = requests.post(url, json=payload, auth=("frappe", password), timeout=30)
		return cast("dict", redact(response.json()))
	except Exception as exc:
		return cast("dict", redact({"error": str(exc)}))
