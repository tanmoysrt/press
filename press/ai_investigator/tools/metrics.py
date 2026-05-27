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

_METRIC_TYPES = {"cpu", "memory", "disk", "iops", "network", "load", "db"}

_CPU_QUERY = (
	'100 - (avg by (instance) (rate(node_cpu_seconds_total{{instance="{server}",mode="idle"}}[5m])) * 100)'
)
_MEMORY_QUERY = (
	'(1 - (node_memory_MemAvailable_bytes{{instance="{server}"}}'
	' / node_memory_MemTotal_bytes{{instance="{server}"}})) * 100'
)
_PROMQL: dict[str, str] = {
	"cpu": _CPU_QUERY,
	"memory": _MEMORY_QUERY,
	"disk": 'node_filesystem_avail_bytes{{instance="{server}",mountpoint="/",fstype!="tmpfs"}}',
	"load": 'node_load5{{instance="{server}"}}',
	"iops": 'rate(node_disk_io_time_seconds_total{{instance="{server}"}}[5m]) * 100',
	"network": 'rate(node_network_receive_bytes_total{{instance="{server}",device!="lo"}}[5m])',
	"db": 'rate(mysql_global_status_queries{{instance="{server}"}}[5m])',
}


def _get_prometheus_url_and_auth() -> tuple[str, str]:
	"""Return (url, password) for Prometheus query_range."""
	monitor_server = frappe.db.get_single_value("Press Settings", "monitor_server")
	if not monitor_server:
		frappe.throw("Monitor server not configured in Press Settings")
	password = get_decrypted_password("Monitor Server", monitor_server, "grafana_password")
	url = f"https://{monitor_server}/prometheus/api/v1/query_range"
	return url, password


def _query_range(promql: str, from_time: str, to_time: str) -> list:
	"""Execute a Prometheus range query and return values list."""
	url, password = _get_prometheus_url_and_auth()
	from_dt = datetime.fromisoformat(from_time)
	to_dt = datetime.fromisoformat(to_time)
	step = max(60, int((to_dt - from_dt).total_seconds() / 60))

	params: dict[str, str | float] = {
		"query": promql,
		"start": from_dt.timestamp(),
		"end": to_dt.timestamp(),
		"step": f"{step}s",
	}
	response = requests.get(url, params=params, auth=("frappe", password), timeout=15)
	return response.json().get("data", {}).get("result", [])


def _avg_from_result(result: list) -> float | None:
	"""Compute average value across all series and time points."""
	values = [float(v[1]) for r in result for v in r.get("values", []) if v[1] != "NaN"]
	if not values:
		return None
	return round(sum(values) / len(values), 2)


@mcp.tool()
@system_manager_only
def get_server_basic_metrics(server: str, from_time: str, to_time: str) -> dict:
	"""Fetch CPU, memory, disk, and load averages for a server over a time window.

	Args:
		server: Server name (hostname or Frappe doc name).
		from_time: Start of window (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: End of window (ISO: YYYY-MM-DD HH:MM:SS).
	"""
	metrics: dict = {}
	for metric_type in ("cpu", "memory", "disk", "load"):
		try:
			promql = _PROMQL[metric_type].format(server=server)
			result = _query_range(promql, from_time, to_time)
			avg = _avg_from_result(result)
			metrics[metric_type] = {"avg": avg, "unit": _unit(metric_type)}
		except Exception:
			metrics[metric_type] = {"avg": None, "error": "unavailable"}
	return cast("dict", redact(metrics))


@mcp.tool()
@system_manager_only
def get_server_metrics(server: str, metric_type: str, from_time: str, to_time: str) -> dict:
	"""Fetch a single metric type for a server over a time window.

	Args:
		server: Server name.
		metric_type: One of cpu, memory, disk, iops, network, load, db.
		from_time: Start of window (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: End of window (ISO: YYYY-MM-DD HH:MM:SS).
	"""
	if metric_type not in _METRIC_TYPES:
		frappe.throw(f"metric_type must be one of: {', '.join(sorted(_METRIC_TYPES))}")

	promql = _PROMQL[metric_type].format(server=server)
	result = _query_range(promql, from_time, to_time)
	values = [
		{"timestamp": v[0], "value": float(v[1]) if v[1] != "NaN" else None}
		for r in result
		for v in r.get("values", [])
	]
	payload = {"metric_type": metric_type, "server": server, "values": values, "unit": _unit(metric_type)}
	return cast("dict", redact(payload))


