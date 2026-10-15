"""Custom fields on Item, default settings and one-time Item Type seeding.

Idempotent: safe on every migrate. Item Types are seeded only once (types_seeded flag),
so types you edit or delete later are never re-created.
"""

import json
import os

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

DEFAULT_SERIES = [
    ("COTS", "EX-NO-COTS-", 4),
    ("Consumables", "EX-NO-CONS-", 4),
    ("Sub-Assemblies", "EX-NO-SA-", 4),
]


def after_install():
    setup()


def after_migrate():
    setup()


def setup():
    make_custom_fields()
    seed_settings_and_types()


def make_custom_fields():
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "exl_naming_section",
                    "fieldtype": "Section Break",
                    "label": "Structured Name",
                    "insert_after": "description",
                    "collapsible": 1,
                },
                {
                    "fieldname": "exl_item_type",
                    "fieldtype": "Link",
                    "label": "Item Type (Naming)",
                    "options": "Item Type",
                    "insert_after": "exl_naming_section",
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "exl_model",
                    "fieldtype": "Data",
                    "label": "Model / Part No.",
                    "insert_after": "exl_item_type",
                    "in_standard_filter": 1,
                },
                {
                    "fieldname": "exl_column_break",
                    "fieldtype": "Column Break",
                    "insert_after": "exl_model",
                },
                {
                    "fieldname": "exl_override_reason",
                    "fieldtype": "Small Text",
                    "label": "Created Despite Warning - Reason",
                    "insert_after": "exl_column_break",
                    "read_only": 1,
                },
                {
                    "fieldname": "exl_parameters",
                    "fieldtype": "Table",
                    "label": "Parameters",
                    "options": "Item Parameter Value",
                    "insert_after": "exl_override_reason",
                },
            ]
        },
        update=True,
    )


def seed_settings_and_types():
    settings = frappe.get_single("Exeliq Item Settings")
    changed = False

    if not settings.default_company:
        company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
        if company:
            settings.default_company = company
            changed = True

    if not settings.default_warehouse and settings.default_company:
        abbr = frappe.db.get_value("Company", settings.default_company, "abbr")
        wh = "Stores - {0}".format(abbr) if abbr else None
        if wh and frappe.db.exists("Warehouse", wh):
            settings.default_warehouse = wh
            changed = True

    if not settings.code_series:
        for group, prefix, digits in DEFAULT_SERIES:
            if frappe.db.exists("Item Group", group):
                settings.append("code_series", {"item_group": group, "prefix": prefix, "digits": digits})
                changed = True

    if not settings.types_seeded:
        seed_item_types()
        settings.types_seeded = 1
        changed = True

    if changed:
        settings.flags.ignore_permissions = True
        settings.save()
        frappe.db.commit()


def seed_item_types():
    path = os.path.join(os.path.dirname(__file__), "item_types_seed.json")
    with open(path) as fh:
        rows = json.load(fh)

    for row in rows:
        name = row["item_type_name"]
        if frappe.db.exists("Item Type", name):
            continue
        doc = frappe.new_doc("Item Type")
        doc.item_type_name = name
        doc.make_required = row.get("make_required", 0)
        doc.ask_type_name = row.get("ask_type_name", 0)
        doc.model_mode = row.get("model_mode") or "Optional"
        if row.get("default_uom") and frappe.db.exists("UOM", row["default_uom"]):
            doc.default_uom = row["default_uom"]
        if row.get("default_item_group") and frappe.db.exists("Item Group", row["default_item_group"]):
            doc.default_item_group = row["default_item_group"]
        for label in row.get("parameters") or []:
            doc.append("parameters", {"parameter_label": label, "mandatory": row.get("mandatory", 0)})
        doc.flags.ignore_permissions = True
        doc.insert()
