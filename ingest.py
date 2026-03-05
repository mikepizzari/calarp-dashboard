"""
ingest.py
---------
Builds data/national_rmp.csv from contacts.xlsx + DLP facilities.csv.

Steps:
  1. Read all 3 sheets from contacts.xlsx (Luke/Brian/Micah), tag with territory
  2. Concatenate, filter NH3_Lbs > 0
  3. Normalize EPAID: float → int string (e.g. 100000001650.0 → "100000001650")
  4. Deduplicate by EPAID (take max Locations value)
  5. Join DLP facilities.csv by EPAID → add latest_receipt_date, dlp_accidents
  6. Write data/national_rmp.csv

Usage:
    python ingest.py
    python ingest.py --contacts data/contacts.xlsx --dlp data/dlp_facilities.csv
"""

import argparse
import io
import urllib.request
from pathlib import Path

import pandas as pd

DATA_DIR = Path("data")

DLP_URL   = (
    "https://raw.githubusercontent.com/data-liberation-project/"
    "epa-rmp-spreadsheets/main/data/output/facilities.csv"
)
DLP_CACHE = DATA_DIR / "dlp_facilities.csv"
OUT_CSV   = DATA_DIR / "national_rmp.csv"


def norm_epaid(v) -> str | None:
    """Convert float EPAID to int string: 100000001650.0 → '100000001650'"""
    if v is None:
        return None
    try:
        import math
        if isinstance(v, float) and math.isnan(v):
            return None
        return str(int(float(v)))
    except (ValueError, TypeError):
        return None


def load_dlp(dlp_path: Path) -> pd.DataFrame:
    """Load DLP facilities.csv from cache or download."""
    if dlp_path.exists():
        print(f"[ingest.py] Using DLP file: {dlp_path}")
        dlp = pd.read_csv(dlp_path, dtype={"EPAFacilityID": str})
    else:
        print(f"[ingest.py] Downloading DLP facilities.csv from GitHub...")
        try:
            with urllib.request.urlopen(DLP_URL, timeout=60) as resp:
                data = resp.read()
            DATA_DIR.mkdir(exist_ok=True)
            dlp_path.write_bytes(data)
            print(f"[ingest.py] Saved DLP cache -> {dlp_path}")
            dlp = pd.read_csv(io.BytesIO(data), dtype={"EPAFacilityID": str})
        except Exception as e:
            print(f"[ingest.py] WARNING: DLP download failed: {e} — proceeding without receipt dates")
            return pd.DataFrame(columns=["epaid", "latest_receipt_date", "dlp_accidents"])

    # Normalize DLP EPAID
    dlp["epaid"] = dlp["EPAFacilityID"].apply(norm_epaid)
    dlp = dlp.rename(columns={
        "LatestReceiptDate":    "latest_receipt_date",
        "NumAccidentsInLatest": "dlp_accidents",
    })
    keep = ["epaid", "latest_receipt_date", "dlp_accidents"]
    return dlp[[c for c in keep if c in dlp.columns]].copy()


