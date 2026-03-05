# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the full pipeline locally:**
```bash
pip install -r requirements.txt
python ingest.py                                                          # build national_rmp.csv
python score.py --national data/national_rmp.csv --cers "data/CERS Data_CalARP Sites.xlsx"
```
This generates `output/dashboard.html`, `output/leads.json`, `output/leads.csv`, `output/last_updated.txt`, `output/leads_previous.json`, and `output/changes.json`.

**National-only mode (no CERS file):**
```bash
python score.py --national data/national_rmp.csv
```

## Architecture

The pipeline runs in this order:

1. **`ingest.py`** — Builds `data/national_rmp.csv` from contacts.xlsx (Luke/Brian/Micah sheets) + DLP facilities.csv.
   - Reads all 3 sheets, filters `NH3_Lbs > 0` (→ 5,877 NH3 facilities across 49 states, no CA)
   - Deduplicates by EPAID (max `Locations` value kept)
   - Downloads DLP facilities.csv from GitHub (cached as `data/dlp_facilities.csv`) and joins by EPAID → adds `latest_receipt_date`, `dlp_accidents`
   - Output columns: `epaid, facility_name, company, addr, city, state, zip, lat, lng, nh3_lbs, locations, accidents, latest_receipt_date, naics, territory, contact_name, contact_phone, contact_email`

2. **`score.py`** — Entry point for scoring. Merges national + CA leads, applies tier model, calls diff.py, build_html.py.
   - Loads `data/national_rmp.csv` (non-CA, from ingest.py)
   - Loads CERS CalARP xlsx, aggregates per SiteID → CA leads with IIAR9/violation/EPA2024 flags
   - Fuzzy-matches CERS SiteNames → DLP CA facilities (threshold 0.85) to get EPAID + accidents + receipt_date for CA
   - Scores all sites with unified tier model; sort T1→T5 then NH3 desc

3. **`diff.py`** — Week-over-week change tracking. Primary key: `lead_key` (epaid string for national; `"cers-{site_id}"` for unmatched CA). Compares tier (lower tier number = better; moved_up = tier improved).

4. **`build_html.py`** — Generates `output/dashboard.html`. Inlines all ~7k leads as JS. Filters: Territory (Luke/Brian/Micah/CERS), Tier (T1–T5), State dropdown, search. CA rows show CERS flag badges; non-CA rows show contact panel.

### Tier scoring model (`score.py`)

`score_tier(locations, accidents)` returns tier 1–5 (1=Mega/best, 5=Single/lowest).

**Base tier from `Locations` (parent company facility count):**
| Tier | Label | Locations |
|------|-------|-----------|
| T1 | Mega | > 200 |
| T2 | Major | 51–200 |
| T3 | Mid-Market | 11–50 |
| T4 | Standard | 2–10 |
| T5 | Single | 1 (or null parent) |

**Accident upgrade:** +1 tier (1 accident) or +2 tiers (2+ accidents), capped at T1.

**Revalid status** (from DLP `LatestReceiptDate` + 5 years): `"overdue"` / `"soon"` / `"ok"` / `"unknown"`.

### CERS flags (CA only, display-only — do not affect tier)

| Flag | Condition |
|------|-----------|
| IIAR9 | Absence of IIAR 9 language in recent rich-note evals |
| Violations:N | N ViolationsFound=Yes rows |
| EPA2024 | Program 3 with latest eval pre-May 2024 |
| Revalid:OVERDUE / Revalid:SOON | From eval date or DLP receipt date |

### Data sources

| Source | Role |
|--------|------|
| `data/contacts.xlsx` (Luke/Brian/Micah sheets) | Primary national facility + contact list (non-CA) |
| `data/CERS Data_CalARP Sites.xlsx` | CA facility list + IIAR9/violations/inspection enrichment |
| `data/dlp_facilities.csv` | DLP join for `LatestReceiptDate` + `NumAccidentsInLatest` |
| Google Sheet (runtime fetch) | CRM overlay — status, follow-ups, contact overrides |

### Required CERS export columns

`score.py` validates: `SiteID`, `SiteName`, `EvalDate`, `ViolationsFound`, `EvalDivision`, `EvalNotes`.

### CI/CD workflows

- **`weekly_update.yml`**: Runs every Monday at 7 AM UTC. Downloads DLP CSV, runs `ingest.py`, then `score.py`, commits updated `output/` + `data/` files.
- **`pages.yml`**: Triggers on push that changes `output/dashboard.html`. Deploys to GitHub Pages.

### Output files

| File | Description |
|------|-------------|
| `data/national_rmp.csv` | Built by ingest.py; non-CA NH3 facilities with contact + DLP data |
| `data/dlp_facilities.csv` | Downloaded DLP facilities cache |
| `output/leads.json` | Full scored dataset (~7k sites) + metadata stats |
| `output/leads.csv` | CRM-importable flat version |
| `output/dashboard.html` | Self-contained interactive dashboard (all leads inlined as JS) |
| `output/leads_previous.json` | Snapshot of last run for week-over-week diffing |
| `output/changes.json` | Diff result from last run |
| `output/last_updated.txt` | ISO timestamp of last run |
