"""Deterministic tools. No LLM code here: same input -> same output."""
import json
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "laptops.json"

def load_laptops():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)

CHECKS = {
    "max_price_inr":       lambda l, v: l["price_inr"] <= v,
    "min_ram_gb":          lambda l, v: l["ram_gb"] >= v,
    "min_storage_gb":      lambda l, v: l["storage_gb"] >= v,
    "min_battery_hours":   lambda l, v: l["battery_hours"] >= v,
    "max_weight_kg":       lambda l, v: l["weight_kg"] <= v,
    "min_rating":          lambda l, v: l["rating"] >= v,
    "use_case":            lambda l, v: str(v).lower() in l["use_cases"],
    "brand":               lambda l, v: l["brand"].lower() == str(v).lower(),
    "needs_dedicated_gpu": lambda l, v: l["dedicated_gpu"] is True,
}

def _passes(laptop, active):
    return all(CHECKS[k](laptop, v) for k, v in active.items())

NEAREST = {"max_price_inr": ("price_inr", min), "max_weight_kg": ("weight_kg", min),
           "min_ram_gb": ("ram_gb", max), "min_storage_gb": ("storage_gb", max),
           "min_battery_hours": ("battery_hours", max), "min_rating": ("rating", max)}

def _nearest(key, feasible):
    """Closest value of this constraint that would let some option through."""
    if key in NEAREST and feasible:
        field, fn = NEAREST[key]
        return fn(l[field] for l in feasible)
    return None

def filter_laptops(**kwargs):
    """Hard-filter the dataset. Unknown/empty args are ignored (and reported)."""
    laptops = load_laptops()
    active = {k: v for k, v in kwargs.items()
              if k in CHECKS and v not in (None, "", False)}
    ignored = [k for k in kwargs if k not in CHECKS]
    matches = [l for l in laptops if _passes(l, active)]
    result = {
        "count": len(matches),
        "applied_filters": active,
        "ignored_args": ignored,
        "matches": [{"id": l["id"], "name": l["name"], "price_inr": l["price_inr"]} for l in matches],
    }
    if not matches and active:
        # Deterministic diagnostics: what happens if we drop each constraint?
        diag = []
        for k in active:
            rest = {kk: vv for kk, vv in active.items() if kk != k}
            alone = sum(1 for l in laptops if CHECKS[k](l, active[k]))
            feasible = [l for l in laptops if _passes(l, rest)]
            diag.append({"constraint": k, "value": active[k],
                         "options_passing_this_alone": alone,
                         "matches_if_dropped": len(feasible),
                         "nearest_feasible_value": _nearest(k, feasible)})
        diag.sort(key=lambda d: -d["matches_if_dropped"])
        result["diagnostics"] = diag
    return result

DEFAULT_WEIGHTS = {"price": 1, "performance": 1, "battery": 1, "portability": 1, "rating": 1}

def _norm(v, lo, hi, invert=False):
    if hi == lo:
        return 1.0
    x = (v - lo) / (hi - lo)
    return 1 - x if invert else x