def run(contacts_path: Path = DATA_DIR / "contacts.xlsx",
        dlp_path: Path = DLP_CACHE):

    # 1. Read all 3 sheets
    sheets = ["Luke", "Brian", "Micah"]
    dfs = []
    for s in sheets:
        df = pd.read_excel(contacts_path, sheet_name=s)
        df.columns = [c.strip() for c in df.columns]
        df["territory"] = s
        dfs.append(df)
    combined = pd.concat(dfs, ignore_index=True)
    print(f"[ingest.py] Total rows from contacts.xlsx: {len(combined):,}")

    # 2. Filter NH3_Lbs > 0
    nh3 = combined[combined["NH3_Lbs"].notna() & (combined["NH3_Lbs"] > 0)].copy()
    print(f"[ingest.py] NH3 facilities (NH3_Lbs > 0): {len(nh3):,}")

    # 3a. Exclude non-refrigeration NAICS codes:
    #   42491 = Farm Supplies Merchant Wholesalers (fertilizer retail — Nutrien, etc.)
    #   44424 = Nursery, Garden Center & Farm Supply (fertilizer retail — AgVantage/Growmark)
    #   32531 = Fertilizer Manufacturing
    #   11511 = Support Activities for Crop Production
    # These facilities store pressurized anhydrous NH3 for agricultural use,
    # not refrigeration systems — they are not IIAR 9 / RMP compliance prospects.
    EXCLUDE_NAICS = {"42491", "44424", "32531", "11511"}
    nh3["_naics5"] = nh3["NAICS"].fillna("").astype(str).str.strip().str[:5]
    before = len(nh3)
    nh3 = nh3[~nh3["_naics5"].isin(EXCLUDE_NAICS)].copy()
    print(f"[ingest.py] After excluding fertilizer/ag NAICS: {len(nh3):,} "
          f"(removed {before - len(nh3):,})")

    # 3b. Exclude large chemical manufacturers that use NH3 as a process feedstock,
    # not for refrigeration (BASF, Dow Chemical).
    EXCLUDE_ACCOUNTS = {"BASF", "Dow"}
    before = len(nh3)
    nh3 = nh3[~nh3["Account Name"].isin(EXCLUDE_ACCOUNTS)].copy()
    print(f"[ingest.py] After excluding chemical feedstock accounts (BASF/Dow): {len(nh3):,} "
          f"(removed {before - len(nh3):,})")

    # 3. Normalize EPAID
    nh3["epaid"] = nh3["EPAID"].apply(norm_epaid)

    # Normalize Locations (null/NaN → 1)
    nh3["Locations"] = pd.to_numeric(nh3["Locations"], errors="coerce").fillna(1).astype(int)

    # 4. Deduplicate by EPAID — keep row with max Locations
    nh3 = (nh3
           .sort_values("Locations", ascending=False)
           .drop_duplicates(subset="epaid", keep="first")
           .copy())
    print(f"[ingest.py] After dedup by EPAID: {len(nh3):,}")

    # 5. Join DLP for receipt date and accident count
    dlp = load_dlp(dlp_path)
    if not dlp.empty:
        nh3 = nh3.merge(dlp, on="epaid", how="left")
    else:
        nh3["latest_receipt_date"] = ""
        nh3["dlp_accidents"] = 0

    # Use contacts.xlsx Accidents where available; fall back to DLP
    acc_c = pd.to_numeric(nh3.get("Accidents"), errors="coerce").fillna(0).astype(int)
    acc_d = pd.to_numeric(nh3.get("dlp_accidents"), errors="coerce").fillna(0).astype(int)
    nh3["accidents"] = acc_c.combine(acc_d, max)

    # 6. Write output CSV
    def safe_str(col, default=""):
        if col not in nh3.columns:
            return default
        return nh3[col].fillna(default).astype(str).str.strip().str.replace(r'\.0$', '', regex=True)

    out = pd.DataFrame({
        "epaid":               nh3["epaid"],
        "facility_name":       safe_str("Facility Name"),
        "company":             safe_str("Account Name"),
        "addr":                safe_str("Street Address"),
        "city":                safe_str("City"),
        "state":               safe_str("State"),
        "zip":                 safe_str("ZIP"),
        "lat":                 pd.to_numeric(nh3.get("Lat"), errors="coerce"),
        "lng":                 pd.to_numeric(nh3.get("Lng"), errors="coerce"),
        "nh3_lbs":             pd.to_numeric(nh3.get("NH3_Lbs"), errors="coerce"),
        "locations":           nh3["Locations"],
        "accidents":           nh3["accidents"],
        "latest_receipt_date": nh3.get("latest_receipt_date", pd.Series([""] * len(nh3))).fillna("").astype(str).str.strip(),
        "naics":               safe_str("NAICS"),
        "territory":           nh3["territory"],
        "contact_name":        safe_str("Contact Name"),
        "contact_phone":       safe_str("Contact Phone"),
        "contact_email":       safe_str("Contact Email"),
    })

    DATA_DIR.mkdir(exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"[ingest.py] Written: {OUT_CSV} ({len(out):,} rows)")

    # Summary
    matched_dlp = (out["latest_receipt_date"].str.len() > 0).sum()
    has_contact = (out["contact_email"].str.len() > 0).sum()
    print(f"[ingest.py] DLP receipt date matched: {matched_dlp:,}/{len(out):,}")
    print(f"[ingest.py] Has email contact: {has_contact:,}/{len(out):,}")
    print(f"[ingest.py] State distribution (top 10):")
    print(out["state"].value_counts().head(10).to_string())
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NH3 National RMP Ingest")
    parser.add_argument("--contacts", default=str(DATA_DIR / "contacts.xlsx"),
                        help="Path to contacts.xlsx")
    parser.add_argument("--dlp", default=str(DLP_CACHE),
                        help="Path to DLP facilities.csv (downloaded if missing)")
    args = parser.parse_args()
    run(Path(args.contacts), Path(args.dlp))
