# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import frappe

if TYPE_CHECKING:
	from collections.abc import Callable

from press.ai_investigator.investigation import evidence, playbooks, router, targets

DEFAULT_TIME_RANGE_HOURS = 1
MAX_TIME_RANGE_HOURS = 24

_INSTRUCTION_TOOL_MAP: list[tuple[list[str], list[str]]] = [
	(["db ", "database", "slow query"], ["get_slow_queries", "get_frequent_slow_queries"]),
	(["error log", "errors", "exception"], ["get_site_error_logs"]),
	(["deploy", "deployment", "caused by deploy"], ["get_recent_jobs", "get_document_versions"]),
	(["slow api", "slow endpoint", "api perform"], ["get_slow_apis"]),
	(["worker", "queue", "background"], ["get_bench_processes"]),
	(["uptime", "down", "outage"], ["get_uptime", "get_site_error_logs"]),
	(["cpu", "memory", "server resource", "infra"], ["get_server_basic_metrics"]),
	(["request", "traffic", "load"], ["get_site_request_summary"]),
]


def start_investigation(
	query: str | None = None,
	incident_name: str | None = None,
	target_doctype: str | None = None,
	target_name: str | None = None,
	from_time: str | None = None,
	to_time: str | None = None,
	source: str = "Manual",
) -> str:
	"""Create an Operational Investigation doc and enqueue the first pass.

	Returns the doc name (e.g., OI-2026-00001).
	"""
	now = datetime.now()
	resolved_to = datetime.fromisoformat(to_time) if to_time else now
	default_from = resolved_to - timedelta(hours=DEFAULT_TIME_RANGE_HOURS)
	resolved_from = datetime.fromisoformat(from_time) if from_time else default_from

	# Clamp time range
	if (resolved_to - resolved_from).total_seconds() > MAX_TIME_RANGE_HOURS * 3600:
		resolved_from = resolved_to - timedelta(hours=MAX_TIME_RANGE_HOURS)

	doc = frappe.get_doc(
		{
			"doctype": "Operational Investigation",
			"title": query or (f"Incident {incident_name}" if incident_name else "Investigation"),
			"source": source,
			"status": "Queued",
			"incident": incident_name,
			"target_doctype": target_doctype,
			"target_name": target_name,
			"from_time": resolved_from,
			"to_time": resolved_to,
			"started_by": frappe.session.user,
			"state_json": {
				"query": query,
				"intent": None,
				"time_window": {
					"from": str(resolved_from),
					"to": str(resolved_to),
				},
				"current_hypotheses": [],
				"recommended_next_checks": [],
				"recommended_actions": [],
				"last_error": None,
			},
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()

	if query:
		evidence.append_log(doc.name, "message", "User", query)
	elif incident_name:
		evidence.append_log(doc.name, "message", "User", f"Investigate incident {incident_name}")

	if frappe.flags.in_test or frappe.conf.get("developer_mode"):
		run_first_pass(doc.name)
	else:
		job = frappe.enqueue(
			"press.ai_investigator.investigation.runner.run_first_pass",
			investigation_name=doc.name,
			queue="long",
			timeout=600,
		)
		doc.db_set("background_job_id", job.id if hasattr(job, "id") else "", update_modified=False)
		frappe.db.commit()

	return doc.name


def run_first_pass(investigation_name: str) -> None:
	"""Run the investigation: classify intent → resolve target → run playbook → store findings."""
	doc = frappe.get_doc("Operational Investigation", investigation_name)
	doc.db_set("status", "Running", update_modified=True)
	doc.db_set("started_at", datetime.now(), update_modified=False)
	frappe.db.commit()

	try:
		_execute_first_pass(doc)
	except Exception as exc:
		_handle_failure(doc, exc)
		raise


def _execute_first_pass(doc) -> None:
	"""Inner pass: classify → resolve → run steps → score hypotheses → update doc."""
	state: dict = json.loads(doc.state_json) if isinstance(doc.state_json, str) else (doc.state_json or {})
	from_time = str(doc.from_time)
	to_time = str(doc.to_time)

	incident_doc = _fetch_incident_doc(doc.incident)
	intent = router.classify_intent(state.get("query") or doc.title, incident=incident_doc)
	state["intent"] = intent

	target = targets.resolve(
		query=state.get("query"),
		incident=incident_doc,
		target_doctype=doc.target_doctype,
		target_name=doc.target_name,
	)
	_update_target_fields(doc, target)

	findings = _run_playbook_steps(doc, playbooks.get_playbook(intent), target, from_time, to_time)
	hypotheses = _score_hypotheses(findings, intent)
	for hyp in hypotheses:
		evidence.log_hypothesis(doc.name, hyp["title"], hyp["confidence"], hyp["evidence"])

	primary_cause, confidence = _determine_primary_cause(hypotheses, findings)
	state["current_hypotheses"] = hypotheses
	final_status = "Completed" if confidence >= 0.4 else "Needs Human"

	summary_text = _generate_ai_response(state.get("query") or doc.title, intent, target, findings)
	evidence.append_log(doc.name, "message", "Assistant", summary_text)

	doc.db_set("status", final_status, update_modified=True)
	doc.db_set("completed_at", datetime.now(), update_modified=False)
	doc.db_set("last_run_at", datetime.now(), update_modified=False)
	doc.db_set("summary", summary_text, update_modified=False)
	doc.db_set("primary_cause", primary_cause or "", update_modified=False)
	doc.db_set("confidence", confidence, update_modified=False)
	doc.db_set("state_json", json.dumps(state), update_modified=False)
	frappe.db.commit()


def _fetch_incident_doc(incident_name: str | None) -> dict | None:
	"""Fetch incident fields needed for target resolution."""
	if not incident_name:
		return None
	return frappe.db.get_value(
		"Incident",
		incident_name,
		["name", "server", "cluster", "status", "type", "subject", "resource_type", "resource"],
		as_dict=True,
	)


def _update_target_fields(doc, target: dict) -> None:
	"""Write resolved target and related resources back to the investigation doc."""
	related = target.get("related", {})
	fields: dict[str, str] = {}
	if target.get("target_doctype") and not doc.target_doctype:
		fields["target_doctype"] = target["target_doctype"]
	if target.get("target_name") and not doc.target_name:
		fields["target_name"] = target["target_name"]
	if related.get("server") and not doc.affected_server:
		fields["affected_server"] = related["server"]
	if related.get("bench") and not doc.affected_bench:
		fields["affected_bench"] = related["bench"]
	if related.get("database_server") and not doc.affected_database_server:
		fields["affected_database_server"] = related["database_server"]
	for field_name, value in fields.items():
		doc.db_set(field_name, value, update_modified=False)


def _run_playbook_steps(doc, steps: list, target: dict, from_time: str, to_time: str) -> list[dict]:
	"""Execute all playbook steps and return the list of findings."""
	findings: list[dict] = []
	tool_results: dict[str, object] = {}

	for step in steps:
		if step.condition and step.condition not in tool_results:
			continue
		result = _run_step(doc, step, target, from_time, to_time)
		if result is None:
			continue
		tool_results[step.tool] = result
		finding = _extract_finding(step.tool, result)
		if finding:
			findings.append(finding)
			evidence.log_finding(
				doc.name,
				finding["text"][:140],
				finding["text"],
				finding.get("type", "observation"),
				finding.get("confidence", 0.5),
			)
	return findings


def _run_step(doc, step, target: dict, from_time: str, to_time: str) -> object:
	"""Execute one playbook step, catch errors on non-required steps."""
	try:
		return _call_tool(step.tool, doc, target, from_time, to_time)
	except Exception as exc:
		evidence.append_log(doc.name, "error", f"{step.tool} failed", str(exc))
		doc.db_set("error_count", (doc.error_count or 0) + 1, update_modified=False)
		frappe.db.commit()
		if step.required:
			raise
		return None


def _call_tool(tool_name: str, doc, target: dict, from_time: str, to_time: str) -> object:
	"""Dispatch to the correct tool function with resolved parameters."""
	import time

	from press.ai_investigator import audit

	target_name = target.get("target_name") or doc.target_name or ""
	target_doctype = target.get("target_doctype") or doc.target_doctype or ""
	related = target.get("related", {})
	site = related.get("site") or (target_name if target_doctype == "Site" else None)
	server = related.get("server") or (target_name if target_doctype == "Server" else None)
	bench = related.get("bench") or (target_name if target_doctype == "Bench" else None)

	from press.ai_investigator.tools import jobs, logs, metrics
	from press.ai_investigator.tools.code_analysis import analyze_slow_endpoint
	from press.ai_investigator.tools.documents import get_document_versions
	from press.ai_investigator.tools.incidents import get_incident_details

	dispatch: dict[str, Callable[[], object]] = {
		"get_incident_details": lambda: get_incident_details(incident_name=doc.incident),
		"get_recent_jobs": (
			lambda: jobs.get_recent_jobs(
				target_doctype=target_doctype,
				target_name=target_name,
				from_time=from_time,
				to_time=to_time,
			)
			if target_doctype and target_name
			else []
		),
		"get_site_error_logs": (
			lambda: logs.get_site_error_logs(site=site, from_time=from_time, to_time=to_time) if site else []
		),
		"get_site_request_summary": (
			lambda: metrics.get_site_request_summary(site=site, from_time=from_time, to_time=to_time)
			if site
			else {}
		),
		"get_server_basic_metrics": (
			lambda: metrics.get_server_basic_metrics(server=server, from_time=from_time, to_time=to_time)
			if server
			else {}
		),
		"get_slow_apis": (
			lambda: logs.get_slow_apis(site=site, from_time=from_time, to_time=to_time) if site else []
		),
		"get_slow_queries": (
			lambda: logs.get_slow_queries(site=site, from_time=from_time, to_time=to_time) if site else []
		),
		"get_frequent_slow_queries": (
			lambda: logs.get_frequent_slow_queries(site=site, from_time=from_time, to_time=to_time)
			if site
			else []
		),
		"get_uptime": (
			lambda: metrics.get_uptime(site=site, from_time=from_time, to_time=to_time) if site else {}
		),
		"get_bench_processes": (lambda: jobs.get_bench_processes(server=server) if server else {}),
		"list_processes": (lambda: jobs.list_processes(server=server) if server else []),
		"get_bench_log": (
			lambda: logs.get_bench_log(
				bench=bench, log_type="frappe.log", from_time=from_time, to_time=to_time
			)
			if bench
			else ""
		),
		"get_document_versions": (
			lambda: get_document_versions(doctype=target_doctype, name=target_name)
			if target_doctype and target_name
			else []
		),
		"analyze_slow_endpoint": (
			lambda: analyze_slow_endpoint(site=site, endpoint_path="", from_time=from_time, to_time=to_time)
			if site
			else {}
		),
	}

	fn = dispatch.get(tool_name)
	if fn is None:
		return None

	start = time.monotonic()
	result = fn()
	duration_ms = int((time.monotonic() - start) * 1000)

	evidence.log_tool_call(
		doc.name,
		tool_name,
		{"target": target_name, "from": from_time, "to": to_time},
		_summarise(result),
		duration_ms,
		"success",
	)
	audit.record_tool_call(tool_name, frappe.session.user, target_name, "success", duration_ms)
	return result


def _summarise(result: object) -> str:
	"""One-line summary of a tool result for log storage."""
	if result is None:
		return "no data"
	if isinstance(result, list):
		return f"{len(result)} items"
	if isinstance(result, dict):
		return f"dict with keys: {', '.join(list(result.keys())[:5])}"
	text = str(result)
	return text[:200] if len(text) > 200 else text


def _extract_finding(tool_name: str, result: object) -> dict | None:
	"""Extract a finding from a tool result."""
	if not result:
		return None
	if isinstance(result, list) and len(result) == 0:
		return None

	is_list = isinstance(result, list)
	n = len(result) if is_list else 0  # type: ignore[arg-type]
	summaries: dict[str, str] = {
		"get_site_error_logs": f"Found {n} error log entries" if is_list else "Error logs retrieved",
		"get_slow_queries": f"Found {n} slow queries" if is_list else "Slow queries retrieved",
		"get_slow_apis": f"Found {n} slow API paths" if is_list else "Slow APIs retrieved",
		"get_frequent_slow_queries": (
			f"Found {n} frequent slow query patterns"
			if isinstance(result, list)
			else "Frequent slow queries retrieved"
		),
	}

	text = summaries.get(tool_name, f"{tool_name}: {_summarise(result)}")
	return {"type": "observation", "text": text, "source": tool_name, "confidence": 0.5}


def _score_hypotheses(findings: list[dict], intent: str) -> list[dict]:
	"""Produce simple scored hypotheses from the findings list."""
	if not findings:
		return []

	hypothesis_map: dict[str, dict] = {
		"get_site_error_logs": {
			"title": "Application errors detected",
			"evidence": "Error logs show exceptions during the investigation window.",
			"confidence": 0.7,
		},
		"get_slow_queries": {
			"title": "Slow database queries impacting performance",
			"evidence": "Slow query log shows queries exceeding threshold.",
			"confidence": 0.65,
		},
		"get_server_basic_metrics": {
			"title": "Server resource pressure",
			"evidence": "Server metrics retrieved for analysis.",
			"confidence": 0.5,
		},
	}

	hypotheses = []
	seen = set()
	for finding in findings:
		source = finding.get("source", "")
		if source in hypothesis_map and source not in seen:
			seen.add(source)
			hypotheses.append(hypothesis_map[source])

	return hypotheses


def _determine_primary_cause(hypotheses: list[dict], findings: list[dict]) -> tuple[str, float]:
	"""Pick the highest-confidence hypothesis as the primary cause."""
	if not hypotheses:
		return ("", 0.0)
	best = max(hypotheses, key=lambda h: h.get("confidence", 0))
	return (best["title"], best.get("confidence", 0.0))


def _generate_ai_response(query: str, intent: str, target: dict, findings: list[dict]) -> str:
	"""Call LLM to analyse tool findings; fallback to a plain summary on error."""
	try:
		from press.ai_investigator import llm as llm_module

		client = llm_module.get_client()
		model = llm_module.get_model("haiku")
		target_desc = (
			f"{target.get('target_doctype')} **{target.get('target_name')}**"
			if target.get("target_name")
			else "no specific resource identified in the query"
		)
		findings_text = (
			"\n".join(f"- {f['text']}" for f in findings) if findings else "No issues detected by tools."
		)
		prompt = (
			f'User query: "{query}"\nIntent: {intent}\nTarget: {target_desc}\n\n'
			f"Tool findings:\n{findings_text}\n\n"
			"Reply in 3-5 sentences: what was checked, what was found, and what to do next. "
			"Be direct and technical. "
			"If no target resource was identified, ask the user to specify the site or server name."
		)
		msg = client.messages.create(
			model=model, max_tokens=400, messages=[{"role": "user", "content": prompt}]
		)
		return msg.content[0].text.strip()
	except Exception:
		return _build_summary(intent, target, findings)


def _generate_continuation_response(instruction: str, new_findings: list[dict]) -> str:
	"""Call LLM to generate a follow-up response; fallback to plain summary on error."""
	try:
		from press.ai_investigator import llm as llm_module

		client = llm_module.get_client()
		model = llm_module.get_model("haiku")
		findings_text = (
			"\n".join(f"- {f['text']}" for f in new_findings) if new_findings else "No new findings."
		)
		prompt = (
			f'User instruction: "{instruction}"\n\nNew findings:\n{findings_text}\n\n'
			"Reply in 2-4 sentences summarising what was found and recommended next steps. Be direct."
		)
		msg = client.messages.create(
			model=model, max_tokens=300, messages=[{"role": "user", "content": prompt}]
		)
		return msg.content[0].text.strip()
	except Exception:
		return _build_continuation_response(new_findings, instruction)


def _build_summary(intent: str, target: dict, findings: list[dict]) -> str:
	"""Build a short human-readable summary of the investigation."""
	target_desc = ""
	if target.get("target_name"):
		target_desc = f" for {target['target_doctype']} {target['target_name']}"

	finding_count = len(findings)
	return f"Investigation ({intent}){target_desc} completed. Found {finding_count} observation(s)."


def _handle_failure(doc, exc: Exception) -> None:
	"""Mark investigation as Failed and record the error."""
	evidence.append_log(doc.name, "error", "Investigation failed", str(exc))
	doc.db_set("status", "Failed", update_modified=True)
	doc.db_set("completed_at", datetime.now(), update_modified=False)
	frappe.db.commit()


def continue_investigation(investigation_name: str, instruction: str) -> dict:
	"""Run follow-up checks on an existing investigation based on a user instruction."""
	doc = frappe.get_doc("Operational Investigation", investigation_name)
	evidence.append_log(investigation_name, "message", "User", instruction)

	tools_to_run = _map_instruction_to_checks(instruction)
	ran_tools = _get_ran_tools(investigation_name)
	time_shifted = _is_time_shift(instruction)

	target = targets.resolve(
		target_doctype=doc.target_doctype,
		target_name=doc.target_name,
	)

	if time_shifted:
		from_time, to_time = _shift_window(str(doc.from_time), str(doc.to_time))
	else:
		from_time, to_time = str(doc.from_time), str(doc.to_time)

	new_findings: list[dict] = []
	for tool_name in tools_to_run:
		if tool_name in ran_tools and not time_shifted:
			continue
		step = playbooks.PlaybookStep(tool=tool_name, required=False)
		result = _run_step(doc, step, target, from_time, to_time)
		if result is None:
			continue
		finding = _extract_finding(tool_name, result)
		if finding:
			new_findings.append(finding)
			evidence.log_finding(
				doc.name,
				finding["text"][:140],
				finding["text"],
				finding.get("type", "observation"),
				finding.get("confidence", 0.5),
			)

	state: dict = json.loads(doc.state_json) if isinstance(doc.state_json, str) else (doc.state_json or {})
	_merge_hypotheses(doc, new_findings, state.get("intent", "general"))

	state = json.loads(doc.state_json) if isinstance(doc.state_json, str) else (doc.state_json or {})
	primary_cause, confidence = _determine_primary_cause(state.get("current_hypotheses", []), new_findings)
	doc.db_set("primary_cause", primary_cause or "", update_modified=False)
	doc.db_set("confidence", confidence, update_modified=False)

	response_text = _generate_continuation_response(instruction, new_findings)
	evidence.append_log(investigation_name, "message", "Assistant", response_text)

	if doc.status == "Needs Human" and new_findings:
		doc.db_set("status", "Completed", update_modified=True)

	frappe.db.commit()
	return {
		"investigation": investigation_name,
		"response": response_text,
		"new_findings_count": len(new_findings),
	}


def _map_instruction_to_checks(instruction: str) -> list[str]:
	"""Map a natural language instruction to a list of tool names."""
	lower = instruction.lower()
	matched: list[str] = []
	for keywords, tools in _INSTRUCTION_TOOL_MAP:
		if any(kw in lower for kw in keywords):
			matched.extend(tools)
	if not matched:
		return ["get_site_error_logs", "get_site_request_summary"]
	return list(dict.fromkeys(matched))


def _get_ran_tools(investigation_name: str) -> set[str]:
	"""Return the set of tool names already called in this investigation."""
	logs = frappe.get_all(
		"Operational Investigation Log",
		filters={"investigation": investigation_name, "type": "tool_call"},
		fields=["title"],
		limit=200,
	)
	return {log["title"] for log in logs}


def _is_time_shift(instruction: str) -> bool:
	"""Return True if the instruction asks to shift the time window."""
	lower = instruction.lower()
	return any(phrase in lower for phrase in ["previous hour", "last hour", "hour ago", "compare", "before"])


def _shift_window(from_time: str, to_time: str) -> tuple[str, str]:
	"""Shift both window endpoints back by one hour."""
	shift = timedelta(hours=1)
	new_from = datetime.fromisoformat(from_time) - shift
	new_to = datetime.fromisoformat(to_time) - shift
	return str(new_from), str(new_to)


def _merge_hypotheses(doc, new_findings: list[dict], intent: str) -> None:
	"""Merge new hypotheses into the investigation's state_json, boosting existing ones."""
	state: dict = json.loads(doc.state_json) if isinstance(doc.state_json, str) else (doc.state_json or {})
	existing: list[dict] = state.get("current_hypotheses", [])
	existing_titles = {h["title"]: i for i, h in enumerate(existing)}

	new_hypotheses = _score_hypotheses(new_findings, intent)
	for hyp in new_hypotheses:
		if hyp["title"] in existing_titles:
			idx = existing_titles[hyp["title"]]
			boosted = min(existing[idx].get("confidence", 0.5) + 0.1, 0.95)
			existing[idx]["confidence"] = boosted
			evidence.log_hypothesis(doc.name, hyp["title"], boosted, existing[idx]["evidence"])
		else:
			existing.append(hyp)
			existing_titles[hyp["title"]] = len(existing) - 1
			evidence.log_hypothesis(doc.name, hyp["title"], hyp["confidence"], hyp["evidence"])

	state["current_hypotheses"] = existing
	doc.db_set("state_json", json.dumps(state), update_modified=False)


def _build_continuation_response(new_findings: list[dict], instruction: str) -> str:
	"""Build a short response text summarising the continuation run."""
	if not new_findings:
		return f"No new findings for: {instruction}"
	titles = ", ".join(f["text"][:60] for f in new_findings[:5])
	return f"Found {len(new_findings)} new observation(s): {titles}"