def score_laptops(ids, weights=None):
    """Score chosen laptops 0-100. Min-max normalised over the whole dataset."""
    laptops = load_laptops()
    by_id = {l["id"]: l for l in laptops}
    unknown = [i for i in (ids or []) if i not in by_id]
    chosen = [by_id[i] for i in (ids or []) if i in by_id]
    if not chosen:
        return {"error": "No valid laptop ids to score", "unknown_ids": unknown}

    w = {k: max(0.0, float((weights or {}).get(k) or 0)) for k in DEFAULT_WEIGHTS} if weights else dict(DEFAULT_WEIGHTS)
    if sum(w.values()) == 0:
        w = dict(DEFAULT_WEIGHTS)
    total = sum(w.values())
    w = {k: round(v / total, 3) for k, v in w.items()}

    perf = lambda l: 0.6 * l["cpu_score"] + 0.4 * l["gpu_score"]
    rng = lambda f: (min(f(l) for l in laptops), max(f(l) for l in laptops))
    p, pf, b, wt, r = (rng(lambda l: l["price_inr"]), rng(perf),
                       rng(lambda l: l["battery_hours"]), rng(lambda l: l["weight_kg"]),
                       rng(lambda l: l["rating"]))
    ranking = []
    for l in chosen:
        parts = {
            "price": _norm(l["price_inr"], *p, invert=True),
            "performance": _norm(perf(l), *pf),
            "battery": _norm(l["battery_hours"], *b),
            "portability": _norm(l["weight_kg"], *wt, invert=True),
            "rating": _norm(l["rating"], *r),
        }
        score = 100 * sum(w[k] * parts[k] for k in parts)
        ranking.append({"id": l["id"], "name": l["name"], "score": round(score, 1),
                        "breakdown": {k: round(100 * v, 1) for k, v in parts.items()},
                        "specs": l})
    ranking.sort(key=lambda x: (-x["score"], x["id"]))
    for i, row in enumerate(ranking, 1):
        row["rank"] = i
    return {"weights_used": w, "ranking": ranking, "unknown_ids": unknown}

def get_laptop_details(laptop_id):
    for l in load_laptops():
        if l["id"] == laptop_id:
            return l
    return {"error": f"Unknown id {laptop_id}"}

TOOLS = {"filter_laptops": filter_laptops, "score_laptops": score_laptops,
         "get_laptop_details": get_laptop_details}

def dispatch(name, args):
    if name not in TOOLS:
        return {"error": f"Unknown tool {name}"}
    try:
        return TOOLS[name](**(args or {}))
    except TypeError as e:
        return {"error": f"Bad arguments: {e}"}

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "filter_laptops",
        "description": "Hard-filter laptops by constraints. Omit any constraint the user did not state. Returns matching ids; if none match, returns diagnostics.",
        "parameters": {"type": "object", "properties": {
            "max_price_inr": {"type": "number"},
            "min_ram_gb": {"type": "number"},
            "min_storage_gb": {"type": "number"},
            "min_battery_hours": {"type": "number"},
            "max_weight_kg": {"type": "number"},
            "min_rating": {"type": "number"},
            "use_case": {"type": "string", "enum": ["student", "programming", "gaming", "creative", "business"]},
            "brand": {"type": "string"},
            "needs_dedicated_gpu": {"type": "boolean"}}}}},
    {"type": "function", "function": {
        "name": "score_laptops",
        "description": "Rank laptops (ids from filter_laptops) 0-100. Weights express user priorities; omit those the user did not mention.",
        "parameters": {"type": "object", "properties": {
            "ids": {"type": "array", "items": {"type": "string"}},
            "weights": {"type": "object", "properties": {
                "price": {"type": "number"}, "performance": {"type": "number"},
                "battery": {"type": "number"}, "portability": {"type": "number"},
                "rating": {"type": "number"}}}},
            "required": ["ids"]}}},
    {"type": "function", "function": {
        "name": "get_laptop_details",
        "description": "Get full specs for one laptop id.",
        "parameters": {"type": "object", "properties": {"laptop_id": {"type": "string"}},
                       "required": ["laptop_id"]}}},
]


def _make_nullable(schema):
    if isinstance(schema, dict):
        if "properties" in schema:
            for p in schema["properties"].values():
                t = p.get("type")
                if isinstance(t, str) and t != "object" and t != "array":
                    p["type"] = [t, "null"]
                    if "enum" in p:
                        p["enum"] = p["enum"] + [None]
                elif t == "array":
                    p["type"] = ["array", "null"]
                elif t == "object":
                    p["type"] = ["object", "null"]
                _make_nullable(p)
    return schema

for _t in TOOL_SCHEMAS:
    _fn = _t["function"]
    if _fn["name"] in ("filter_laptops", "score_laptops"):
        _make_nullable(_fn["parameters"])