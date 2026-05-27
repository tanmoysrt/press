# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import re

_KEYWORD_MAP: dict[str, list[str]] = {
	"incident_rca": ["incident", "inc-", "outage", "alert", "pagerduty", "rca"],
	"site_performance": ["slow site", "slow request", "site performance", "high latency", "response time"],
	"server_performance": ["server performance", "cpu", "memory", "disk", "load", "swap"],
	"bench_performance": ["bench", "worker", "supervisor", "queue"],
	"database_performance": ["slow query", "database slow", "db slow", "mariadb", "query performance"],
	"downtime_explanation": ["down", "downtime", "unavailable", "not responding", "unreachable", "offline"],
	"recent_changes": ["recent change", "deploy", "migration", "update", "what changed", "rollback"],
	"job_failure": ["job failed", "agent job", "job failure", "failed job"],
	"capacity_check": ["capacity", "disk full", "running out", "space"],
	"safe_action_request": ["restart", "reload", "migrate", "rebuild", "scale"],
}


def classify_intent(query: str, incident=None) -> str:
	"""Classify query into one of the known investigation intents.

	Uses keyword matching; falls back to general_question for ambiguous input.
	"""
	lowered = query.lower() if query else ""

	for intent, keywords in _KEYWORD_MAP.items():
		for keyword in keywords:
			if re.search(re.escape(keyword), lowered):
				return intent

	if incident is not None:
		return "incident_rca"

	return "general_question"
