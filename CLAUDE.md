# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the full pipeline locally:**
```bash
pip install -r requirements.txt
python score.py --input data/CERS_Data_CalARP_Sites.xlsx
```
This generates `output/dashboard.html`, `output/leads.json`, `output/leads.csv`, `output/last_updated.txt`, `output/leads_previous.json`, and `output/changes.json`.

The input file can be `.xlsx`, `.xls`, or `.csv`. The script auto-detects format.

## Architecture

The pipeline runs in this order when `score.py` is invoked:

1. **`score.py`** — Entry point. Reads a CERS CalARP inspection Excel/CSV export, groups rows by `SiteID`, aggregates eval history, and scores each site 1–10 using `score_site()`. Calls `diff.py` then `build_html.py`, then saves a snapshot via `diff.py`.

2. **`diff.py`** — Week-over-week change tracking. `compute_diff()` compares the current scored leads against `output/leads_previous.json`. Returns a changes dict (moved_up, moved_down, new_sites, dropped). `save_snapshot()` writes `leads_previous.json` at the end of a successful run so next week's diff has a baseline.

3. **`build_html.py`** — Generates the self-contained `output/dashboard.html`. Takes the stats dict, full leads list, and changes dict from `score.py`. The HTML file inlines all data as JS constants and has no external dependencies except Google Fonts.

### Scoring logic (`score.py`)

`score_site()` returns `(score, pain_points, notes)`. Pain points are action-oriented triggers that affect score; notes are informational context that don't.

Urgency score starts at 2, capped at 10. Points are added for:
- **+3** IIAR 9 gap: inferred by absence of "IIAR 9"/"RAGAGEP"/"MI" language in notes, only penalized when notes are rich enough to expect a mention (≥2 substantive note rows AND last eval ≥2020, or ≥4 note rows total)
- **+3** RMP revalidation overdue: `latest_eval + 5 years < today` (date-precise, not year-rounded)
- **+1** RMP revalidation due soon: not overdue, but `latest_eval + 5 years < today + 18 months`
- **+2** EPA 2024 RMP rule unaddressed: Program 3 site with no eval after May 2024
- **+1/+2** violation history: +1 for 1–3 violations, +2 for 4+
- **+1** high seismic zone (Bay Area, LA/Ventura — from `HIGH_SEISMIC` list matched against CUPA name)
- **+1** Program 3 confirmed (from notes regex)

Medium seismic zone is an informational note (no score impact).

### Required CERS export columns

`score.py` validates these columns exist: `SiteID`, `SiteName`, `EvalDate`, `ViolationsFound`, `EvalDivision`, `EvalNotes`. Column names are stripped of whitespace before validation.

### CI/CD workflows

- **`weekly_update.yml`**: Runs every Monday at 7 AM UTC. Finds any `.xlsx`/`.csv` in `data/`, runs `score.py`, commits updated `output/` files back to the repo.
- **`pages.yml`**: Triggers on any push that changes `output/dashboard.html`. Copies `dashboard.html` → `_site/index.html` and deploys to GitHub Pages.

### Output files

| File | Description |
|------|-------------|
| `output/leads.json` | Full scored dataset + metadata stats |
| `output/leads.csv` | CRM-importable flat version (pain_points joined with ` \| `) |
| `output/dashboard.html` | Self-contained interactive dashboard (top 200 leads in JS) |
| `output/leads_previous.json` | Snapshot of last run for week-over-week diffing |
| `output/changes.json` | Diff result from last run |
| `output/last_updated.txt` | ISO timestamp of last run |
