# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import functools

import frappe


def system_manager_only(fn):
	"""Restrict a tool to System Manager role — second enforcement layer after the MCP endpoint guard."""

	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		frappe.only_for("System Manager")
		return fn(*args, **kwargs)

	return wrapper
