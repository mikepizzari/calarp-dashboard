"""
CalARP Lead Scoring Engine
--------------------------
Reads a CERS CalARP inspection export (Excel or CSV),
scores each site on urgency (1-10), and writes:
  - output/leads.json       (full scored lead list)
  - output/leads.csv        (CRM-import ready)
  - output/dashboard.html   (self-contained dashboard)
  - output/last_updated.txt (ISO timestamp)

Usage:
    python score.py --input data/CERS_Data_CalARP_Sites.xlsx
    python score.py --input data/CERS_Data_CalARP_Sites.csv
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from diff import compute_diff, save_snapshot

TODAY = datetime.now()
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ── SEISMIC ZONE MAP (CUPA keyword → zone) ───────────────────────────────────
HIGH_SEISMIC = [
    "alameda","contra costa","san francisco","oakland","santa clara",
    "san jose","hayward","fremont","richmond","berkeley","long beach",
    "los angeles city","los angeles county","ventura","santa cruz","monterey",
]
MED_SEISMIC = [
    "san diego","orange county","riverside","san bernardino","sacramento",
    "san joaquin","kern","imperial",
]

def seismic_zone(cupa: str) -> str:
    c = cupa.lower()
    if any(k in c for k in HIGH_SEISMIC):
        return "High"
    if any(k in c for k in MED_SEISMIC):
        return "Medium"
    return "Low"

# ── NOTE PATTERNS ─────────────────────────────────────────────────────────────
AMMONIA_RE   = re.compile(r"ammonia|NH3|anhydrous", re.I)
REFINERY_RE  = re.compile(r"refin|petroleum|crude|324110", re.I)
FOOD_RE      = re.compile(r"food|cold.?stor|refriger|dairy|cheese|winery|wine|"
                           r"fruit|vegetable|meat|poultry|packing|cannery|frozen|"
                           r"ice.?cream|beverage|tomato|almond|walnut|raisin|warehouse", re.I)
IIAR9_RE     = re.compile(r"IIAR.?9|mechanical.?integrity|\bMI\b|RAGAGEP", re.I)
P3_RE        = re.compile(r"program.?3|Program 3|PSM|process.?safety", re.I)
P2_RE        = re.compile(r"program.?2|Program 2", re.I)

# ── SCORING ───────────────────────────────────────────────────────────────────
def score_site(row: dict) -> tuple[int, list[str]]:
    pts = 2
    pain = []

    if row["iiar9_gap"]:
        pts += 3
        pain.append("IIAR 9 MI Program: No evidence of update (Jan 2026 deadline passed)")

    if row["revalid_overdue"]:
        pts += 3
        pain.append(f"RMP Revalidation OVERDUE: Last eval {row['latest_eval']} "
                    f"({row['years_since']:.1f} yrs ago)")
    elif row["revalid_soon"]:
        pts += 1
        pain.append(f"RMP Revalidation DUE 2027: Plan now ({row['latest_eval']})")

    if row["pre_epa2024"]:
        pts += 2
        pain.append("EPA 2024 RMP Rule: Third-party audit + STAA requirements unaddressed")

    if row["total_violations"] > 0:
        pts += 1
        pain.append(f"Prior violation history: {row['total_violations']} violations on record")

    if row["seismic"] == "High":
        pts += 1
        pain.append("High seismic zone: IIAR 9 Section 6.6 bracing documentation required")
    elif row["seismic"] == "Medium":
        pain.append("Medium seismic zone: Verify IIAR 9 seismic bracing compliance")

    if row["is_p3"]:
        pts += 1

    return min(pts, 10), pain

def pitch(row: dict) -> str:
    if row["revalid_overdue"] and row["iiar9_gap"]:
        return "IIAR 9 MI Gap Analysis + RMP Revalidation Package"
    if row["iiar9_gap"]:
        return "IIAR 9 MI Program Development"
    if row["revalid_overdue"]:
        return "RMP 5-Year Revalidation"
    return "EPA 2024 RMP Rule Compliance Review"

# ── MAIN PIPELINE ─────────────────────────────────────────────────────────────
def run(input_path: str):
    print(f"[score.py] Reading: {input_path}")
    p = Path(input_path)
    if p.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(p)
    else:
        df = pd.read_csv(p)

    # Normalise column names (strip whitespace)
    df.columns = [c.strip() for c in df.columns]

    required = {"SiteID", "SiteName", "EvalDate", "ViolationsFound",
                "EvalDivision", "EvalNotes"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"[score.py] ERROR – missing columns: {missing}\n"
                 f"Found: {list(df.columns)}")

    df["EvalDate"]  = pd.to_datetime(df["EvalDate"], errors="coerce")
    df["EvalNotes"] = df["EvalNotes"].fillna("").astype(str)

    # ── Per-site aggregation ──────────────────────────────────────────────────
    agg = df.groupby("SiteID").agg(
        SiteName      = ("SiteName",       "first"),
        CUPA          = ("EvalDivision",    "first"),
        TotalEvals    = ("EvalDate",        "count"),
        LatestEval    = ("EvalDate",        "max"),
        TotalViolations = ("ViolationsFound", lambda x: (x == "Yes").sum()),
        AllNotes      = ("EvalNotes",       lambda x: " ".join(x)),
    ).reset_index()

    agg["LatestEval"] = pd.to_datetime(agg["LatestEval"])
    agg["DaysSince"]  = (TODAY - agg["LatestEval"]).dt.days
    agg["YearsSince"] = agg["DaysSince"] / 365.25

    # Count how many rows per site have non-empty notes
    notes_count = df[df["EvalNotes"].str.strip().str.len() > 10].groupby("SiteID").size().rename("NotesCount")
    agg = agg.join(notes_count, on="SiteID")
    agg["NotesCount"] = agg["NotesCount"].fillna(0).astype(int)

    def flag(notes, rx): return bool(rx.search(notes))

    def iiar9_gap_flag(notes: str, notes_count: int, latest_year: int) -> bool:
        """
        Only flag as IIAR 9 gap if:
        - Notes are rich enough to expect a mention (at least 2 substantive note rows), OR
        - The site has recent evals (post-2020) where IIAR 9 should appear if compliant
        If notes are sparse/blank, mark as UNKNOWN (False) — don't penalize for missing data.
        """
        if flag(notes, IIAR9_RE):
            return False   # Explicitly compliant — no gap
        if notes_count >= 2 and latest_year >= 2020:
            return True    # Enough notes, recent enough — absence is meaningful
        if notes_count >= 4:
            return True    # Lots of notes across history — absence is meaningful
        return False       # Sparse notes — can't determine, don't penalize

    rows = []
    for _, r in agg.iterrows():
        notes = r["AllNotes"]
        latest_year = r["LatestEval"].year if pd.notna(r["LatestEval"]) else 0
        latest_str  = r["LatestEval"].strftime("%Y-%m-%d") if pd.notna(r["LatestEval"]) else "Unknown"
        notes_ct    = int(r["NotesCount"])

        rec = {
            "site_id":          int(r["SiteID"]),
            "facility_name":    str(r["SiteName"]).strip(),
            "cupa":             str(r["CUPA"]).strip(),
            "physical_address": "VERIFY via CERS SiteID or EPA ECHO",
            "total_evals":      int(r["TotalEvals"]),
            "total_violations": int(r["TotalViolations"]),
            "latest_eval":      latest_str,
            "years_since":      round(float(r["YearsSince"]), 1),
            "seismic":          seismic_zone(str(r["CUPA"])),
            "has_ammonia":      flag(notes, AMMONIA_RE),
            "is_food":          flag(notes, FOOD_RE),
            "is_refinery":      flag(notes, REFINERY_RE),
            "is_p3":            flag(notes, P3_RE),
            "is_p2":            flag(notes, P2_RE),
            "iiar9_gap":        iiar9_gap_flag(notes, notes_ct, latest_year),
            "revalid_overdue":  latest_year > 0 and latest_year <= 2021,
            "revalid_soon":     latest_year == 2022,
            "pre_epa2024":      pd.notna(r["LatestEval"]) and r["LatestEval"] < pd.Timestamp("2024-05-01"),
        }
        score, pain = score_site(rec)
        rec["urgency_score"]     = score
        rec["pain_points"]       = pain
        rec["recommended_pitch"] = pitch(rec)
        rows.append(rec)

    rows.sort(key=lambda x: -x["urgency_score"])

    # ── Stats for dashboard ───────────────────────────────────────────────────
    total = len(rows)
    score_dist   = dict(sorted(Counter(r["urgency_score"] for r in rows).items()))
    hot          = sum(1 for r in rows if r["urgency_score"] >= 8)
    iiar9_gap    = sum(1 for r in rows if r["iiar9_gap"])
    overdue      = sum(1 for r in rows if r["revalid_overdue"])
    soon         = sum(1 for r in rows if r["revalid_soon"])
    violations   = sum(1 for r in rows if r["total_violations"] > 0)
    high_seismic = sum(1 for r in rows if r["seismic"] == "High")
    med_seismic  = sum(1 for r in rows if r["seismic"] == "Medium")
    low_seismic  = sum(1 for r in rows if r["seismic"] == "Low")
    pre2024      = sum(1 for r in rows if r["pre_epa2024"])
    p3_count     = sum(1 for r in rows if r["is_p3"])

    cupa_counts = defaultdict(list)
    for r in rows:
        cupa_counts[r["cupa"]].append(r["urgency_score"])
    cupa_stats = sorted(
        [{"name": k, "count": len(v), "avg": round(sum(v)/len(v), 1)}
         for k, v in cupa_counts.items()],
        key=lambda x: -x["count"]
    )[:14]

    stats = {
        "generated":      TODAY.strftime("%Y-%m-%d"),
        "total_sites":    total,
        "hot_leads":      hot,
        "total_evals":    int(df.shape[0]),
        "iiar9_gap":      iiar9_gap,
        "revalid_overdue": overdue,
        "revalid_soon":   soon,
        "violation_sites": violations,
        "high_seismic":   high_seismic,
        "med_seismic":    med_seismic,
        "low_seismic":    low_seismic,
        "pre_epa2024":    pre2024,
        "p3_count":       p3_count,
        "score_dist":     score_dist,
        "cupa_stats":     cupa_stats,
    }

    # ── Write JSON ────────────────────────────────────────────────────────────
    out_json = {"metadata": stats, "leads": rows}
    with open(OUTPUT_DIR / "leads.json", "w") as f:
        json.dump(out_json, f, indent=2, default=str)
    print(f"[score.py] Written: output/leads.json ({total} sites)")

    # ── Write CSV ─────────────────────────────────────────────────────────────
    csv_rows = []
    for r in rows:
        row = {k: v for k, v in r.items() if k != "pain_points"}
        row["pain_points"] = " | ".join(r["pain_points"])
        csv_rows.append(row)
    pd.DataFrame(csv_rows).to_csv(OUTPUT_DIR / "leads.csv", index=False)
    print(f"[score.py] Written: output/leads.csv")

    # ── Write timestamp ───────────────────────────────────────────────────────
    with open(OUTPUT_DIR / "last_updated.txt", "w") as f:
        f.write(TODAY.isoformat())

    # ── Compute week-over-week changes ────────────────────────────────────────
    from diff import compute_diff, save_snapshot
    changes = compute_diff(rows)

    # ── Generate dashboard HTML ───────────────────────────────────────────────
    from build_html import build_html
    build_html(stats, rows, changes)
    print(f"[score.py] Written: output/dashboard.html")

    # ── Save snapshot for next week's diff ───────────────────────────────────
    save_snapshot(out_json)

    print(f"[score.py] Done. {total} sites scored, {hot} hot leads (8-10).")
    if not changes.get("baseline"):
        s = changes["summary"]
        print(f"[score.py] Changes: up={s['moved_up_count']} down={s['moved_down_count']} new={s['new_count']} dropped={s['dropped_count']}")
    return stats, rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CalARP Lead Scorer")
    parser.add_argument("--input", required=True,
                        help="Path to CERS export (.xlsx or .csv)")
    args = parser.parse_args()
    run(args.input)
