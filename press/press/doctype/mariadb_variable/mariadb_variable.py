# Copyright (c) 2023, Frappe and contributors
# For license information, please see license.txt
from __future__ import annotations

from typing import TYPE_CHECKING

import frappe
from frappe.model.document import Document

if TYPE_CHECKING:
	from press.press.doctype.database_server.database_server import DatabaseServer


class MariaDBVariable(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		configurable_by_user: DF.Check
		datatype: DF.Literal["Int", "Float", "Str"]
		default_value: DF.Data | None
		doc_section: DF.Literal["server", "replication-and-binary-log", "innodb"]
		dynamic: DF.Check
		set_on_new_servers: DF.Check
		skippable: DF.Check
		title: DF.Data | None
	# end: auto-generated types

	def get_default_value(self):
		if not (value := self.default_value):
			frappe.throw("Default Value is required")
		match self.datatype:
			case "Int":
				return int(value)
			case "Float":
				return float(value)
		return value

	@frappe.whitelist()
	def set_on_all_servers(self):
		value = self.get_default_value()
		servers = frappe.get_all(
			"Database Server", {"status": "Active", "is_self_hosted": False}, pluck="name"
		)
		for server_name in servers:
			server: DatabaseServer = frappe.get_doc("Database Server", server_name)
			server.add_or_update_mariadb_variable(self.name, f"value_{self.datatype.lower()}", value)

	def set_on_server(self, server: DatabaseServer):
		value = self.get_default_value()
		server.add_or_update_mariadb_variable(self.name, f"value_{self.datatype.lower()}", value)
