import frappe

OLD = "Bidirectional Power Supply"
NEW = "Programmable DC Bidirectional Power Supply"


def execute():
    # 1. rename the type (links on Items follow automatically)
    if frappe.db.exists("Item Type", OLD) and not frappe.db.exists("Item Type", NEW):
        frappe.rename_doc("Item Type", OLD, NEW, force=True)
        frappe.db.set_value("Item Type", NEW, "item_type_name", NEW, update_modified=False)

    # 2. every parameter mandatory, except catch-all types where the user types the name (Other)
    for name in frappe.get_all("Item Type", filters={"ask_type_name": 0}, pluck="name"):
        doc = frappe.get_doc("Item Type", name)
        changed = name == NEW
        for p in doc.parameters:
            if not p.mandatory:
                p.mandatory = 1
                changed = True
        if changed:
            doc.flags.ignore_permissions = True
            doc.save()  # also refreshes the Name Format preview
