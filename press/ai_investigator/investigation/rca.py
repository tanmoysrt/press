# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe

from press.ai_investigator import llm
from press.ai_investigator.investigation import evidence


def finalize_rca(investigation_name: str) -> str:
	"""Generate and store the RCA markdown for a completed investigation."""
	doc = frappe.get_doc("Operational Investigation", investigation_name)
	if doc.rca_markdown:
		return doc.rca_markdown

	tool_calls = _load_logs_by_type(investigation_name, "tool_call")
	findings = _load_logs_by_type(investigation_name, "finding")
	hypotheses = _load_logs_by_type(investigation_name, "hypothesis")
	action_results = _load_logs_by_type(investigation_name, "action_result")

	timeline_rows = _build_timeline_rows(tool_calls, findings)
	evidence_bullets = _build_evidence_bullets(findings)
	action_taken = _build_action_taken_text(action_results)
	primary_hyp = _pick_primary_hypothesis(hypotheses)

	primary_cause = primary_hyp["title"] if primary_hyp else "Unknown"
	confidence = primary_hyp["data_json"].get("confidence", 0.0) if primary_hyp else 0.0

	summary = _llm_summarize(doc, findings, primary_cause, confidence)
	follow_ups = _build_follow_ups(doc, hypotheses)
	root_cause = _build_root_cause_prose(primary_hyp)

	markdown_text = _render_rca_markdown(
		doc, summary, timeline_rows, evidence_bullets, root_cause, action_taken, follow_ups
	)

	doc.db_set("rca_markdown", markdown_text, update_modified=False)
	evidence.append_log(investigation_name, "rca", "RCA generated", markdown_text)
	return markdown_text


def _load_logs_by_type(investigation_name: str, log_type: str) -> list[dict]:
	"""Fetch all logs of a given type for an investigation."""
	return frappe.get_all(
		"Operational Investigation Log",
		filters={"investigation": investigation_name, "type": log_type},
		fields=["title", "content", "data_json", "timestamp"],
		order_by="timestamp asc",
		limit=100,
	)


def _build_timeline_rows(tool_calls: list[dict], findings: list[dict]) -> list[tuple[str, str]]:
	"""Merge tool calls and findings into a sorted timeline."""
	rows: list[tuple[str, str, str]] = []
	for log in tool_calls:
		rows.append((str(log["timestamp"]), str(log["timestamp"])[:19], f"Tool: {log['title']}"))
	for log in findings:
		rows.append((str(log["timestamp"]), str(log["timestamp"])[:19], f"Finding: {log['title']}"))
	rows.sort(key=lambda r: r[0])
	return [(r[1], r[2]) for r in rows]


def _build_evidence_bullets(findings: list[dict]) -> list[str]:
	"""Build a list of bullet strings from finding logs."""
	return [log["title"] for log in findings if log.get("title")]


def _build_action_taken_text(action_results: list[dict]) -> str:
	"""Build a prose description of actions taken."""
	if not action_results:
		return "No actions recorded."
	lines = [f"- {log['title']}: {log.get('content', '')}" for log in action_results]
	return "\n".join(lines)


def _pick_primary_hypothesis(hypotheses: list[dict]) -> dict | None:
	"""Return the hypothesis with the highest confidence."""
	if not hypotheses:
		return None
	return max(hypotheses, key=lambda h: (h.get("data_json") or {}).get("confidence", 0.0))


def _llm_summarize(doc, findings: list[dict], primary_cause: str, confidence: float) -> str:
	"""Call the LLM for a 2-3 sentence summary; fall back to deterministic text."""
	try:
		client = llm.get_client()
		model = llm.get_model("sonnet")
		bullet_findings = "\n".join(f"- {f['title']}" for f in findings[:10])
		prompt = (
			"You are an SRE assistant. Based on the following investigation findings and hypotheses,"
			" write a 2-3 sentence summary of what happened.\n\n"
			f"Findings:\n{bullet_findings}\n\n"
			f"Primary cause: {primary_cause}\n"
			f"Confidence: {confidence:.0%}\n\n"
			"Write only the summary paragraph, no headers."
		)
		response = client.messages.create(
			model=model,
			max_tokens=300,
			messages=[{"role": "user", "content": prompt}],
		)
		return response.content[0].text.strip()
	except Exception:
		count = len(findings)
		return (
			f"Investigation completed with {count} observation(s). "
			f"Primary cause identified: {primary_cause} (confidence: {confidence:.0%})."
		)


def _build_follow_ups(doc, hypotheses: list[dict]) -> list[str]:
	"""Collect follow-up actions from state_json and low-confidence hypotheses."""
	state = doc.state_json or {}
	follow_ups: list[str] = list(state.get("recommended_next_checks", []))
	for hyp in hypotheses:
		conf = (hyp.get("data_json") or {}).get("confidence", 1.0)
		if conf < 0.5:
			follow_ups.append(f"Investigate unconfirmed hypothesis: {hyp['title']}")
	return follow_ups


def _build_root_cause_prose(primary_hyp: dict | None) -> str:
	"""Build the root cause prose section from the primary hypothesis."""
	if not primary_hyp:
		return "Root cause could not be determined from available evidence."
	content = primary_hyp.get("content") or ""
	return content if content else f"Evidence points to: {primary_hyp.get('title', 'unknown')}."


def _format_timeline_table(timeline_rows: list[tuple[str, str]]) -> str:
	"""Render timeline rows as a markdown table."""
	if not timeline_rows:
		return "| Time | Event |\n|------|-------|\n| — | No events recorded |"
	header = "| Time | Event |\n|------|-------|"
	body = "\n".join(f"| {t} | {e} |" for t, e in timeline_rows)
	return f"{header}\n{body}"


def _format_evidence_section(evidence_bullets: list[str]) -> str:
	"""Render evidence bullets as a markdown list."""
	if not evidence_bullets:
		return "- No findings recorded."
	return "\n".join(f"- {b}" for b in evidence_bullets)


def _format_follow_ups_section(follow_ups: list[str]) -> str:
	"""Render follow-ups as a markdown checklist."""
	if not follow_ups:
		return "- [ ] No follow-ups identified."
	return "\n".join(f"- [ ] {item}" for item in follow_ups)


def _render_rca_markdown(
	doc,
	summary: str,
	timeline_rows: list[tuple[str, str]],
	evidence_bullets: list[str],
	root_cause: str,
	action_taken: str,
	follow_ups: list[str],
) -> str:
	"""Assemble the full RCA markdown document."""
	title = doc.incident or doc.name
	affected_parts = []
	if doc.affected_site:
		affected_parts.append(f"Site: {doc.affected_site}")
	if doc.affected_server:
		affected_parts.append(f"Server: {doc.affected_server}")
	if doc.affected_bench:
		affected_parts.append(f"Bench: {doc.affected_bench}")
	affected_str = ", ".join(affected_parts) if affected_parts else "Unknown"

	primary_cause = doc.primary_cause or "Unknown"
	confidence = doc.confidence or 0.0
	from_time = str(doc.from_time)
	to_time = str(doc.to_time)

	timeline_table = _format_timeline_table(timeline_rows)
	evidence_section = _format_evidence_section(evidence_bullets)
	follow_ups_section = _format_follow_ups_section(follow_ups)

	return f"""# RCA: {title}

## Summary
{summary}

## Impact
- Affected: {affected_str}
- Window: {from_time} - {to_time}

## Timeline
{timeline_table}

## Root Cause
Primary: {primary_cause}
Confidence: {confidence:.0%}

{root_cause}

## Evidence
{evidence_section}

## Action Taken
{action_taken}

## Follow-ups
{follow_ups_section}
"""
