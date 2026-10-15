import frappe
from frappe import _
from frappe.model.document import Document

from exeliq_items.naming import clean_part


class ItemType(Document):
    def validate(self):
        self.item_type_name = clean_part(self.item_type_name)
        if not self.item_type_name:
            frappe.throw(_("Item Type is required"))
        if "/" in self.item_type_name:
            frappe.throw(_("Item Type cannot contain '/' because it separates the parts of the name"))

        seen = set()
        for row in self.parameters:
            row.parameter_label = clean_part(row.parameter_label)
            row.suffix = (row.suffix or "").strip()
            key = (row.parameter_label or "").lower()
            if key in seen:
                frappe.throw(_("Parameter {0} is listed twice").format(row.parameter_label))
            seen.add(key)
        if len(self.parameters) > 8:
            frappe.throw(_("Keep it to 8 parameters or fewer so names stay readable"))

        self.format_preview = self.get_format_preview()

    def get_format_preview(self):
        parts = ["Make" if self.make_required else "[Make]"]
        if self.model_mode == "Required":
            parts.append("Model")
        elif self.model_mode == "Optional":
            parts.append("[Model]")
        for row in self.parameters:
            label = row.parameter_label + ((" " + row.suffix) if row.suffix else "")
            parts.append(label if row.mandatory else "[" + label + "]")
        type_label = "<Type Name>" if self.ask_type_name else self.item_type_name
        return "{0} - {1}".format(type_label, "/".join(parts))
