"""Whitelisted API used by the Item Creator page."""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt

from exeliq_items import naming


# ---------------------------------------------------------------- helpers

def _parse(data):
    if isinstance(data, str):
        data = json.loads(data or "{}")
    return frappe._dict(data or {})


def _settings():
    return frappe.get_cached_doc("Exeliq Item Settings")


def _series_for(item_group):
    for row in _settings().code_series:
        if row.item_group == item_group:
            return row
    return None


def _existing_items():
    return frappe.get_all(
        "Item",
        fields=["name as item_code", "item_name", "disabled", "exl_model", "exl_item_type"],
        limit_page_length=0,
    )


def _hsn_field():
    meta = frappe.get_meta("Item")
    for f in ("gst_hsn_code", "hsn_code"):
        if meta.has_field(f):
            return f
    return None


def _type_doc(item_type):
    if not item_type:
        return None
    if not frappe.db.exists("Item Type", item_type):
        return None
    return frappe.get_cached_doc("Item Type", item_type)


# ---------------------------------------------------------------- page bootstrap

@frappe.whitelist()
def get_bootstrap():
    """Everything the page needs once on load."""
    settings = _settings()
    return {
        "groups": [r.item_group for r in settings.code_series],
        "hsn_field": _hsn_field(),
        "default_company": settings.default_company,
        "default_warehouse": settings.default_warehouse,
        "can_create": bool(frappe.has_permission("Item", "create")),
        # ERPNext overwrites item_code when Stock Settings names Items by Naming Series
        "naming_by_series": frappe.db.get_single_value("Stock Settings", "item_naming_by") == "Naming Series",
    }


@frappe.whitelist()
def get_type(item_type):
    doc = _type_doc(item_type)
    if not doc:
        frappe.throw(_("Item Type {0} not found").format(item_type))
    return {
        "name": doc.name,
        "disabled": cint(doc.disabled),
        "ask_type_name": cint(doc.get("ask_type_name")),
        "make_required": cint(doc.make_required),
        "model_mode": doc.model_mode or "Optional",
        "default_uom": doc.default_uom,
        "default_item_group": doc.default_item_group,
        "format_preview": doc.format_preview,
        "parameters": [
            {"label": p.parameter_label, "suffix": p.suffix or "", "mandatory": cint(p.mandatory)}
            for p in doc.parameters
        ],
    }


# ---------------------------------------------------------------- autocomplete

@frappe.whitelist()
def get_suggestions(item_type, field, txt="", parameter=None, type_name=None):
    """field = 'model' | 'param' | 'type_name'. Structured values rank above values mined from old names."""
    values = []

    if field == "type_name":
        # existing type prefixes from all item names - helps 'Other' users reuse a spelling
        counts = {}
        for name in frappe.get_all("Item", pluck="item_name", limit_page_length=0):
            t, rest = naming.split_type(name or "")
            if rest:
                counts[t] = counts.get(t, 0) + 1
        values = list(counts.items())
        return naming.filter_suggestions(values, txt)

    doc = _type_doc(item_type)
    lookup_type = (type_name if doc and doc.get("ask_type_name") else item_type) or item_type

    if field == "model":
        rows = frappe.db.sql(
            """select exl_model, count(*) from `tabItem`
               where exl_item_type=%s and ifnull(exl_model,'')!='' group by exl_model""",
            item_type,
        )
        values += [(r[0], 5 * r[1]) for r in rows]
    elif field == "param" and parameter:
        rows = frappe.db.sql(
            """select pv.value, count(*) from `tabItem Parameter Value` pv
               join `tabItem` i on i.name = pv.parent and pv.parenttype='Item'
               where i.exl_item_type=%s and pv.parameter=%s and ifnull(pv.value,'')!=''
               group by pv.value""",
            (item_type, parameter),
        )
        values += [(r[0], 5 * r[1]) for r in rows]

    # values mined from older, unstructured names of the same type
    names = frappe.get_all("Item", pluck="item_name", limit_page_length=0)
    values += list(naming.legacy_segment_counts(names, lookup_type).items())
    return naming.filter_suggestions(values, txt)


# ---------------------------------------------------------------- preview / validation