@mcp.tool()
@system_manager_only
def get_site_request_summary(site: str, from_time: str, to_time: str) -> dict:
	"""Fetch request count, 5xx errors, and avg latency for a site.

	Args:
		site: Site name (e.g. customer.example.com).
		from_time: Start of window (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: End of window (ISO: YYYY-MM-DD HH:MM:SS).
	"""
	log_server = frappe.db.get_single_value("Press Settings", "log_server")
	if not log_server:
		return cast("dict", redact({"error": "log_server not configured"}))

	password = get_decrypted_password("Log Server", log_server, "kibana_password")
	url = f"https://{log_server}/elasticsearch/filebeat-*/_search"

	from_dt = datetime.fromisoformat(from_time)
	to_dt = datetime.fromisoformat(to_time)

	query = {
		"size": 0,
		"query": {
			"bool": {
				"filter": [
					{"match_phrase": {"json.transaction_type": "request"}},
					{"match_phrase": {"json.site": site}},
					{
						"range": {
							"@timestamp": {
								"gte": int(from_dt.timestamp() * 1000),
								"lte": int(to_dt.timestamp() * 1000),
							}
						}
					},
				]
			}
		},
		"aggs": {
			"total_count": {"value_count": {"field": "json.duration"}},
			"avg_duration": {"avg": {"field": "json.duration"}},
			"error_5xx": {
				"filter": {"range": {"json.response_code": {"gte": 500}}},
				"aggs": {"count": {"value_count": {"field": "json.response_code"}}},
			},
		},
	}

	try:
		response = requests.post(url, json=query, auth=("frappe", password), timeout=15)
		aggs = response.json().get("aggregations", {})
		return cast(
			"dict",
			redact(
				{
					"site": site,
					"from_time": from_time,
					"to_time": to_time,
					"total_requests": aggs.get("total_count", {}).get("value", 0),
					"avg_duration_ms": round(aggs.get("avg_duration", {}).get("value") or 0, 2),
					"error_5xx_count": aggs.get("error_5xx", {}).get("count", {}).get("value", 0),
				}
			),
		)
	except Exception as exc:
		return cast("dict", redact({"error": str(exc)}))


@mcp.tool()
@system_manager_only
def get_uptime(site: str, from_time: str, to_time: str) -> dict:
	"""Fetch uptime probe data for a site over a time window.

	Args:
		site: Site name.
		from_time: Start of window (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: End of window (ISO: YYYY-MM-DD HH:MM:SS).
	"""
	try:
		url, password = _get_prometheus_url_and_auth()
		from_dt = datetime.fromisoformat(from_time)
		to_dt = datetime.fromisoformat(to_time)
		step = max(60, int((to_dt - from_dt).total_seconds() / 60))

		uptime_query = (
			f'avg_over_time(probe_success{{job="site",instance="{site}"}}[{step}s]) or on() vector(0)'
		)
		params: dict[str, str | float] = {
			"query": uptime_query,
			"start": from_dt.timestamp(),
			"end": to_dt.timestamp(),
			"step": f"{step}s",
		}
		response = requests.get(url, params=params, auth=("frappe", password), timeout=15)
		result = response.json().get("data", {}).get("result", [])
		values = [{"timestamp": v[0], "value": float(v[1])} for r in result for v in r.get("values", [])]
		avg_uptime = round(sum(v["value"] for v in values) / len(values), 4) if values else None
		return cast("dict", redact({"site": site, "avg_uptime": avg_uptime, "values": values[:20]}))
	except Exception as exc:
		return cast("dict", redact({"site": site, "error": str(exc)}))


def _unit(metric_type: str) -> str:
	units = {
		"cpu": "%",
		"memory": "%",
		"disk": "bytes",
		"load": "load",
		"iops": "%",
		"network": "bytes/s",
		"db": "qps",
	}
	return units.get(metric_type, "")


MAX_RAW_TIME_RANGE_HOURS = 24


@mcp.tool()
@system_manager_only
def query_prometheus_raw(query: str, from_time: str, to_time: str, step: str = "60s") -> dict:
	"""Run a raw PromQL range query against the Prometheus instance.

	Args:
		query: PromQL expression.
		from_time: Start time (ISO: YYYY-MM-DD HH:MM:SS).
		to_time: End time (ISO: YYYY-MM-DD HH:MM:SS).
		step: Step duration (e.g. 60s, 5m). Default 60s.
	"""
	from_dt = datetime.fromisoformat(from_time)
	to_dt = datetime.fromisoformat(to_time)
	hours = (to_dt - from_dt).total_seconds() / 3600
	if hours > MAX_RAW_TIME_RANGE_HOURS:
		frappe.throw(f"Time range exceeds {MAX_RAW_TIME_RANGE_HOURS}h limit")

	monitor_server = frappe.db.get_single_value("Press Settings", "monitor_server")
	if not monitor_server:
		return cast("dict", redact({"error": "monitor_server not configured"}))

	password = get_decrypted_password("Monitor Server", monitor_server, "grafana_password")
	url = f"https://{monitor_server}/prometheus/api/v1/query_range"
	params: dict[str, str | float] = {
		"query": query,
		"start": from_dt.timestamp(),
		"end": to_dt.timestamp(),
		"step": step,
	}
	try:
		response = requests.get(url, params=params, auth=("frappe", password), timeout=30)
		result = response.json().get("data", {}).get("result", [])
		return cast("dict", redact({"query": query, "result": result}))
	except Exception as exc:
		return cast("dict", redact({"error": str(exc)}))
