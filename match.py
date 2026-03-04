"""
match.py
--------
Fuzzy-matches CERS CalARP sites (output/leads.json) against
data/contacts.xlsx by facility name.

Writes data/site_match.json:
  { site_id_str: { epaid, contact_name, contact_phone, contact_email,
                   nh3_lbs, accidents, match_confidence, matched_name,
                   low_confidence } }

Can also be called from score.py: match.run(leads_list) -> dict
"""

import json
import math
import re
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

DATA_DIR   = Path("data")
OUTPUT_DIR = Path("output")

CONTACTS_FILE = DATA_DIR / "contacts.xlsx"
MATCH_FILE    = DATA_DIR / "site_match.json"

# CERS data is California-only — only match against CA contacts to prevent
# false positives from AZ/UT/NV/etc. facilities with similar names.
LEADS_STATE = "CA"

# Minimum similarity to accept a match at all.
# Above this but below HIGH_CONF → flagged low_confidence=True in UI.
LOW_CONF  = 0.80
HIGH_CONF = 0.90

_FILLER = re.compile(
    r"\b(inc|llc|corp|co|company|the|and|ltd|corporation|industries|"
    r"industry|services|group|holdings|plant|facility|operations|"
    r"warehouse|foods|food|farms|farm|distribution|dist|mfg|"
    r"manufacturing|processing|pack|packing|cold|storage|store)\b"
)

def _norm(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[,.\-'\"&/\\()]", " ", s)
    s = _FILLER.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def _safe(v):
    """Return None for NaN/float-nan values."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def run(leads: list | None = None) -> dict:
    """
    Match leads against contacts.xlsx.

    Args:
        leads: list of lead dicts from score.py. If None, reads output/leads.json.

    Returns:
        dict: {site_id_str: contact_dict}, also writes data/site_match.json.
    """
    if not CONTACTS_FILE.exists():
        print("[match.py] No contacts.xlsx found — skipping match.")
        return {}

    if leads is None:
        leads_path = OUTPUT_DIR / "leads.json"
        if not leads_path.exists():
            print("[match.py] No leads.json found — run score.py first.")
            return {}
        with open(leads_path) as f:
            leads = json.load(f).get("leads", [])

    # Load and normalise contacts — filter to same state as leads
    contacts = pd.read_excel(CONTACTS_FILE)
    contacts.columns = [c.strip() for c in contacts.columns]

    if "State" in contacts.columns and LEADS_STATE:
        contacts = contacts[contacts["State"].str.upper() == LEADS_STATE.upper()]
        if contacts.empty:
            print(f"[match.py] No {LEADS_STATE} records in contacts.xlsx — 0 matches. "
                  f"Add CA facilities to contacts.xlsx to enable contact lookup.")
            with open(MATCH_FILE, "w") as f:
                json.dump({}, f)
            return {}

    contacts["_norm"] = contacts["Facility Name"].fillna("").apply(_norm)
    matched: dict = {}
    low_conf_count = 0

    for lead in leads:
        sid       = str(lead["site_id"])
        norm_lead = _norm(lead["facility_name"])

        best_score = 0.0
        best_row   = None

        for _, row in contacts.iterrows():
            sim = _sim(norm_lead, row["_norm"])
            if sim > best_score:
                best_score = sim
                best_row   = row

        if best_score >= LOW_CONF and best_row is not None:
            is_low = best_score < HIGH_CONF
            if is_low:
                low_conf_count += 1

            # Convert EPAID float → int string (e.g. 100000001650.0 → "100000001650")
            epaid_raw = _safe(best_row.get("EPAID"))
            epaid_str = str(int(epaid_raw)) if epaid_raw is not None else None

            matched[sid] = {
                "epaid":            epaid_str,
                "contact_name":     _safe(best_row.get("Contact Name")),
                "contact_phone":    _safe(best_row.get("Contact Phone")),
                "contact_email":    _safe(best_row.get("Contact Email")),
                "nh3_lbs":          _safe(best_row.get("NH3_Lbs")),
                "accidents":        _safe(best_row.get("Accidents")),
                "matched_name":     str(best_row.get("Facility Name", "")),
                "match_confidence": round(best_score, 3),
                "low_confidence":   is_low,
            }

    DATA_DIR.mkdir(exist_ok=True)
    with open(MATCH_FILE, "w") as f:
        json.dump(matched, f, indent=2, default=str)

    total = len(leads)
    print(f"[match.py] Matched {len(matched)} / {total} CERS sites to contacts.xlsx.")
    if low_conf_count:
        print(f"[match.py] {low_conf_count} low-confidence matches (< {HIGH_CONF:.0%}) — flagged for review.")

    return matched


if __name__ == "__main__":
    result = run()
    print(f"[match.py] Done. {len(result)} matches written to data/site_match.json.")
