"""
diff.py
-------
Compares the current scoring run against the previous snapshot
stored in output/leads_previous.json.

Produces a change report with three categories:
  - MOVED_UP:   urgency score increased since last run
  - MOVED_DOWN: urgency score decreased since last run
  - NEW:        site not present in previous run
  - DROPPED:    site present last run but missing this run

The report is saved to output/changes.json and also returned
as a dict for use by build_html.py.
"""

import json
from pathlib import Path

OUTPUT_DIR = Path("output")


def compute_diff(current_leads: list) -> dict:
    """
    Compare current_leads against output/leads_previous.json.
    Returns a dict of changes keyed by site_id.
    """
    prev_path = OUTPUT_DIR / "leads_previous.json"

    # Build lookup for current run  {site_id -> lead_record}
    current_map = {str(r["site_id"]): r for r in current_leads}

    # If no previous snapshot exists, everything is "new" but we
    # treat it as a baseline run — no change indicators shown.
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

    prev_map = {str(r["site_id"]): r for r in prev_data.get("leads", [])}
    prev_date = prev_data.get("metadata", {}).get("generated", "unknown")

    moved_up, moved_down, new_sites, dropped = [], [], [], []

    # Check every current site against previous
    for sid, rec in current_map.items():
        if sid not in prev_map:
            new_sites.append({
                "site_id":       rec["site_id"],
                "facility_name": rec["facility_name"],
                "cupa":          rec["cupa"],
                "current_score": rec["urgency_score"],
                "prev_score":    None,
                "delta":         None,
                "pitch":         rec["recommended_pitch"],
            })
        else:
            prev_score = prev_map[sid]["urgency_score"]
            curr_score = rec["urgency_score"]
            delta = curr_score - prev_score
            if delta > 0:
                moved_up.append({
                    "site_id":       rec["site_id"],
                    "facility_name": rec["facility_name"],
                    "cupa":          rec["cupa"],
                    "current_score": curr_score,
                    "prev_score":    prev_score,
                    "delta":         delta,
                    "pitch":         rec["recommended_pitch"],
                    "reason":        _explain_delta(rec, prev_map[sid]),
                })
            elif delta < 0:
                moved_down.append({
                    "site_id":       rec["site_id"],
                    "facility_name": rec["facility_name"],
                    "cupa":          rec["cupa"],
                    "current_score": curr_score,
                    "prev_score":    prev_score,
                    "delta":         delta,
                    "pitch":         rec["recommended_pitch"],
                    "reason":        _explain_delta(rec, prev_map[sid]),
                })

    # Check for dropped sites
    for sid, rec in prev_map.items():
        if sid not in current_map:
            dropped.append({
                "site_id":       rec["site_id"],
                "facility_name": rec["facility_name"],
                "cupa":          rec["cupa"],
                "prev_score":    rec["urgency_score"],
            })

    # Sort by magnitude of change
    moved_up.sort(key=lambda x: -x["delta"])
    moved_down.sort(key=lambda x: x["delta"])
    new_sites.sort(key=lambda x: -x["current_score"])

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
    """
    Save the current leads.json as leads_previous.json
    so next week's run can diff against it.
    Called at the END of a successful score.py run.
    """
    prev_path = OUTPUT_DIR / "leads_previous.json"
    with open(prev_path, "w") as f:
        json.dump(current_data, f, indent=2, default=str)
    print("[diff.py] Snapshot saved -> output/leads_previous.json")


def _save(changes: dict):
    with open(OUTPUT_DIR / "changes.json", "w") as f:
        json.dump(changes, f, indent=2, default=str)


def _explain_delta(curr: dict, prev: dict) -> str:
    """Generate a human-readable reason for the score change."""
    reasons = []
    # Revalidation tipped over
    if curr.get("revalid_overdue") and not prev.get("revalid_overdue"):
        reasons.append("Revalidation now overdue")
    if curr.get("revalid_soon") and not prev.get("revalid_soon"):
        reasons.append("Revalidation due 2027 — entered pipeline window")
    # New violation detected
    if curr.get("total_violations", 0) > prev.get("total_violations", 0):
        reasons.append(f"New violation recorded "
                       f"({prev.get('total_violations',0)} → {curr.get('total_violations',0)})")
    # Violation cleared
    if curr.get("total_violations", 0) < prev.get("total_violations", 0):
        reasons.append(f"Violation count reduced "
                       f"({prev.get('total_violations',0)} → {curr.get('total_violations',0)})")
    # IIAR 9 gap resolved
    if not curr.get("iiar9_gap") and prev.get("iiar9_gap"):
        reasons.append("IIAR 9 compliance language now detected in notes")
    # IIAR 9 gap appeared
    if curr.get("iiar9_gap") and not prev.get("iiar9_gap"):
        reasons.append("IIAR 9 compliance language no longer found")
    # EPA 2024 threshold cleared (new eval recorded post May 2024)
    if not curr.get("pre_epa2024") and prev.get("pre_epa2024"):
        reasons.append("New eval post May 2024 — EPA 2024 RMP Rule threshold cleared")
    # EPA 2024 threshold appeared (latest eval regressed in data export)
    if curr.get("pre_epa2024") and not prev.get("pre_epa2024"):
        reasons.append("EPA 2024 compliance window reopened — latest eval pre-May 2024")
    # Score changed but reason unclear (data refresh)
    if not reasons:
        delta = curr.get("urgency_score", 0) - prev.get("urgency_score", 0)
        reasons.append(f"Score {'increased' if delta > 0 else 'decreased'} on data refresh")
    return "; ".join(reasons)
