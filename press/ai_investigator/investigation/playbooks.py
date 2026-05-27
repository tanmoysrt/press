# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from dataclasses import dataclass


@dataclass
class PlaybookStep:
	"""One tool call in an investigation playbook."""

	tool: str
	required: bool = True
	condition: str | None = None  # skip if this finding type absent


def _step(tool: str, required: bool = True, condition: str | None = None) -> PlaybookStep:
	return PlaybookStep(tool=tool, required=required, condition=condition)


PLAYBOOKS: dict[str, list[PlaybookStep]] = {
	"incident_rca": [
		_step("get_incident_details"),
		_step("get_recent_jobs"),
		_step("get_site_error_logs", required=False),
		_step("get_site_request_summary", required=False),
		_step("get_server_basic_metrics", required=False),
	],
	"site_performance": [
		_step("get_site_request_summary"),
		_step("get_slow_apis", required=False),
		_step("get_slow_queries", required=False),
		_step("get_server_basic_metrics", required=False),
		_step("get_recent_jobs", required=False),
	],
	"server_performance": [
		_step("get_server_basic_metrics"),
		_step("list_processes", required=False),
		_step("get_bench_processes", required=False),
		_step("get_recent_jobs", required=False),
	],
	"bench_performance": [
		_step("get_bench_processes"),
		_step("get_bench_log", required=False),
		_step("get_server_basic_metrics", required=False),
	],
	"downtime_explanation": [
		_step("get_uptime"),
		_step("get_site_request_summary", required=False),
		_step("get_site_error_logs", required=False),
		_step("get_recent_jobs", required=False),
		_step("get_server_basic_metrics", required=False),
	],
	"recent_changes": [
		_step("get_recent_jobs"),
		_step("get_document_versions", required=False),
	],
	"database_performance": [
		_step("get_slow_queries"),
		_step("get_frequent_slow_queries", required=False),
		_step("get_site_request_summary", required=False),
		_step("get_server_basic_metrics", required=False),
	],
}

_GENERAL_QUESTION_PLAYBOOK: list[PlaybookStep] = [
	_step("get_site_request_summary", required=False),
	_step("get_server_basic_metrics", required=False),
	_step("get_recent_jobs", required=False),
]


def get_playbook(intent: str) -> list[PlaybookStep]:
	"""Return the ordered list of steps for the given intent."""
	return PLAYBOOKS.get(intent, _GENERAL_QUESTION_PLAYBOOK)
