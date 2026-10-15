# Exeliq Items

Structured Item creation for ERPNext. Names are built as

    Type - Make/Model/P1/P2/P3

and checked against every existing Item before creation.

## What's inside

| Piece | Where | Purpose |
|---|---|---|
| **New Item** page | `/app/item-creator` (also a button on the Item list) | Fill → check → create |
| **Item Type** doctype | `/app/item-type` | One template per kind of item: Make required?, Model required/optional/no, parameters in order, default group & UOM |
| **Exeliq Item Settings** | `/app/exeliq-item-settings` | Item code series per Item Group, default company & warehouse, similarity threshold |
| Custom fields on **Item** | "Structured Name" section | Item Type, Model / Part No., parameter values, override reason |

## Name rules

* Make = Brand name as stored. Left out when the brand is blank or GENERIC.
* Empty parts are skipped. Spacing is cleaned: single spaces, none around `/`.
* A parameter with a Unit Suffix (e.g. `A`) gets it added when the value is a bare number: `16` → `16A`.
* Types with **User Types the Type Name** ticked (seeded: *Other*) use the name the user enters instead.
* Max 140 characters.

## Duplicate checks

| Result | When |
|---|---|
| 🔴 Block | Same name ignoring case/spacing (dots and commas kept, so `2.5mm` ≠ `25mm`) |
| 🔴 Block | Same Model / Part No. found as a whole segment in any item name, or in its Model field |
| 🟡 Warn | Model appears inside a longer part number (variant), or name ≥ threshold similar (default 88% same type, 93% other types) |

Warnings can be overridden with a reason, which is stored on the Item.

## Item codes

Next code = series prefix + (highest existing number + 1), zero-padded. Seeded:
COTS → `EX-NO-COTS-`, Consumables → `EX-NO-CONS-`, Sub-Assemblies → `EX-NO-SA-`.
Only groups listed in Settings appear on the page.
Requires **Stock Settings → Item Naming By = Item Code** (the page warns otherwise).

## Install (devcontainer)

```bash
cd /workspace/development/frappe-bench
bench get-app /path/to/exeliq_items     # or copy into apps/ and: bench pip install -e apps/exeliq_items
bench --site dev.localhost install-app exeliq_items
bench --site dev.localhost migrate
bench build --app exeliq_items
bench --site dev.localhost clear-cache
```

The 82 seeded Item Types are inserted once. After that they are yours: edits and deletions
are never overwritten by later migrates. A type that items already use cannot be deleted - disable it.
