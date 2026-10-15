"""Pure naming + duplicate-detection logic (no frappe imports, so it is unit-testable).

Name format:  Type - Make/Model/P1/P2/P3
  * Make is left out when the brand is GENERIC / blank.
  * Empty parts are skipped.
  * Spacing is normalised: single spaces, no spaces around "/".
"""

import re
from collections import Counter
from difflib import SequenceMatcher

GENERIC_BRANDS = {"", "generic", "gen"}
TYPE_SPLIT_RE = re.compile(r"\s*-\s+|\s+-\s*")
NUMERIC_RE = re.compile(r"^\d+(\.\d+)?$")
MAX_NAME_LEN = 140


# ---------------------------------------------------------------- cleaning

def clean_part(value):
    """Tidy one name segment: collapse whitespace, no spaces around '/', strip stray separators."""
    if value is None:
        return ""
    s = str(value).replace(" ", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*/\s*", "/", s)
    s = s.strip(" /-")
    return s


def apply_suffix(value, suffix):
    """Append a unit suffix only when the value is a bare number: 16 + A -> 16A, '16A' stays."""
    value = clean_part(value)
    suffix = (suffix or "").strip()
    if value and suffix and NUMERIC_RE.match(value):
        return value + suffix
    return value


def is_generic(brand):
    return (brand or "").strip().lower() in GENERIC_BRANDS


def build_name(type_name, make=None, model=None, params=None):
    """params: list of (value, suffix) tuples in template order."""
    type_name = clean_part(type_name)
    parts = []
    if not is_generic(make):
        parts.append(clean_part(make))
    if model:
        parts.append(clean_part(model))
    for value, suffix in params or []:
        parts.append(apply_suffix(value, suffix))
    parts = [p for p in parts if p]
    if not parts:
        return type_name
    return "{0} - {1}".format(type_name, "/".join(parts))


# ---------------------------------------------------------------- comparison keys

def normalize_name(name):
    """Comparison key: case, spacing and separator spacing ignored. Dots/commas kept (2.5mm != 25mm)."""
    s = (name or "").lower().replace(" ", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*([-/])\s*", r"\1", s)
    return s


def alnum(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def split_type(name):
    """'MCB- SCH/A9N/16A' -> ('MCB', 'SCH/A9N/16A'). Names with no ' - ' return (name, '')."""
    name = (name or "").strip()
    bits = TYPE_SPLIT_RE.split(name, maxsplit=1)
    if len(bits) == 2:
        return bits[0].strip(), bits[1].strip()
    return name, ""


def segments(name):
    _, rest = split_type(name)
    return [s.strip() for s in rest.split("/") if s.strip()]


# ---------------------------------------------------------------- conflicts

def find_conflicts(candidate_name, existing, type_name=None, model=None, threshold=0.88, max_similar=5):
    """
    existing: iterable of dicts with keys item_code, item_name, disabled, and optionally
              exl_model, exl_item_type.
    Returns (blocks, warnings) - lists of dicts {item_code, item_name, disabled, reason, score}.
    """
    blocks, warns = [], []
    cand_norm = normalize_name(candidate_name)
    type_key = alnum(type_name or split_type(candidate_name)[0])
    model_key = alnum(model)
    seen = set()

    def hit(row, reason, score=1.0):
        return {
            "item_code": row.get("item_code"),
            "item_name": row.get("item_name"),
            "disabled": int(row.get("disabled") or 0),
            "reason": reason,
            "score": round(score, 3),
        }

    rows = list(existing)

    # 1. Same name (ignoring case / spacing / separator spacing)
    for row in rows:
        if normalize_name(row.get("item_name")) == cand_norm:
            blocks.append(hit(row, "Same name already exists"))
            seen.add(row.get("item_code"))

    # 2. Same model / part number under any name
    if len(model_key) >= 3:
        for row in rows:
            code = row.get("item_code")
            if code in seen:
                continue
            item_name = row.get("item_name") or ""
            # model as a whole segment anywhere in the name, split on '/', spaces and ' - '
            seg_keys = {alnum(s) for s in segments(item_name)}
            seg_keys |= {alnum(s) for s in re.split(r"[/\s]+", item_name) if s}
            seg_keys |= {alnum(s) for s in re.split(r"/|\s+-\s*|\s*-\s+", item_name) if s}
            if alnum(row.get("exl_model")) == model_key or model_key in seg_keys:
                blocks.append(hit(row, "Same model / part no. already exists"))
                seen.add(code)
            elif len(model_key) >= 5 and model_key in alnum(item_name):
                warns.append(hit(row, "Model appears inside this item's name (variant?)", 0.95))
                seen.add(code)

    # 3. Similar names (same type, or very close overall)
    similar = []
    for row in rows:
        code = row.get("item_code")
        if code in seen:
            continue
        other = normalize_name(row.get("item_name"))
        if not other:
            continue
        same_type = type_key and (
            alnum(split_type(row.get("item_name"))[0]) == type_key
            or alnum(row.get("exl_item_type")) == type_key
        )
        bar = threshold if same_type else max(threshold, 0.93)
        sm = SequenceMatcher(None, cand_norm, other)
        if sm.real_quick_ratio() < bar or sm.quick_ratio() < bar:
            continue
        score = sm.ratio()
        if score >= bar:
            similar.append(hit(row, "Similar name" + (" (same type)" if same_type else ""), score))
    similar.sort(key=lambda r: r["score"], reverse=True)
    warns.extend(similar[:max_similar])
    return blocks, warns


# ---------------------------------------------------------------- suggestions

def legacy_segment_counts(existing_names, type_name):
    """Every '/' segment used in older items of this type, with frequency. Used for autocomplete."""
    key = alnum(type_name)
    counter = Counter()
    for name in existing_names:
        t, rest = split_type(name)
        if alnum(t) != key or not rest:
            continue
        for seg in rest.split("/"):
            seg = clean_part(seg)
            if seg:
                counter[seg] += 1
    return counter


def filter_suggestions(values, txt, limit=15):
    """values: iterable of (value, weight). Case-insensitive contains match, prefix matches first."""
    txt = (txt or "").strip().lower()
    merged = {}
    for v, w in values:
        v = clean_part(v)
        if not v:
            continue
        k = v.lower()
        if k in merged:
            merged[k] = (merged[k][0], merged[k][1] + w)
        else:
            merged[k] = (v, w)
    out = []
    for k, (v, w) in merged.items():
        if txt and txt not in k:
            continue
        out.append((0 if k.startswith(txt) else 1, -w, k, v))
    out.sort()
    return [o[3] for o in out[:limit]]


# ---------------------------------------------------------------- item codes

def next_code(prefix, digits, existing_codes):
    """EX-NO-COTS- + highest existing number + 1, zero-padded."""
    prefix = prefix or ""
    pat = re.compile(r"^" + re.escape(prefix) + r"(\d+)$")
    highest = 0
    for code in existing_codes:
        m = pat.match(code if isinstance(code, str) else "")
        if m:
            highest = max(highest, int(m.group(1)))
    return "{0}{1}".format(prefix, str(highest + 1).zfill(int(digits or 4)))
