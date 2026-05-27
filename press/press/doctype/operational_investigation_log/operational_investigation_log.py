# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class OperationalInvestigationLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		content: DF.LongText | None
		data_json: DF.JSON | None
		investigation: DF.Link
		timestamp: DF.Datetime | None
		title: DF.Data | None
		type: DF.Literal[
			"message",
			"finding",
			"hypothesis",
			"tool_call",
			"action_plan",
			"action_result",
			"rca",
			"error",
			"system",
		]
	# end: auto-generated types

	"""Append-only event log for an investigation."""