def _evaluate(data):
    """Build the name and run every check. Pure read - never writes."""
    errors = []
    doc = _type_doc(data.item_type)
    if not doc:
        return {"item_name": "", "errors": [_("Pick an Item Type")], "blocks": [], "warnings": []}
    if cint(doc.disabled):
        errors.append(_("Item Type {0} is disabled").format(doc.name))

    type_name = doc.name
    if cint(doc.get("ask_type_name")):
        type_name = naming.clean_part(data.type_name)
        if not type_name:
            errors.append(_("Enter the Type Name (e.g. Oscilloscope)"))
        elif "/" in type_name:
            errors.append(_("Type Name cannot contain '/'"))

    brand = naming.clean_part(data.brand)
    if brand and not frappe.db.exists("Brand", brand):
        errors.append(_("Brand {0} does not exist - create it first").format(brand))
    if cint(doc.make_required) and naming.is_generic(brand):
        errors.append(_("Make (Brand) is required for {0}").format(doc.name))

    model = naming.clean_part(data.model) if doc.model_mode != "No" else ""
    if doc.model_mode == "Required" and not model:
        errors.append(_("Model / Part No. is required for {0}").format(doc.name))

    given = {}
    for p in data.get("params") or []:
        given[(p.get("label") or "").lower()] = p.get("value")
    params, param_rows = [], []
    for p in doc.parameters:
        value = naming.clean_part(given.get(p.parameter_label.lower()))
        if cint(p.mandatory) and not value:
            errors.append(_("{0} is required").format(p.parameter_label))
        final = naming.apply_suffix(value, p.suffix)
        params.append((value, p.suffix))
        if final:
            param_rows.append({"parameter": p.parameter_label, "value": final})

    item_name = naming.build_name(type_name or doc.name, brand, model, params)
    if item_name == (type_name or doc.name):
        errors.append(_("Fill at least one of Make, Model or a parameter"))
    if len(item_name) > naming.MAX_NAME_LEN:
        errors.append(_("Name is {0} characters - the limit is {1}. Shorten some values.").format(
            len(item_name), naming.MAX_NAME_LEN))

    threshold = flt(_settings().similarity_threshold or 88) / 100.0
    blocks, warnings = naming.find_conflicts(
        item_name, _existing_items(), type_name=type_name, model=model, threshold=threshold
    )

    next_code = None
    if data.item_group:
        series = _series_for(data.item_group)
        if series:
            codes = frappe.get_all("Item", filters={"name": ["like", series.prefix + "%"]}, pluck="name",
                                   limit_page_length=0)
            next_code = naming.next_code(series.prefix, series.digits, codes)

    return {
        "item_name": item_name,
        "type_name": type_name,
        "brand": brand,
        "model": model,
        "param_rows": param_rows,
        "errors": errors,
        "blocks": blocks,
        "warnings": warnings,
        "next_code": next_code,
    }


@frappe.whitelist()
def preview(data):
    return _evaluate(_parse(data))


# ---------------------------------------------------------------- create

@frappe.whitelist()
def create_item(data, override_reason=None):
    frappe.has_permission("Item", "create", throw=True)
    data = _parse(data)
    result = _evaluate(data)

    if result["errors"]:
        frappe.throw("<br>".join(result["errors"]), title=_("Fix these first"))
    if result["blocks"]:
        lines = ["{0}: {1} ({2})".format(b["item_code"], b["item_name"], b["reason"]) for b in result["blocks"]]
        frappe.throw(_("This item already exists:") + "<br>" + "<br>".join(lines), title=_("Duplicate"))
    override_reason = (override_reason or "").strip()
    if result["warnings"] and not override_reason:
        frappe.throw(_("Similar items exist. Give a reason to create anyway."), title=_("Reason needed"))

    # ---- details
    if not data.item_group:
        frappe.throw(_("Item Group is required"))
    series = _series_for(data.item_group)
    if not series:
        frappe.throw(_("No item code series set for Item Group {0}. Add it in Exeliq Item Settings.").format(
            data.item_group))
    if not data.stock_uom:
        frappe.throw(_("UOM is required"))
    hsn_field = _hsn_field()
    if hsn_field and not data.hsn:
        frappe.throw(_("HSN/SAC is required"))

    is_fixed_asset = cint(data.is_fixed_asset)
    if is_fixed_asset and not data.asset_category:
        frappe.throw(_("Asset Category is required for a Fixed Asset"))

    settings = _settings()
    item = frappe.new_doc("Item")
    item.item_name = result["item_name"]
    item.item_group = data.item_group
    item.stock_uom = data.stock_uom
    item.description = (data.description or "").strip() or result["item_name"]
    item.is_fixed_asset = is_fixed_asset
    item.is_stock_item = 0 if is_fixed_asset else cint(data.is_stock_item)
    if is_fixed_asset:
        item.asset_category = data.asset_category
    if flt(data.valuation_rate):
        item.valuation_rate = flt(data.valuation_rate)
    if hsn_field:
        item.set(hsn_field, data.hsn)

    brand = result["brand"]
    if naming.is_generic(brand):
        brand = "GENERIC" if frappe.db.exists("Brand", "GENERIC") else None
    if brand:
        item.brand = brand

    if data.item_tax_template:
        item.append("taxes", {"item_tax_template": data.item_tax_template})
    if settings.default_company and settings.default_warehouse:
        item.append("item_defaults", {
            "company": settings.default_company,
            "default_warehouse": settings.default_warehouse,
        })

    item.exl_item_type = data.item_type
    item.exl_model = result["model"] or None
    item.exl_override_reason = override_reason if result["warnings"] else None
    for row in result["param_rows"]:
        item.append("exl_parameters", row)

    # ---- code from the group's series; skip forward if a number is already taken
    codes = frappe.get_all("Item", filters={"name": ["like", series.prefix + "%"]}, pluck="name",
                           limit_page_length=0)
    code = naming.next_code(series.prefix, series.digits, codes)
    for _attempt in range(20):
        if not frappe.db.exists("Item", code):
            break
        codes.append(code)
        code = naming.next_code(series.prefix, series.digits, codes)
    item.item_code = code
    item.insert()

    return {"item_code": item.name, "item_name": item.item_name}
