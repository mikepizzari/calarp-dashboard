"""
diff.py
-------
Compares the current scoring run against the previous snapshot
stored in output/leads_previous.json.

Primary key: lead_key (epaid string for national; "cers-{site_id}" for unmatched CA).
Tier comparison: lower tier number = better (T1 best, T5 lowest).
  moved_up:   prev_tier > curr_tier (tier improved, number decreased)
  moved_down: prev_tier < curr_tier (tier worsened, number increased)
  new_sites:  lead_key not in previous run
  dropped:    lead_key in previous run but missing this run
"""

import json
from pathlib import Path

OUTPUT_DIR = Path("output")


def compute_diff(current_leads: list) -> dict:
    """Compare current_leads against output/leads_previous.json."""
    prev_path = OUTPUT_DIR / "leads_previous.json"

    current_map = {str(r["lead_key"]): r for r in current_leads}

    if not prev_path.exists():
        print("[diff.py] No previous snapshot found — this is the baseline run.")
        changes = {
            "baseline": True,
            "run_date": None,
            "moved_up":   [],
            "moved_down": [],
            "new_sites":  [],
            "dropped":    [],
        }
        _save(changes)
        return changes

    with open(prev_path) as f:
        prev_data = json.load(f)

    # Support both new format (lead_key) and old format (site_id) for migration
    def _key(r):
        return str(r.get("lead_key") or r.get("site_id") or "")
    prev_map  = {_key(r): r for r in prev_data.get("leads", []) if _key(r)}
    prev_date = prev_data.get("metadata", {}).get("generated", "unknown")

    moved_up, moved_down, new_sites, dropped = [], [], [], []

    for key, rec in current_map.items():
        if key not in prev_map:
            new_sites.append({
                "lead_key":      rec["lead_key"],
                "facility_name": rec["facility_name"],
                "state":         rec.get("state", ""),
                "territory":     rec.get("territory", ""),
                "current_tier":  rec["tier"],
                "tier_label":    rec["tier_label"],
                "prev_tier":     None,
                "delta":         None,
            })
        else:
            # Old snapshots may not have "tier"; treat as baseline if missing
            prev_tier = prev_map[key].get("tier")
            curr_tier = rec["tier"]
            if prev_tier is None:
                continue  # skip comparison if old snapshot lacks tier
            # delta > 0 = improvement (tier number decreased)
            delta = prev_tier - curr_tier
            if delta > 0:
                moved_up.append({
                    "lead_key":      rec["lead_key"],
                    "facility_name": rec["facility_name"],
                    "state":         rec.get("state", ""),
                    "territory":     rec.get("territory", ""),
                    "current_tier":  curr_tier,
                    "tier_label":    rec["tier_label"],
                    "prev_tier":     prev_tier,
                    "delta":         delta,
                    "reason":        _explain_delta(rec, prev_map[key]),
                })
            elif delta < 0:
                moved_down.append({
                    "lead_key":      rec["lead_key"],
                    "facility_name": rec["facility_name"],
                    "state":         rec.get("state", ""),
                    "territory":     rec.get("territory", ""),
                    "current_tier":  curr_tier,
                    "tier_label":    rec["tier_label"],
                    "prev_tier":     prev_tier,
                    "delta":         delta,
                    "reason":        _explain_delta(rec, prev_map[key]),
                })

    for key, rec in prev_map.items():
        if key not in current_map:
            dropped.append({
                "lead_key":      rec.get("lead_key") or str(rec.get("site_id", "")),
                "facility_name": rec["facility_name"],
                "state":         rec.get("state", ""),
                "territory":     rec.get("territory", ""),
                "prev_tier":     rec.get("tier"),
            })

    moved_up.sort(key=lambda x: -x["delta"])
    moved_down.sort(key=lambda x: x["delta"])
    new_sites.sort(key=lambda x: x["current_tier"])

    changes = {
        "baseline":   False,
        "prev_date":  prev_date,
        "moved_up":   moved_up,
        "moved_down": moved_down,
        "new_sites":  new_sites,
        "dropped":    dropped,
        "summary": {
            "moved_up_count":   len(moved_up),
            "moved_down_count": len(moved_down),
            "new_count":        len(new_sites),
            "dropped_count":    len(dropped),
            "unchanged_count":  len(current_map) - len(moved_up) - len(moved_down) - len(new_sites),
        }
    }

    _save(changes)
    print(f"[diff.py] vs {prev_date}: "
          f"^{len(moved_up)} up, v{len(moved_down)} down, "
          f"+{len(new_sites)} new, -{len(dropped)} dropped")
    return changes


def save_snapshot(current_data: dict):
    """Save current leads.json as leads_previous.json for next week's diff."""
    prev_path = OUTPUT_DIR / "leads_previous.json"
    with open(prev_path, "w") as f:
        json.dump(current_data, f, indent=2, default=str)
    print("[diff.py] Snapshot saved -> output/leads_previous.json")


def _save(changes: dict):
    with open(OUTPUT_DIR / "changes.json", "w") as f:
        json.dump(changes, f, indent=2, default=str)


def _explain_delta(curr: dict, prev: dict) -> str:
    reasons = []
    curr_rv = curr.get("revalid_status", "")
    prev_rv = prev.get("revalid_status", "")
    if curr_rv == "overdue" and prev_rv != "overdue":
        reasons.append("RMP revalidation now overdue")
    elif curr_rv == "soon" and prev_rv not in ("overdue", "soon"):
        reasons.append("RMP revalidation due within 18 months")
    curr_t = curr.get("tier")
    prev_t = prev.get("tier")
    if curr_t and prev_t and curr_t != prev_t:
        reasons.append(f"Tier changed T{prev_t} -> T{curr_t}")
    if not reasons:
        reasons.append("Data refresh")
    return "; ".join(reasons)
