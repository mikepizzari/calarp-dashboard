"""
National NH3 Lead Scoring Engine
---------------------------------
Primary data: data/national_rmp.csv (non-CA) + CERS CalARP xlsx (CA).
Scores each facility on a 5-tier model driven by parent company Locations.

Writes:
  output/leads.json       full scored lead list + metadata
  output/leads.csv        CRM-importable flat version
  output/dashboard.html   self-contained interactive dashboard
  output/last_updated.txt ISO timestamp

Usage:
    python score.py --national data/national_rmp.csv --cers "data/CERS Data_CalARP Sites.xlsx"
    python score.py --national data/national_rmp.csv          # national only
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from diff import compute_diff, save_snapshot

TODAY      = datetime.now()
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
DATA_DIR   = Path("data")

TIER_LABELS = {1: "Mega", 2: "Major", 3: "Mid-Market", 4: "Standard", 5: "Single"}

# ── TIER SCORING ──────────────────────────────────────────────────────────────
def score_tier(locations: int, accidents: int) -> int:
    """Returns tier 1–5 (1=Mega/best, 5=Single/lowest).

    Base tier from Locations (parent company facility count).
    Accident history upgrades tier by 1 (1 accident) or 2 (2+ accidents).
    """
    if   locations > 200: base = 1
    elif locations > 50:  base = 2
    elif locations > 10:  base = 3
    elif locations > 1:   base = 4
    else:                 base = 5
    upgrade = 2 if accidents >= 2 else (1 if accidents == 1 else 0)
    return max(1, base - upgrade)


def revalid_status(receipt_date_str: str) -> str:
    """Compute revalidation status from LatestReceiptDate string.

    Returns "overdue" / "soon" / "ok" / "unknown".
    5-year RMP cycle: overdue if due < today, soon if due < today + 18 months.
    """
    s = str(receipt_date_str or "").strip()
    if not s:
        return "unknown"
    try:
        rd       = pd.Timestamp(s)
        today_ts = pd.Timestamp(TODAY)
        due      = rd + pd.DateOffset(years=5)
        if due < today_ts:
            return "overdue"
        if due < today_ts + pd.DateOffset(months=18):
            return "soon"
        return "ok"
    except Exception:
        return "unknown"


# ── CERS NOTE PATTERNS ────────────────────────────────────────────────────────
IIAR9_RE = re.compile(r"IIAR.?9|mechanical.?integrity|\bMI\b|RAGAGEP", re.I)
P3_RE    = re.compile(r"program.?3|Program 3|PSM|process.?safety", re.I)

_FILLER = re.compile(
    r"\b(inc|llc|corp|co|company|the|and|ltd|industries|services|group|"
    r"holdings|plant|facility|operations|warehouse|foods|food|farms|farm|"
    r"distribution|mfg|manufacturing|processing|pack|packing|cold|storage)\b"
)

def _norm_name(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[,.\-'\"&/\\()]", " ", s)
    s = _FILLER.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def iiar9_gap_flag(notes: str, notes_count: int, latest_year: int) -> bool:
    """True if IIAR 9 MI language is absent from notes that are rich enough to expect it."""
    if IIAR9_RE.search(notes):
        return False
    if notes_count >= 2 and latest_year >= 2020:
        return True
    if notes_count >= 4:
        return True
    return False


def norm_epaid(v) -> str | None:
    """Convert float EPAID to int string: 100000001650.0 -> '100000001650'"""
    if v is None:
        return None
    try:
        import math
        if isinstance(v, float) and math.isnan(v):
            return None
        return str(int(float(v)))
    except (ValueError, TypeError):
        return None


# ── CERS AGGREGATION ──────────────────────────────────────────────────────────
def aggregate_cers(cers_path: str) -> list[dict]:
    """Load and aggregate CERS CalARP export -> one record per SiteID."""
    p = Path(cers_path)
    df = pd.read_excel(p) if p.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(p)
    df.columns = [c.strip() for c in df.columns]

    required = {"SiteID", "SiteName", "EvalDate", "ViolationsFound", "EvalDivision", "EvalNotes"}
    missing = required - set(df.columns)
    if missing:
        sys.exit(f"[score.py] ERROR – missing CERS columns: {missing}")

    df["EvalDate"]  = pd.to_datetime(df["EvalDate"], errors="coerce")
    df["EvalNotes"] = df["EvalNotes"].fillna("").astype(str)

    agg = df.groupby("SiteID").agg(
        SiteName        = ("SiteName",        "first"),
        CUPA            = ("EvalDivision",     "first"),
        TotalEvals      = ("EvalDate",         "count"),
        LatestEval      = ("EvalDate",         "max"),
        TotalViolations = ("ViolationsFound",  lambda x: (x == "Yes").sum()),
        AllNotes        = ("EvalNotes",        lambda x: " ".join(x)),
    ).reset_index()

    agg["LatestEval"] = pd.to_datetime(agg["LatestEval"])
    notes_ct_map = (df[df["EvalNotes"].str.strip().str.len() > 10]
                    .groupby("SiteID").size().rename("NotesCount"))
    agg = agg.join(notes_ct_map, on="SiteID")
    agg["NotesCount"] = agg["NotesCount"].fillna(0).astype(int)

    sites = []
    for _, r in agg.iterrows():
        notes      = r["AllNotes"]
        latest_str = r["LatestEval"].strftime("%Y-%m-%d") if pd.notna(r["LatestEval"]) else ""
        latest_yr  = r["LatestEval"].year if pd.notna(r["LatestEval"]) else 0
        notes_ct   = int(r["NotesCount"])
        is_p3      = bool(P3_RE.search(notes))
        gap        = iiar9_gap_flag(notes, notes_ct, latest_yr)
        pre_epa    = is_p3 and pd.notna(r["LatestEval"]) and r["LatestEval"] < pd.Timestamp("2024-05-01")

        # Revalid from CERS eval date (fallback; may be overridden by DLP match)
        cers_rv = revalid_status(latest_str)

        cers_flags = []
        if gap:                                      cers_flags.append("IIAR9")
        if int(r["TotalViolations"]) > 0:            cers_flags.append(f"Violations:{int(r['TotalViolations'])}")
        if pre_epa:                                  cers_flags.append("EPA2024")
        if cers_rv == "overdue":                     cers_flags.append("Revalid:OVERDUE")
        elif cers_rv == "soon":                      cers_flags.append("Revalid:SOON")

        sites.append({
            "site_id":            int(r["SiteID"]),
            "facility_name":      str(r["SiteName"]).strip(),
            "cupa":               str(r["CUPA"]).strip(),
            "state":              "CA",
            "is_ca":              True,
            "latest_eval":        latest_str,
            "total_evals":        int(r["TotalEvals"]),
            "total_violations":   int(r["TotalViolations"]),
            "iiar9_gap":          gap,
            "is_p3":              is_p3,
            "pre_epa2024":        pre_epa,
            "cers_rv":            cers_rv,
            "cers_flags":         cers_flags,
            # Defaults — may be updated by DLP match
            "locations":          1,
            "accidents":          0,
            "latest_receipt_date": "",
            "epaid":              None,
        })
    return sites


# ── CERS -> DLP FUZZY MATCH (CA only) ─────────────────────────────────────────
def match_cers_to_dlp(cers_sites: list, dlp_cache: Path) -> dict:
    """Fuzzy-match CERS SiteName -> DLP CA FacilityName.

    Returns {site_id: {epaid, accidents, latest_receipt_date}}.
    Threshold: SequenceMatcher ratio ≥ 0.85.
    """
    if not dlp_cache.exists():
        print("[score.py] DLP cache not found — skipping CERS-DLP match.")
        return {}

    dlp    = pd.read_csv(dlp_cache, dtype={"EPAFacilityID": str})
    ca_dlp = dlp[dlp["State"] == "CA"].copy()
    ca_dlp["epaid"] = ca_dlp["EPAFacilityID"].apply(norm_epaid)
    ca_dlp["_norm"] = ca_dlp["Name"].fillna("").apply(_norm_name)

    results = {}
    for site in cers_sites:
        norm_lead  = _norm_name(site["facility_name"])
        best_score = 0.0
        best_row   = None
        for _, row in ca_dlp.iterrows():
            sim = SequenceMatcher(None, norm_lead, row["_norm"]).ratio()
            if sim > best_score:
                best_score = sim
                best_row   = row
        if best_score >= 0.85 and best_row is not None:
            results[site["site_id"]] = {
                "epaid":               best_row["epaid"],
                "accidents":           int(best_row.get("NumAccidentsInLatest") or 0),
                "latest_receipt_date": str(best_row.get("LatestReceiptDate") or ""),
            }

    print(f"[score.py] CERS->DLP match: {len(results)}/{len(cers_sites)} CA sites matched")
    return results


# ── SCORE HISTORY ─────────────────────────────────────────────────────────────
def _update_score_history(rows: list) -> dict:
    """Track tier (inverted: T1->5, T5->1) weekly for CRM followup logic."""
    history_path = OUTPUT_DIR / "score_history.json"
    date_str     = TODAY.strftime("%Y-%m-%d")

    if history_path.exists():
        with open(history_path) as f:
            history = json.load(f)
    else:
        history = {"dates": [], "scores": {}}

    dates  = history["dates"]
    scores = history["scores"]

    current_keys = {r["lead_key"] for r in rows}

    def tier_to_score(t): return 6 - t  # T1->5, T5->1

    if date_str in dates:
        idx = dates.index(date_str)
        for r in rows:
            k = r["lead_key"]
            if k not in scores:
                scores[k] = [None] * len(dates)
            scores[k][idx] = tier_to_score(r["tier"])
        for k in scores:
            if k not in current_keys and len(scores[k]) > idx:
                scores[k][idx] = None
    else:
        dates.append(date_str)
        for r in rows:
            k = r["lead_key"]
            if k not in scores:
                scores[k] = [None] * (len(dates) - 1)
            scores[k].append(tier_to_score(r["tier"]))
        for k in scores:
            if k not in current_keys and len(scores[k]) < len(dates):
                scores[k].append(None)

    if len(dates) > 52:
        trim   = len(dates) - 52
        dates  = dates[trim:]
        scores = {k: v[trim:] for k, v in scores.items()}

    history = {"dates": dates, "scores": scores}
    with open(history_path, "w") as f:
        json.dump(history, f, separators=(",", ":"))
    print(f"[score.py] Updated score_history.json ({len(dates)} weeks, {len(scores)} sites)")
    return history


# ── MAIN PIPELINE ─────────────────────────────────────────────────────────────
def run(national_path: str, cers_path: str = ""):
    rows = []

    # ── Non-CA: national_rmp.csv ──────────────────────────────────────────────
    if national_path and Path(national_path).exists():
        print(f"[score.py] Reading national: {national_path}")
        nat = pd.read_csv(national_path, dtype={"epaid": str})
        nat["latest_receipt_date"] = nat["latest_receipt_date"].fillna("").astype(str)
        nat["locations"] = pd.to_numeric(nat["locations"], errors="coerce").fillna(1).astype(int)
        nat["accidents"] = pd.to_numeric(nat["accidents"], errors="coerce").fillna(0).astype(int)
        nat["nh3_lbs"]   = pd.to_numeric(nat["nh3_lbs"],   errors="coerce")

        for _, r in nat.iterrows():
            loc  = int(r["locations"])
            acc  = int(r["accidents"])
            tier = score_tier(loc, acc)
            rv   = revalid_status(str(r["latest_receipt_date"]))
            ep   = str(r["epaid"]) if pd.notna(r["epaid"]) else None

            def s(col): return str(r[col]).strip() if pd.notna(r.get(col)) and str(r.get(col)).strip() not in ("", "nan") else ""

            rows.append({
                "lead_key":            ep or f"national-{s('facility_name')}",
                "epaid":               ep,
                "facility_name":       s("facility_name"),
                "company":             s("company"),
                "addr":                s("addr"),
                "city":                s("city"),
                "state":               s("state"),
                "zip":                 s("zip"),
                "lat":                 float(r["lat"])  if pd.notna(r.get("lat"))  else None,
                "lng":                 float(r["lng"])  if pd.notna(r.get("lng"))  else None,
                "nh3_lbs":             float(r["nh3_lbs"]) if pd.notna(r["nh3_lbs"]) else None,
                "locations":           loc,
                "accidents":           acc,
                "latest_receipt_date": s("latest_receipt_date"),
                "naics":               s("naics"),
                "territory":           s("territory"),
                "contact_name":        s("contact_name"),
                "contact_phone":       s("contact_phone"),
                "contact_email":       s("contact_email"),
                "tier":                tier,
                "tier_label":          TIER_LABELS[tier],
                "revalid_status":      rv,
                "is_ca":               False,
                "cers_flags":          [],
            })
        print(f"[score.py] National (non-CA) leads: {len(rows):,}")
    else:
        print("[score.py] No national CSV — CA-only mode")

    # ── CA: CERS aggregation ──────────────────────────────────────────────────
    cers_sites = []
    if cers_path and Path(cers_path).exists():
        print(f"[score.py] Reading CERS: {cers_path}")
        cers_sites = aggregate_cers(cers_path)

        # Fuzzy-match CERS -> DLP CA for EPAID + accidents + receipt_date
        dlp_cache   = DATA_DIR / "dlp_facilities.csv"
        dlp_matches = match_cers_to_dlp(cers_sites, dlp_cache)

        for site in cers_sites:
            dlp_m = dlp_matches.get(site["site_id"])
            if dlp_m:
                site["epaid"]               = dlp_m["epaid"]
                site["accidents"]           = dlp_m["accidents"]
                site["latest_receipt_date"] = dlp_m["latest_receipt_date"]
                # Prefer DLP receipt date for revalid if available
                if dlp_m["latest_receipt_date"]:
                    rv = revalid_status(dlp_m["latest_receipt_date"])
                    site["revalid_status"] = rv
                    # Rebuild revalid badge in cers_flags
                    site["cers_flags"] = [f for f in site["cers_flags"] if not f.startswith("Revalid:")]
                    if rv == "overdue":  site["cers_flags"].append("Revalid:OVERDUE")
                    elif rv == "soon":   site["cers_flags"].append("Revalid:SOON")
                else:
                    site["revalid_status"] = site.get("cers_rv", "unknown")
            else:
                site["revalid_status"] = site.get("cers_rv", "unknown")

            tier     = score_tier(site["locations"], site["accidents"])
            lead_key = site["epaid"] if site["epaid"] else f"cers-{site['site_id']}"

            site["tier"]       = tier
            site["tier_label"] = TIER_LABELS[tier]
            site["lead_key"]   = lead_key
            site["territory"]  = "CERS"
            rows.append(site)

        print(f"[score.py] CA (CERS) leads: {len(cers_sites):,}")

    if not rows:
        sys.exit("[score.py] ERROR: No leads loaded. Provide --national or --cers.")

    # ── Sort: T1->T5, then NH3 desc within tier ───────────────────────────────
    def sort_key(r):
        return (r["tier"], -(r.get("nh3_lbs") or 0))
    rows.sort(key=sort_key)

    # ── Stats ─────────────────────────────────────────────────────────────────
    total       = len(rows)
    tier_counts = {str(k): v for k, v in sorted(Counter(r["tier"] for r in rows).items())}
    overdue_ct  = sum(1 for r in rows if r.get("revalid_status") == "overdue")
    soon_ct     = sum(1 for r in rows if r.get("revalid_status") == "soon")

    # State counts for heat map (keyed by 2-letter state code)
    state_counts: dict[str, int] = {}
    for r in rows:
        st = r.get("state", "") or ""
        if st:
            state_counts[st] = state_counts.get(st, 0) + 1

    stats = {
        "generated":      TODAY.strftime("%Y-%m-%d"),
        "total_sites":    total,
        "tier_counts":    tier_counts,
        "revalid_overdue": overdue_ct,
        "revalid_soon":    soon_ct,
        "state_counts":    state_counts,
        "ca_count":        len(cers_sites),
        "national_count":  total - len(cers_sites),
    }

    # ── Write JSON ────────────────────────────────────────────────────────────
    out_json = {"metadata": stats, "leads": rows}
    with open(OUTPUT_DIR / "leads.json", "w") as f:
        json.dump(out_json, f, indent=2, default=str)
    print(f"[score.py] Written: output/leads.json ({total:,} sites)")

    # ── Write CSV ─────────────────────────────────────────────────────────────
    csv_rows = []
    for r in rows:
        row = {k: v for k, v in r.items() if k != "cers_flags"}
        row["cers_flags"] = " | ".join(r.get("cers_flags", []))
        csv_rows.append(row)
    pd.DataFrame(csv_rows).to_csv(OUTPUT_DIR / "leads.csv", index=False)
    print(f"[score.py] Written: output/leads.csv")

    # ── Timestamp ─────────────────────────────────────────────────────────────
    with open(OUTPUT_DIR / "last_updated.txt", "w") as f:
        f.write(TODAY.isoformat())

    # ── Diff & score history ──────────────────────────────────────────────────
    changes       = compute_diff(rows)
    score_history = _update_score_history(rows)

    # ── Build HTML ────────────────────────────────────────────────────────────
    from build_html import build_html
    build_html(stats, rows, changes, score_history=score_history)
    print(f"[score.py] Written: output/dashboard.html")

    # ── Save snapshot for next diff ───────────────────────────────────────────
    save_snapshot(out_json)

    nat_ct  = total - len(cers_sites)
    print(f"[score.py] Done. {total:,} total leads ({nat_ct:,} national + {len(cers_sites):,} CA).")
    if not changes.get("baseline"):
        s = changes["summary"]
        print(f"[score.py] Changes: up={s['moved_up_count']} down={s['moved_down_count']} "
              f"new={s['new_count']} dropped={s['dropped_count']}")
    return stats, rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="National NH3 Lead Scorer")
    parser.add_argument("--national", default="data/national_rmp.csv",
                        help="Path to national_rmp.csv (built by ingest.py)")
    parser.add_argument("--cers", default="",
                        help="Path to CERS CalARP export (.xlsx or .csv)")
    args = parser.parse_args()
    run(args.national, args.cers)
