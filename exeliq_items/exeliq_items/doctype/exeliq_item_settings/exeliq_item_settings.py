import frappe
from frappe import _
from frappe.model.document import Document


class ExeliqItemSettings(Document):
    def validate(self):
        seen = set()
        for row in self.code_series:
            if row.item_group in seen:
                frappe.throw(_("Item Group {0} has more than one code series").format(row.item_group))
            seen.add(row.item_group)
            row.prefix = (row.prefix or "").strip()
            if not row.digits or row.digits < 1:
                row.digits = 4
