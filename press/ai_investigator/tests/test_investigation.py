# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import unittest
from datetime import datetime

import frappe

from press.ai_investigator.investigation import router, runner, targets


class TestAIInvestigatorInvestigation(unittest.TestCase):
	"""Test target resolution, intent routing, and continuation logic."""

	def setUp(self):
		self.cleanup()

	def tearDown(self):
		self.cleanup()

	def cleanup(self):
		frappe.db.rollback()

	def test_intent_routing_with_incident(self):
		"""Prioritize query keywords over default incident_rca."""
		incident_doc = {"name": "INC-0001", "type": "Database Down"}

		# Case 1: Specific query with slow queries -> database_performance
		self.assertEqual(
			router.classify_intent("The slow query log has some patterns", incident=incident_doc),
			"database_performance",
		)

		# Case 2: Specific query with CPU/memory -> server_performance
		self.assertEqual(
			router.classify_intent("High memory and cpu load on server", incident=incident_doc),
			"server_performance",
		)

		# Case 3: Ambiguous query with incident -> incident_rca fallback
		self.assertEqual(
			router.classify_intent("Help me check what happened", incident=incident_doc),
			"incident_rca",
		)

		# Case 4: Ambiguous query without incident -> general_question fallback
		self.assertEqual(
			router.classify_intent("Help me check what happened", incident=None),
			"general_question",
		)

	def test_target_resolution_from_incident_resource(self):
		"""Resolve target from resource_type/resource when present in incident."""
		site_name = "test-site.example.com"
		if not frappe.db.exists("Site", site_name):
			site = frappe.get_doc(
				{
					"doctype": "Site",
					"name": site_name,
					"status": "Active",
				}
			)
			site.insert(ignore_permissions=True)

		incident_doc = {
			"name": "INC-0002",
			"resource_type": "Site",
			"resource": site_name,
		}

		resolved = targets.resolve(incident=incident_doc)
		self.assertEqual(resolved["target_doctype"], "Site")
		self.assertEqual(resolved["target_name"], site_name)

	def test_target_resolution_server_fallback(self):
		"""Safely fallback to server link in incident only if it exists."""
		server_name = "test-server-ai-ops"
		if not frappe.db.exists("Server", server_name):
			server = frappe.get_doc(
				{
					"doctype": "Server",
					"name": server_name,
					"status": "Active",
				}
			)
			server.insert(ignore_permissions=True)

		incident_doc = {
			"name": "INC-0003",
			"server": server_name,
		}

		resolved = targets.resolve(incident=incident_doc)
		self.assertEqual(resolved["target_doctype"], "Server")
		self.assertEqual(resolved["target_name"], server_name)

		# Case 2: server does not exist -> resolve returns None targets
		incident_doc_invalid = {
			"name": "INC-0004",
			"server": "non-existent-server-name",
		}
		resolved_invalid = targets.resolve(incident=incident_doc_invalid)
		self.assertIsNone(resolved_invalid["target_doctype"])
		self.assertIsNone(resolved_invalid["target_name"])

	def test_continuation_logs_hypotheses_and_updates_doc(self):
		"""Verify that continue_investigation logs hypotheses and updates main doc fields."""
		site_name = "test-site-2.example.com"
		if not frappe.db.exists("Site", site_name):
			site = frappe.get_doc(
				{
					"doctype": "Site",
					"name": site_name,
					"status": "Active",
				}
			)
			site.insert(ignore_permissions=True)

		oi = frappe.get_doc(
			{
				"doctype": "Operational Investigation",
				"title": f"Test Investigation for {site_name}",
				"source": "Manual",
				"target_doctype": "Site",
				"target_name": site_name,
				"from_time": datetime.now(),
				"to_time": datetime.now(),
				"state_json": {
					"query": "slow site",
					"intent": "site_performance",
					"current_hypotheses": [],
				},
			}
		)
		oi.insert(ignore_permissions=True)

		# Call continuation with a database slow checking instruction
		# In runner.py, _map_instruction_to_checks maps "database slow" to ["get_slow_queries", "get_frequent_slow_queries"]
		runner.continue_investigation(oi.name, "check if the database is slow")

		# Reload the doc
		oi.reload()

		# Verify state_json has new hypotheses
		state = oi.state_json or {}
		self.assertTrue(len(state.get("current_hypotheses", [])) > 0)

		# Verify primary cause and confidence are updated in main doc
		self.assertIsNotNone(oi.primary_cause)
		self.assertTrue(oi.confidence > 0)

		# Verify that hypothesis entries were appended to Operational Investigation Log
		logs = frappe.get_all(
			"Operational Investigation Log",
			filters={"investigation": oi.name, "type": "hypothesis"},
			fields=["title", "data_json"],
		)
		self.assertTrue(len(logs) > 0)
		self.assertIn("Slow database queries impacting performance", [l.title for l in logs])
