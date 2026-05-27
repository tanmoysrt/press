# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe

FORBIDDEN_ACTIONS = {
	"archive",
	"delete",
	"drop",
	"restore",
	"reinstall",
	"reboot_database_server",
	"disable_proxy",
	"remove_proxy",
	"ssh_write",
	"execute_command",
	"read_credentials",
	"read_env",
}


def check_action(action: str) -> None:
	"""Raise PermissionError if action is forbidden."""
	if action in FORBIDDEN_ACTIONS:
		raise frappe.PermissionError(f"Action '{action}' is not allowed via MCP.")
