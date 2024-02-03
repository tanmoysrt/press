// Copyright (c) 2024, Frappe and contributors
// For license information, please see license.txt

frappe.ui.form.on("Performance Report", {
	refresh(frm) {
		frm.add_custom_button(__('Multiply 10^9 with Count & Time Field'), function(){
			format_fields_helper(frm.get_doc());
			frm.refresh_fields();
			msgprint("All the count & time fields with billion and billion_ps suffixes have been multiplied by 10^9");
			frm.remove_custom_button(__('Multiply 10^9 with Count & Time Field'));
    });
	},
});

function format_fields_helper(fields_map){
	for (const [key, value] of Object.entries(fields_map)) {
		if (typeof value === 'object') {
			format_fields_helper(value);
		} else {
			if (key.endsWith('_billion') || key.endsWith('_billion_ps')){
				if (typeof value === 'number'){
					fields_map[key] = value*1000000000;
				}
			}
		}
	}
	return fields_map;
}
