"""
build_html.py
-------------
Generates a fully self-contained dashboard HTML file from
the scored lead data produced by score.py.

Supports national NH3 facilities (all 50 states) + CA (CERS).
Filters: State, Territory (Luke/Brian/Micah/CERS), Tier (T1–T5).
"""

import json
from pathlib import Path

OUTPUT_DIR = Path("output")

CRM_SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/e/"
    "2PACX-1vTwnj_oAgynuyp05FomBrZl-UqSTgMu_JVRW-gSUPi133vsOFs0_bu2l9LId8uOTkIDpuqmGbvqksk6"
    "/pub?gid=0&single=true&output=csv"
)

APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbxPgvoUdK-1oUFoL9k0KndCgcCDEKZ7VlrMmTjsykxLNC79TLy7U15afa7EP76XbBk/exec"

TIER_COLORS = {1: "#ef4444", 2: "#ff4d1c", 3: "#f5a623", 4: "#3b82f6", 5: "#6b6b85"}
TIER_LABELS = {1: "Mega", 2: "Major", 3: "Mid-Market", 4: "Standard", 5: "Single"}


def build_html(stats: dict, leads: list, changes: dict = None,
               score_history: dict = None):

    generated    = stats["generated"]
    total        = stats["total_sites"]
    tier_counts  = stats.get("tier_counts", {})
    overdue      = stats["revalid_overdue"]
    soon         = stats["revalid_soon"]
    state_counts = stats.get("state_counts", {})
    ca_count     = stats.get("ca_count", 0)
    national_ct  = stats.get("national_count", total - ca_count)

    score_history = score_history or {"dates": [], "scores": {}}

    # Build table leads (all leads for JS filtering)
    table_leads = []
    for r in leads:
        table_leads.append({
            "k":    r["lead_key"],
            "ep":   r.get("epaid"),
            "t":    r["tier"],
            "tl":   r["tier_label"],
            "n":    r["facility_name"],
            "st":   r.get("state", ""),
            "cupa": r.get("cupa", ""),
            "tr":   r.get("territory", ""),
            "nh":   r.get("nh3_lbs"),
            "rv":   r.get("revalid_status", "unknown"),
            "ca":   r.get("is_ca", False),
            "cf":   r.get("cers_flags", []),
            "cn":   r.get("contact_name", ""),
            "cp":   r.get("contact_phone", ""),
            "ce":   r.get("contact_email", ""),
            "lc":   r.get("locations", 1),
            "ac":   r.get("accidents", 0),
            "co":   r.get("company", ""),
        })

    # Score history keyed by lead_key
    sh_scores = score_history.get("scores", {})
    score_history_js = json.dumps({"dates": score_history["dates"], "scores": sh_scores})

    tier_counts_js  = json.dumps([[int(k), v] for k, v in sorted(
                                   ((int(k), v) for k, v in tier_counts.items()))])
    state_counts_js = json.dumps(state_counts)
    table_leads_js  = json.dumps(table_leads)
    crm_url_js          = json.dumps(CRM_SHEET_URL)
    apps_script_url_js  = json.dumps(APPS_SCRIPT_URL)

    # Change map: {lead_key → {dir, delta, reason}}
    change_map = {}
    if changes and not changes.get("baseline"):
        for r in changes.get("moved_up", []):
            change_map[str(r["lead_key"])] = {"dir": "up",   "delta": r["delta"],  "reason": r.get("reason", "")}
        for r in changes.get("moved_down", []):
            change_map[str(r["lead_key"])] = {"dir": "down", "delta": r["delta"],  "reason": r.get("reason", "")}
        for r in changes.get("new_sites", []):
            change_map[str(r["lead_key"])] = {"dir": "new",  "delta": None, "reason": "New site in this export"}

    change_map_js    = json.dumps(change_map)
    changes_summary  = changes.get("summary", {}) if changes else {}
    changes_prev_dt  = changes.get("prev_date") if changes else None
    is_baseline      = (changes is None) or changes.get("baseline", True)

    moved_up_js   = json.dumps(changes.get("moved_up",   [])[:20] if changes else [])
    moved_down_js = json.dumps(changes.get("moved_down", [])[:20] if changes else [])
    new_sites_js  = json.dumps(changes.get("new_sites",  [])[:20] if changes else [])

    chg_up   = changes_summary.get("moved_up_count", 0)
    chg_down = changes_summary.get("moved_down_count", 0)
    chg_new  = changes_summary.get("new_count", 0)
    prev_lbl = f"vs {changes_prev_dt}" if changes_prev_dt else "baseline run"
    chg_badge = "" if is_baseline else f"""
  <div class="change-badge">
    <span class="cb-item cb-up">&#x25B2; {chg_up} up</span>
    <span class="cb-item cb-down">&#x25BC; {chg_down} down</span>
    <span class="cb-item cb-new">+ {chg_new} new</span>
    <span class="cb-sep">{prev_lbl}</span>
  </div>"""

    # KPI cards: T1–T3 + Overdue + Soon
    t1 = tier_counts.get("1", 0)
    t2 = tier_counts.get("2", 0)
    t3 = tier_counts.get("3", 0)
    t4 = tier_counts.get("4", 0)
    t5 = tier_counts.get("5", 0)

    # All unique states for dropdown
    states = sorted(set(r.get("state", "") for r in leads if r.get("state")))
    state_opts = "\n".join(
        f'<option value="{s}">{s}</option>' for s in states
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NH3 Lead Intelligence Dashboard — {generated}</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
:root{{
  --bg:#09090f;--surface:#111119;--border:#1e1e2e;--border2:#2a2a3e;
  --text:#e8e8f0;--muted:#6b6b85;--accent:#ff4d1c;--amber:#f5a623;
  --green:#2dd4a0;--blue:#3b82f6;--purple:#a855f7;--red:#ef4444;
  --display:"Bebas Neue",sans-serif;--mono:"DM Mono",monospace;--body:"DM Sans",sans-serif;
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:var(--body);font-size:14px;line-height:1.6;min-height:100vh;overflow-x:hidden;}}
::-webkit-scrollbar{{width:5px;height:5px;}}
::-webkit-scrollbar-track{{background:var(--bg);}}
::-webkit-scrollbar-thumb{{background:var(--border2);border-radius:3px;}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:0.3}}}}
header{{position:relative;padding:40px 48px 28px;border-bottom:1px solid var(--border);overflow:hidden;}}
header::after{{content:"NH\2083";position:absolute;right:-20px;top:-30px;font-family:var(--display);font-size:220px;color:var(--accent);opacity:0.04;pointer-events:none;letter-spacing:-8px;}}
.live-badge{{display:inline-flex;align-items:center;gap:8px;background:rgba(255,77,28,0.12);border:1px solid rgba(255,77,28,0.3);border-radius:4px;padding:4px 12px;font-family:var(--mono);font-size:11px;color:var(--accent);letter-spacing:0.12em;text-transform:uppercase;margin-bottom:14px;}}
.live-dot{{width:6px;height:6px;background:var(--accent);border-radius:50%;animation:pulse 2s infinite;}}
h1{{font-family:var(--display);font-size:48px;line-height:1;letter-spacing:2px;margin-bottom:6px;}}
h1 span{{color:var(--accent);}}
.header-sub{{font-family:var(--mono);font-size:11px;color:var(--muted);letter-spacing:0.08em;}}
.header-meta{{display:flex;gap:36px;margin-top:22px;flex-wrap:wrap;}}
.meta-item{{display:flex;flex-direction:column;gap:2px;}}
.meta-label{{font-family:var(--mono);font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.1em;}}
.meta-value{{font-family:var(--display);font-size:26px;letter-spacing:1px;}}
.meta-hot{{color:var(--accent);}}
main{{padding:28px 48px 64px;display:flex;flex-direction:column;gap:24px;}}
.section-label{{display:flex;align-items:center;gap:12px;margin-bottom:16px;}}
.section-label span{{font-family:var(--mono);font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.15em;white-space:nowrap;}}
.section-label::after{{content:"";flex:1;height:1px;background:var(--border);}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:24px;}}
.card-title{{font-family:var(--display);font-size:18px;letter-spacing:1px;margin-bottom:20px;}}
.card-title small{{color:var(--muted);font-size:12px;font-family:var(--mono);font-weight:400;letter-spacing:0;margin-left:8px;}}
.kpi-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;}}
.kpi-card{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:18px 20px;position:relative;overflow:hidden;transition:transform 0.2s,border-color 0.2s;cursor:default;}}
.kpi-card:hover{{transform:translateY(-2px);border-color:var(--border2);}}
.kpi-card::before{{content:"";position:absolute;top:0;left:0;right:0;height:2px;background:var(--kpi-color,var(--accent));}}
.kpi-num{{font-family:var(--display);font-size:42px;line-height:1;color:var(--kpi-color,var(--text));letter-spacing:1px;margin-bottom:4px;}}
.kpi-label{{font-family:var(--mono);font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.1em;line-height:1.4;}}
.kpi-sub{{font-size:11px;color:var(--muted);margin-top:6px;}}
.charts-row{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:16px;}}
.histogram{{display:flex;align-items:flex-end;gap:8px;height:140px;padding-bottom:26px;position:relative;}}
.histogram::after{{content:"";position:absolute;bottom:26px;left:0;right:0;height:1px;background:var(--border);}}
.bar-col{{flex:1;display:flex;flex-direction:column;align-items:center;height:100%;justify-content:flex-end;}}
.bar{{width:100%;border-radius:3px 3px 0 0;min-height:4px;position:relative;transition:opacity 0.2s;cursor:default;}}
.bar:hover{{opacity:0.75;}}
.bar-count{{font-family:var(--mono);font-size:9px;color:var(--muted);position:absolute;top:-17px;left:50%;transform:translateX(-50%);white-space:nowrap;}}
.bar-label{{font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:4px;}}
.donut-wrap{{display:flex;flex-direction:column;align-items:center;gap:16px;}}
.donut-legend{{display:flex;flex-direction:column;gap:8px;width:100%;}}
.legend-item{{display:flex;align-items:center;justify-content:space-between;gap:8px;}}
.legend-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0;}}
.legend-label{{font-size:11px;color:var(--muted);flex:1;}}
.legend-val{{font-family:var(--mono);font-size:11px;}}
.timeline{{display:flex;flex-direction:column;gap:14px;}}
.tl-row{{display:flex;align-items:center;gap:10px;}}
.tl-dot{{width:8px;height:8px;border-radius:50%;flex-shrink:0;}}
.tl-label{{flex:1;font-size:12px;}}
.tl-val{{font-family:var(--display);font-size:22px;line-height:1;}}
.tl-sub{{font-family:var(--mono);font-size:9px;color:var(--muted);}}
.heat-wrap{{position:relative;border-radius:6px;overflow:hidden;background:#1e1e2e;line-height:0;}}
.heat-wrap canvas{{width:100%;height:auto;display:block;filter:blur(22px);transform:scale(1.08);transform-origin:center;}}
.heat-labels{{position:absolute;inset:0;pointer-events:none;}}
.hlbl{{position:absolute;transform:translate(-50%,-50%);font-family:var(--mono);font-size:9px;font-weight:700;color:rgba(255,255,255,0.8);text-shadow:0 1px 4px rgba(0,0,0,0.9);}}
.map-legend-row{{display:flex;gap:10px;margin-top:10px;align-items:center;justify-content:flex-end;}}
.map-legend-bar{{height:7px;width:130px;border-radius:4px;background:linear-gradient(to right,#1a4b8f,#22d3ee,#4ade80,#f5a623,#ef4444);}}
.filter-row{{display:flex;gap:8px;margin-bottom:14px;align-items:center;flex-wrap:wrap;}}
.filter-label{{font-family:var(--mono);font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.1em;}}
.filter-btn{{background:var(--border);border:1px solid var(--border2);color:var(--muted);font-family:var(--mono);font-size:11px;padding:5px 12px;border-radius:4px;cursor:pointer;transition:all 0.15s;}}
.filter-btn:hover,.filter-btn.active{{background:rgba(255,77,28,0.15);border-color:rgba(255,77,28,0.4);color:var(--accent);}}
.filter-sep{{width:1px;height:20px;background:var(--border2);margin:0 4px;}}
.select-filter{{background:var(--border);border:1px solid var(--border2);color:var(--text);font-family:var(--mono);font-size:11px;padding:5px 10px;border-radius:4px;outline:none;cursor:pointer;transition:border-color 0.15s;}}
.select-filter:focus{{border-color:rgba(255,77,28,0.4);}}
.select-filter option{{background:var(--surface);}}
.search-box{{background:var(--border);border:1px solid var(--border2);color:var(--text);font-family:var(--mono);font-size:12px;padding:5px 12px;border-radius:4px;outline:none;margin-left:auto;width:230px;transition:border-color 0.15s;}}
.search-box:focus{{border-color:rgba(255,77,28,0.4);}}
.search-box::placeholder{{color:var(--muted);}}
.table-info{{font-family:var(--mono);font-size:10px;color:var(--muted);margin-bottom:10px;}}
.table-wrap{{overflow-x:auto;}}
table{{width:100%;border-collapse:collapse;font-size:12px;}}
thead tr{{border-bottom:1px solid var(--border2);}}
th{{font-family:var(--mono);font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.1em;padding:8px 12px;text-align:left;white-space:nowrap;cursor:pointer;user-select:none;transition:color 0.15s;}}
th:hover{{color:var(--text);}}
th.sort-active{{color:var(--accent);}}
td{{padding:10px 12px;border-bottom:1px solid var(--border);vertical-align:middle;}}
tr:hover td{{background:rgba(255,255,255,0.02);}}
.tier-badge{{display:inline-flex;align-items:center;justify-content:center;padding:3px 8px;border-radius:4px;font-family:var(--display);font-size:14px;letter-spacing:0.5px;white-space:nowrap;}}
.t1{{background:rgba(239,68,68,0.2);color:#ef4444;border:1px solid rgba(239,68,68,0.3);}}
.t2{{background:rgba(255,77,28,0.2);color:#ff4d1c;border:1px solid rgba(255,77,28,0.3);}}
.t3{{background:rgba(245,166,35,0.2);color:#f5a623;border:1px solid rgba(245,166,35,0.3);}}
.t4{{background:rgba(59,130,246,0.2);color:#3b82f6;border:1px solid rgba(59,130,246,0.3);}}
.t5{{background:var(--border);color:var(--muted);border:1px solid var(--border2);}}
.tag{{display:inline-block;padding:2px 7px;border-radius:3px;font-family:var(--mono);font-size:10px;letter-spacing:0.04em;margin:1px;}}
.tag-red{{background:rgba(239,68,68,0.15);color:var(--red);}}
.tag-amber{{background:rgba(245,166,35,0.15);color:var(--amber);}}
.tag-green{{background:rgba(45,212,160,0.15);color:var(--green);}}
.tag-blue{{background:rgba(59,130,246,0.15);color:var(--blue);}}
.tag-purple{{background:rgba(168,85,247,0.15);color:var(--purple);}}
.tag-gray{{background:rgba(107,114,128,0.18);color:#9ca3af;}}
.fac-name{{font-weight:500;color:var(--text);max-width:220px;}}
.fac-loc{{font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:2px;}}
.fac-crm{{font-family:var(--mono);font-size:10px;min-height:14px;margin-top:2px;}}
.pagination{{display:flex;gap:6px;margin-top:14px;justify-content:center;align-items:center;flex-wrap:wrap;}}
.page-btn{{background:var(--border);border:1px solid var(--border2);color:var(--muted);font-family:var(--mono);font-size:11px;padding:4px 10px;border-radius:4px;cursor:pointer;transition:all 0.15s;}}
.page-btn:hover,.page-btn.active{{background:rgba(255,77,28,0.15);border-color:rgba(255,77,28,0.4);color:var(--accent);}}
.page-info{{font-family:var(--mono);font-size:11px;color:var(--muted);}}
.change-badge{{display:flex;align-items:center;gap:10px;margin-top:12px;flex-wrap:wrap;}}
.cb-item{{font-family:var(--mono);font-size:11px;padding:3px 10px;border-radius:4px;}}
.cb-up{{background:rgba(45,212,160,0.15);color:#2dd4a0;border:1px solid rgba(45,212,160,0.3);}}
.cb-down{{background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid rgba(239,68,68,0.3);}}
.cb-new{{background:rgba(59,130,246,0.15);color:#3b82f6;border:1px solid rgba(59,130,246,0.3);}}
.cb-sep{{font-family:var(--mono);font-size:10px;color:var(--muted);}}
.delta-up{{display:inline-flex;align-items:center;font-family:var(--mono);font-size:10px;color:#2dd4a0;margin-left:5px;vertical-align:middle;}}
.delta-down{{display:inline-flex;align-items:center;font-family:var(--mono);font-size:10px;color:#ef4444;margin-left:5px;vertical-align:middle;}}
.delta-new{{display:inline-flex;align-items:center;font-family:var(--mono);font-size:10px;color:#3b82f6;margin-left:5px;vertical-align:middle;}}
@media(max-width:1100px){{.kpi-grid{{grid-template-columns:repeat(3,1fr);}}.charts-row{{grid-template-columns:1fr;}}.hlbl{{font-size:8px;}}}}
@media(max-width:700px){{header,main{{padding-left:20px;padding-right:20px;}}.kpi-grid{{grid-template-columns:repeat(2,1fr);}}h1{{font-size:36px;}}}}
.changes-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}}
.change-item{{padding:10px 0;border-bottom:1px solid var(--border);}}
.change-item:last-child{{border-bottom:none;}}
.ci-top{{display:flex;align-items:center;gap:8px;margin-bottom:3px;}}
.ci-name{{font-size:12px;font-weight:500;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.ci-meta{{font-family:var(--mono);font-size:10px;color:var(--muted);padding-left:36px;}}
.ci-reason{{font-size:11px;color:var(--muted);padding-left:36px;margin-top:2px;line-height:1.4;}}
@media(max-width:1100px){{.changes-grid{{grid-template-columns:1fr;}}}}
tr.expandable{{cursor:pointer;}}
.expand-icon{{font-family:var(--mono);font-size:12px;color:var(--muted);margin-left:5px;display:inline-block;transition:transform 0.15s;line-height:1;}}
.expand-icon.open{{transform:rotate(90deg);}}
.detail-row td{{padding:0;border-bottom:1px solid var(--border);background:rgba(255,255,255,0.01);}}
.detail-body{{padding:14px 16px 14px 52px;display:flex;gap:24px;align-items:flex-start;flex-wrap:wrap;}}
.flags-list{{flex:1;display:flex;flex-direction:column;gap:7px;min-width:200px;}}
.flag-item{{font-size:11px;color:var(--muted);display:flex;gap:8px;align-items:flex-start;line-height:1.5;}}
.flag-dot{{width:5px;height:5px;border-radius:50%;background:var(--accent);flex-shrink:0;margin-top:5px;}}
.copy-btn{{background:var(--border);border:1px solid var(--border2);color:var(--muted);font-family:var(--mono);font-size:11px;padding:6px 14px;border-radius:4px;cursor:pointer;transition:all 0.15s;white-space:nowrap;align-self:flex-start;}}
.copy-btn:hover{{background:rgba(255,77,28,0.15);border-color:rgba(255,77,28,0.4);color:var(--accent);}}
.copy-btn.copied{{background:rgba(45,212,160,0.15);border-color:rgba(45,212,160,0.4);color:#2dd4a0;}}
.crm-panel{{min-width:200px;max-width:240px;border-left:1px solid var(--border);padding-left:18px;display:flex;flex-direction:column;gap:5px;}}
.crm-field{{font-size:11px;color:var(--muted);display:flex;gap:6px;align-items:flex-start;line-height:1.45;}}
.crm-icon{{flex-shrink:0;width:14px;text-align:center;}}
.crm-value{{color:var(--text);}}
.crm-divider{{border-top:1px solid var(--border);margin-top:6px;padding-top:6px;}}
.crm-status{{display:inline-block;padding:1px 7px;border-radius:3px;font-family:var(--mono);font-size:10px;letter-spacing:0.04em;background:rgba(107,114,128,0.18);color:#9ca3af;}}
.fp-p1{{display:inline-block;padding:1px 7px;border-radius:3px;font-family:var(--mono);font-size:10px;background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid rgba(239,68,68,0.3);}}
.fp-p2{{display:inline-block;padding:1px 7px;border-radius:3px;font-family:var(--mono);font-size:10px;background:rgba(245,166,35,0.15);color:#f5a623;border:1px solid rgba(245,166,35,0.3);}}
.fp-p3{{display:inline-block;padding:1px 7px;border-radius:3px;font-family:var(--mono);font-size:10px;background:rgba(59,130,246,0.15);color:#3b82f6;border:1px solid rgba(59,130,246,0.3);}}
.action-btns{{display:flex;flex-direction:column;gap:6px;align-self:flex-start;}}
.log-btn{{background:var(--border);border:1px solid var(--border2);color:var(--muted);font-family:var(--mono);font-size:11px;padding:6px 14px;border-radius:4px;cursor:pointer;text-decoration:none;display:inline-block;transition:all 0.15s;white-space:nowrap;}}
.log-btn:hover{{background:rgba(59,130,246,0.15);border-color:rgba(59,130,246,0.4);color:var(--blue);}}
.log-form{{background:var(--bg);border:1px solid var(--border2);border-radius:6px;padding:12px 14px;margin-top:6px;display:flex;flex-direction:column;gap:8px;min-width:340px;}}
.log-form-row{{display:flex;gap:10px;flex-wrap:wrap;align-items:flex-end;}}
.log-form label{{font-family:var(--mono);font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.08em;display:flex;flex-direction:column;gap:3px;}}
.log-form input[type=date],.log-form select,.log-form textarea{{background:var(--border);border:1px solid var(--border2);color:var(--text);font-family:var(--mono);font-size:11px;padding:4px 8px;border-radius:4px;outline:none;transition:border-color 0.15s;}}
.log-form input[type=date]:focus,.log-form select:focus,.log-form textarea:focus{{border-color:rgba(59,130,246,0.5);}}
.log-form textarea{{width:100%;resize:vertical;}}
.log-form-actions{{display:flex;gap:6px;align-items:center;margin-top:2px;}}
.submit-btn{{background:rgba(59,130,246,0.2);border:1px solid rgba(59,130,246,0.4);color:var(--blue);font-family:var(--mono);font-size:11px;padding:5px 14px;border-radius:4px;cursor:pointer;transition:all 0.15s;}}
.submit-btn:hover:not(:disabled){{background:rgba(59,130,246,0.35);}}.submit-btn:disabled{{opacity:0.5;cursor:not-allowed;}}
.cancel-btn{{background:transparent;border:1px solid var(--border2);color:var(--muted);font-family:var(--mono);font-size:11px;padding:5px 10px;border-radius:4px;cursor:pointer;transition:all 0.15s;}}
.cancel-btn:hover{{color:var(--text);border-color:rgba(255,255,255,0.2);}}
.log-msg{{font-family:var(--mono);font-size:10px;padding:2px 4px;}}.log-msg.ok{{color:#2dd4a0;}}.log-msg.err{{color:#ef4444;}}
</style>
</head>
<body>
<header>
  <div class="live-badge"><span class="live-dot"></span>UPDATED {generated} &nbsp;·&nbsp; NATIONAL NH3 RMP COVERAGE</div>
  <h1>NH<span>3</span> LEAD DASHBOARD</h1>
  <div class="header-sub">NATIONAL COVERAGE · AMMONIA REFRIGERATION · RMP COMPLIANCE INTELLIGENCE · ALL 50 STATES</div>
  <div class="header-meta">
    <div class="meta-item"><span class="meta-label">Total NH3 Sites</span><span class="meta-value">{total:,}</span></div>
    <div class="meta-item"><span class="meta-label">T1+T2 Priority</span><span class="meta-value meta-hot">{t1+t2:,}</span></div>
    <div class="meta-item"><span class="meta-label">Revalid Overdue</span><span class="meta-value" style="color:#ef4444">{overdue:,}</span></div>
    <div class="meta-item"><span class="meta-label">National</span><span class="meta-value" style="font-size:20px;padding-top:6px">{national_ct:,}</span></div>
    <div class="meta-item"><span class="meta-label">CA (CERS)</span><span class="meta-value" style="font-size:20px;padding-top:6px">{ca_count:,}</span></div>
    <div class="meta-item"><span class="meta-label">Last Updated</span><span class="meta-value" style="font-size:20px;padding-top:6px">{generated}</span></div>
  </div>
  {chg_badge}
</header>
<main>
  <div id="changes-section" style="display:none">
    <div class="section-label"><span>WEEK-OVER-WEEK CHANGES</span></div>
    <div class="changes-grid">
      <div class="card"><div class="card-title">Tier Upgrades <small id="up-count"></small></div><div id="changes-up"></div></div>
      <div class="card"><div class="card-title">Tier Downgrades <small id="down-count"></small></div><div id="changes-down"></div></div>
      <div class="card"><div class="card-title">New Sites <small id="new-count"></small></div><div id="changes-new"></div></div>
    </div>
  </div>
  <div>
    <div class="section-label"><span>TIER DISTRIBUTION</span></div>
    <div class="kpi-grid">
      <div class="kpi-card" style="--kpi-color:#ef4444"><div class="kpi-num">{t1:,}</div><div class="kpi-label">T1 Mega</div><div class="kpi-sub">200+ locations · Enterprise target</div></div>
      <div class="kpi-card" style="--kpi-color:#ff4d1c"><div class="kpi-num">{t2:,}</div><div class="kpi-label">T2 Major</div><div class="kpi-sub">51–200 locations · Multi-site deal</div></div>
      <div class="kpi-card" style="--kpi-color:#f5a623"><div class="kpi-num">{t3:,}</div><div class="kpi-label">T3 Mid-Market</div><div class="kpi-sub">11–50 locations · Regional play</div></div>
      <div class="kpi-card" style="--kpi-color:#a855f7"><div class="kpi-num">{overdue:,}</div><div class="kpi-label">Revalid Overdue</div><div class="kpi-sub">Receipt date + 5yr &lt; today · Call now</div></div>
      <div class="kpi-card" style="--kpi-color:#3b82f6"><div class="kpi-num">{soon:,}</div><div class="kpi-label">Revalid Due Soon</div><div class="kpi-sub">Due within 18 months · Pipeline now</div></div>
    </div>
  </div>
  <div class="charts-row">
    <div class="card">
      <div class="card-title">Tier Distribution <small>n={total:,} sites</small></div>
      <div class="histogram" id="histogram"></div>
    </div>
    <div class="card">
      <div class="card-title">Coverage</div>
      <div class="donut-wrap" id="donut-wrap"></div>
    </div>
    <div class="card">
      <div class="card-title">RMP Revalidation</div>
      <div class="timeline">
        <div class="tl-row"><div class="tl-dot" style="background:#ef4444"></div><div class="tl-label">Overdue now</div><div><div class="tl-val" style="color:#ef4444">{overdue:,}</div><div class="tl-sub">Receipt + 5yr &lt; today</div></div></div>
        <div class="tl-row"><div class="tl-dot" style="background:#f5a623"></div><div class="tl-label">Due soon</div><div><div class="tl-val" style="color:#f5a623">{soon:,}</div><div class="tl-sub">Due within 18 months</div></div></div>
        <div class="tl-row"><div class="tl-dot" style="background:#2dd4a0"></div><div class="tl-label">Within window</div><div><div class="tl-val" style="color:#2dd4a0">{total - overdue - soon:,}</div><div class="tl-sub">OK or unknown date</div></div></div>
      </div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Lead List <small>all {total:,} NH3 sites · full dataset in output/leads.csv</small></div>
    <div class="filter-row">
      <span class="filter-label">Territory:</span>
      <button class="filter-btn active" data-tf="all">ALL</button>
      <button class="filter-btn" data-tf="Luke">LUKE</button>
      <button class="filter-btn" data-tf="Brian">BRIAN</button>
      <button class="filter-btn" data-tf="Micah">MICAH</button>
      <button class="filter-btn" data-tf="CERS">CERS (CA)</button>
      <div class="filter-sep"></div>
      <span class="filter-label">Tier:</span>
      <button class="filter-btn active" data-tier="all">ALL</button>
      <button class="filter-btn" data-tier="1">T1</button>
      <button class="filter-btn" data-tier="2">T2</button>
      <button class="filter-btn" data-tier="3">T3</button>
      <button class="filter-btn" data-tier="4">T4</button>
      <button class="filter-btn" data-tier="5">T5</button>
      <div class="filter-sep"></div>
      <select class="select-filter" id="state-select">
        <option value="">ALL STATES</option>
        {state_opts}
      </select>
      <input class="search-box" id="search" type="text" placeholder="Search facility…">
    </div>
    <div class="table-info" id="table-info"></div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th data-col="t">TIER ↕</th>
          <th>FACILITY / LOCATION</th>
          <th data-col="st">STATE ↕</th>
          <th data-col="tr">TERRITORY ↕</th>
          <th data-col="nh">NH3 LBS ↕</th>
          <th>REVALID</th>
          <th>CONTACT / FLAGS</th>
        </tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
    <div class="pagination" id="pagination"></div>
  </div>
</main>
<script>
const TIER_COLORS = {{1:'#ef4444',2:'#ff4d1c',3:'#f5a623',4:'#3b82f6',5:'#6b6b85'}};
const TIER_LABELS = {{1:'Mega',2:'Major',3:'Mid-Market',4:'Standard',5:'Single'}};
const TIER_DIST   = {tier_counts_js};
const STATE_COUNTS = {state_counts_js};
const LEADS       = {table_leads_js};
const SCORE_HISTORY = {score_history_js};
const CHANGE_MAP  = {change_map_js};
const MOVED_UP    = {moved_up_js};
const MOVED_DOWN  = {moved_down_js};
const NEW_SITES   = {new_sites_js};
const IS_BASELINE = {'true' if is_baseline else 'false'};
const PREV_DATE   = "{changes_prev_dt or ''}";
const CRM_SHEET_URL = {crm_url_js};
const APPS_SCRIPT_URL = {apps_script_url_js};

// ── Tier histogram ────────────────────────────────────────────────────────────
const maxBar = Math.max(...TIER_DIST.map(d=>d[1]));
const hist   = document.getElementById('histogram');
TIER_DIST.forEach(([tier,count])=>{{
  const pct = (count/maxBar)*100;
  const col = document.createElement('div');
  col.className = 'bar-col';
  col.innerHTML = `<div class="bar" style="height:${{pct}}%;background:${{TIER_COLORS[tier]}}" title="T${{tier}} ${{TIER_LABELS[tier]}}: ${{count}} sites"><span class="bar-count">${{count}}</span></div><span class="bar-label">T${{tier}}</span>`;
  hist.appendChild(col);
}});

// ── Coverage donut (national vs CA) ──────────────────────────────────────────
const total_s={total}, nat_s={national_ct}, ca_s={ca_count};
const R=46,cx=60,cy=60,circ=2*Math.PI*R;
const nw=(nat_s/total_s)*circ, cw=(ca_s/total_s)*circ;
document.getElementById('donut-wrap').innerHTML=`
  <svg viewBox="0 0 120 120" width="120" height="120">
    <circle cx="${{cx}}" cy="${{cy}}" r="${{R}}" fill="none" stroke="#1e1e2e" stroke-width="18"/>
    <circle cx="${{cx}}" cy="${{cy}}" r="${{R}}" fill="none" stroke="#ff4d1c" stroke-width="18"
      stroke-dasharray="${{nw}} ${{circ-nw}}" stroke-dashoffset="${{circ/4}}" />
    <circle cx="${{cx}}" cy="${{cy}}" r="${{R}}" fill="none" stroke="#3b82f6" stroke-width="18"
      stroke-dasharray="${{cw}} ${{circ-cw}}" stroke-dashoffset="${{circ/4-nw}}" />
    <text x="${{cx}}" y="56" text-anchor="middle" font-family="Bebas Neue,sans-serif" font-size="22" fill="#e8e8f0">${{nat_s}}</text>
    <text x="${{cx}}" y="67" text-anchor="middle" font-family="DM Mono,monospace" font-size="8" fill="#6b6b85">NATIONAL</text>
  </svg>
  <div class="donut-legend">
    <div class="legend-item"><div class="legend-dot" style="background:#ff4d1c"></div><span class="legend-label">National (49 states)</span><span class="legend-val">${{nat_s}} <span style="color:#6b6b85;font-size:10px">${{Math.round(nat_s/total_s*100)}}%</span></span></div>
    <div class="legend-item"><div class="legend-dot" style="background:#3b82f6"></div><span class="legend-label">California (CERS)</span><span class="legend-val">${{ca_s}} <span style="color:#6b6b85;font-size:10px">${{Math.round(ca_s/total_s*100)}}%</span></span></div>
  </div>`;

// ── State radial gradient heat map ─────────────────────────────────────────────
// State centroids [lat, lng] — approximate geographic centers
const SC={{'AK':[64.2,-153.4],'AL':[32.8,-86.8],'AR':[34.8,-92.2],'AZ':[34.3,-111.1],'CA':[37.2,-119.4],'CO':[39.1,-105.4],'CT':[41.6,-72.7],'DC':[38.9,-77.0],'DE':[39.1,-75.5],'FL':[27.8,-81.7],'GA':[32.7,-83.4],'HI':[20.8,-156.6],'IA':[42.1,-93.5],'ID':[44.4,-114.5],'IL':[40.0,-89.2],'IN':[40.0,-86.1],'KS':[38.5,-98.3],'KY':[37.5,-85.3],'LA':[31.2,-91.8],'MA':[42.2,-71.5],'MD':[39.0,-76.8],'ME':[45.3,-69.2],'MI':[44.3,-85.4],'MN':[46.4,-93.2],'MO':[38.4,-92.5],'MS':[32.7,-89.7],'MT':[47.0,-110.5],'NC':[35.6,-79.4],'ND':[47.5,-100.5],'NE':[41.5,-99.9],'NH':[43.7,-71.6],'NJ':[40.2,-74.7],'NM':[34.8,-106.2],'NV':[39.5,-116.7],'NY':[42.9,-75.5],'OH':[40.4,-82.8],'OK':[35.6,-97.5],'OR':[44.0,-120.5],'PA':[40.9,-77.8],'RI':[41.7,-71.5],'SC':[33.9,-80.9],'SD':[44.4,-100.3],'TN':[35.9,-86.7],'TX':[31.5,-99.3],'UT':[39.4,-111.1],'VA':[37.5,-79.4],'VT':[44.0,-72.7],'WA':[47.4,-120.5],'WI':[44.3,-89.8],'WV':[38.6,-80.6],'WY':[43.0,-107.6]}};
(function(){{
  const cv=document.getElementById('heat-canvas'); if(!cv)return;
  const ctx=cv.getContext('2d');
  const W=cv.width, H=cv.height;
  function proj(lat,lng){{
    if(lat>54){{
      const x=W*0.04+(lng+180)/((-130)-(-180))*W*0.17;
      const y=H*0.68+(1-(lat-54)/(72-54))*H*0.28;
      return[x,y];
    }}
    if(lng<-140){{
      const x=W*0.23+(lng+162)/((-154)-(-162))*W*0.15;
      const y=H*0.78+(1-(lat-18)/(23-18))*H*0.18;
      return[x,y];
    }}
    const x=(lng-(-125))/((-66)-(-125))*(W*0.82)+W*0.10;
    const y=(1-(lat-24)/(50-24))*(H*0.83)+H*0.06;
    return[x,y];
  }}
  const STOPS=[[0,[26,75,143]],[0.25,[34,211,238]],[0.5,[74,222,128]],[0.75,[245,166,35]],[1,[239,68,68]]];
  function heatColor(t){{
    for(let i=1;i<STOPS.length;i++){{
      if(t<=STOPS[i][0]){{
        const s=(t-STOPS[i-1][0])/(STOPS[i][0]-STOPS[i-1][0]);
        const a=STOPS[i-1][1],b=STOPS[i][1];
        return[Math.round(a[0]+s*(b[0]-a[0])),Math.round(a[1]+s*(b[1]-a[1])),Math.round(a[2]+s*(b[2]-a[2]))];
      }}
    }}
    return STOPS[STOPS.length-1][1];
  }}
  const maxSt=Math.max(1,...Object.values(STATE_COUNTS));
  ctx.fillStyle='#1e1e2e'; ctx.fillRect(0,0,W,H);
  [0.55,1.0].forEach(function(pass){{
    Object.keys(SC).forEach(function(st){{
      const cnt=STATE_COUNTS[st]||0; if(!cnt)return;
      const[lat,lng]=SC[st];
      const[x,y]=proj(lat,lng);
      const t=Math.sqrt(cnt/maxSt);
      const[r,g,b]=heatColor(t);
      const radius=Math.max(35,t*190)*pass;
      const grad=ctx.createRadialGradient(x,y,0,x,y,radius);
      grad.addColorStop(0,'rgba('+r+','+g+','+b+',0.85)');
      grad.addColorStop(0.5,'rgba('+r+','+g+','+b+',0.45)');
      grad.addColorStop(1,'rgba('+r+','+g+','+b+',0)');
      ctx.fillStyle=grad; ctx.fillRect(0,0,W,H);
    }});
  }});
  const labEl=document.getElementById('heat-labels');
  if(labEl){{Object.keys(SC).forEach(function(st){{
    const cnt=STATE_COUNTS[st]||0;
    const[lat,lng]=SC[st];
    const[x,y]=proj(lat,lng);
    const span=document.createElement('span');
    span.className='hlbl';
    span.title=st+': '+(cnt||0)+' site'+(cnt!==1?'s':'');
    span.textContent=st;
    span.style.left=(x/W*100).toFixed(1)+'%';
    span.style.top=(y/H*100).toFixed(1)+'%';
    labEl.appendChild(span);
  }});}}
}})();

// ── CRM ───────────────────────────────────────────────────────────────────────
let CRM = {{}};
const LOCAL_KEY = 'calarp_crm';

function _parseCSVLine(line) {{
  const res=[]; let cur='', inQ=false;
  for(let i=0;i<line.length;i++) {{
    const c=line[i];
    if(c==='"'){{ inQ=!inQ; }}
    else if(c===','&&!inQ){{ res.push(cur); cur=''; }}
    else cur+=c;
  }}
  res.push(cur); return res;
}}

fetch(CRM_SHEET_URL)
  .then(r=>r.text())
  .then(text=>{{
    const lines=text.trim().split('\\n');
    if(!lines.length) return;
    const hdrs=_parseCSVLine(lines[0]).map(h=>h.trim().toLowerCase());
    lines.slice(1).forEach(line=>{{
      const vals=_parseCSVLine(line);
      const row={{}};
      hdrs.forEach((h,i)=>row[h]=(vals[i]||'').trim());
      const rawKey=row['site_id']||row['epaid']||row['lead_key']||'';
      const key=rawKey.replace(/\\.0$/,'');
      if(key) CRM[key]=row;
    }});
    console.log(`[CRM] Loaded ${{Object.keys(CRM).length}} records`);
    try{{const sv=JSON.parse(localStorage.getItem(LOCAL_KEY)||'{{}}');Object.keys(sv).forEach(k=>{{if(!CRM[k])CRM[k]=sv[k];}});}}catch(e){{}}
    render();
  }})
  .catch(e=>console.warn('[CRM] Fetch failed:',e));

function _scoreAtContact(key, lastContact) {{
  if(!lastContact||!SCORE_HISTORY.dates||!SCORE_HISTORY.scores[key]) return null;
  const dates=SCORE_HISTORY.dates, scores=SCORE_HISTORY.scores[key];
  let best=-1;
  dates.forEach((d,i)=>{{ if(d<=lastContact) best=i; }});
  return best>=0 ? scores[best] : null;
}}

function _followupFlag(lead, crm) {{
  if(!crm) return null;
  const today=new Date().toISOString().slice(0,10);
  const key=String(lead.k);
  const last=crm['last_contact_date']||'';
  const next=crm['next_followup_date']||'';
  if(last) {{
    const sac=_scoreAtContact(key, last);
    if(sac!==null) {{
      // Score is inverted tier (T1→5, T5→1). Higher = better tier.
      if(sac<4&&lead.t<=2) return 'P1';  // was T3+ at contact, now T1/T2
      const curScore=6-lead.t;
      if(curScore>sac) return 'P2';      // tier improved since contact
    }}
  }}
  if(next&&next<=today) return 'P3';
  if(last) {{
    const days=(new Date(today)-new Date(last))/86400000;
    if(days>=30) return 'P3';
  }}
  return null;
}}

function _flagHtml(flag) {{
  if(!flag) return '';
  const titles={{P1:'Tier upgraded since last contact',P2:'Priority improved since last contact',P3:'Follow-up due'}};
  return `<span class="fp-${{flag.toLowerCase()}}" title="${{titles[flag]||flag}}">${{flag}}</span>`;
}}

function _cersFlagsHtml(cf) {{
  if(!cf||!cf.length) return '';
  return cf.map(f=>{{
    if(f==='IIAR9') return '<span class="tag tag-red">IIAR9 Gap</span>';
    if(f.startsWith('Violations:')) {{
      const n=f.split(':')[1];
      return `<span class="tag tag-amber">${{n}} Violation${{n>1?'s':''}}</span>`;
    }}
    if(f==='EPA2024') return '<span class="tag tag-purple">EPA 2024</span>';
    if(f==='Revalid:OVERDUE') return '<span class="tag tag-red">Revalid OVERDUE</span>';
    if(f==='Revalid:SOON') return '<span class="tag tag-amber">Revalid SOON</span>';
    return `<span class="tag tag-gray">${{f}}</span>`;
  }}).join(' ');
}}

function _crmPanelHtml(l) {{
  const key=String(l.k);
  const crm=CRM[key]||null;
  const name  = (crm&&crm['override_contact_name'])  || l.cn || '';
  const phone = (crm&&crm['override_contact_phone']) || l.cp || '';
  const email = (crm&&crm['override_contact_email']) || l.ce || '';
  const hasContact = name||phone||email;
  const flag = _followupFlag(l, crm);

  let html='<div class="crm-panel">';
  if(l.ca) {{
    // CA: show CERS flags instead of contact
    const flags=_cersFlagsHtml(l.cf);
    if(flags) {{
      html+=`<div style="font-size:11px;color:var(--muted);margin-bottom:6px">CERS Compliance Flags:</div>`;
      html+=`<div style="display:flex;flex-wrap:wrap;gap:4px">${{flags}}</div>`;
    }} else {{
      html+='<div style="font-size:11px;color:var(--muted)">No CERS flags detected</div>';
    }}
    if(crm) {{
      html+='<div class="crm-divider">';
      const status=crm['status']||'', last=crm['last_contact_date']||'', next=crm['next_followup_date']||'';
      const today=new Date().toISOString().slice(0,10);
      if(flag||status) html+=`<div class="crm-field">${{_flagHtml(flag)}} ${{status?`<span class="crm-status">${{status}}</span>`:''}}</div>`;
      if(last) html+=`<div class="crm-field"><span class="crm-icon" style="font-size:10px">&#x1F4C5;</span><span class="crm-value">Last: ${{last}}</span></div>`;
      if(next) html+=`<div class="crm-field" style="color:${{next<=today?'#ef4444':'inherit'}}"><span class="crm-icon" style="font-size:10px">&#x23F0;</span><span class="crm-value">Next: ${{next}}</span></div>`;
      const notes=crm['crm_notes']||'';
      if(notes) html+=`<div class="crm-field" style="margin-top:4px;font-style:italic">${{notes}}</div>`;
      html+='</div>';
    }}
  }} else {{
    // Non-CA: show contact info
    if(hasContact) {{
      if(name)  html+=`<div class="crm-field"><span class="crm-icon">&#x1F464;</span><span class="crm-value">${{name}}</span></div>`;
      if(phone) html+=`<div class="crm-field"><span class="crm-icon">&#x1F4DE;</span><span class="crm-value">${{phone}}</span></div>`;
      if(email) html+=`<div class="crm-field"><span class="crm-icon">&#x2709;</span><span class="crm-value">${{email}}</span></div>`;
    }} else {{
      html+='<div style="font-size:11px;color:var(--muted);line-height:1.4">No contact info yet<br><span style="font-size:10px">Add row to CRM sheet</span></div>';
    }}
    if(crm) {{
      html+='<div class="crm-divider">';
      const status=crm['status']||'', last=crm['last_contact_date']||'', next=crm['next_followup_date']||'';
      const today=new Date().toISOString().slice(0,10);
      if(flag||status) html+=`<div class="crm-field">${{_flagHtml(flag)}} ${{status?`<span class="crm-status">${{status}}</span>`:''}}</div>`;
      const assigned=crm['assigned_to']||'';
      if(assigned) html+=`<div class="crm-field"><span class="crm-icon" style="font-size:10px">&#x1F465;</span><span class="crm-value">${{assigned}}</span></div>`;
      if(last) html+=`<div class="crm-field"><span class="crm-icon" style="font-size:10px">&#x1F4C5;</span><span class="crm-value">Last: ${{last}}</span></div>`;
      if(next) html+=`<div class="crm-field" style="color:${{next<=today?'#ef4444':'inherit'}}"><span class="crm-icon" style="font-size:10px">&#x23F0;</span><span class="crm-value">Next: ${{next}}</span></div>`;
      const notes=crm['crm_notes']||'';
      if(notes) html+=`<div class="crm-field" style="margin-top:4px;font-style:italic">${{notes}}</div>`;
      html+='</div>';
    }}
  }}
  html+='</div>';
  return html;
}}

function _logFormHtml(l) {{
  const key=String(l.k);
  const crm=CRM[key]||{{}};
  const today=new Date().toISOString().slice(0,10);
  const d=crm['last_contact_date']||today;
  const nxt=crm['next_followup_date']||'';
  const notes=(crm['crm_notes']||'').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const curStatus=crm['status']||'';
  const statuses=['Contacted','Interested','Demo Scheduled','Proposal Sent','Closed','Not Interested'];
  const statusOpts=statuses.map(s=>'<option value="'+s+'"'+(curStatus===s?' selected':'')+'>'+s+'</option>').join('');
  return '<div class="log-form" onclick="event.stopPropagation()">'+
    '<div class="log-form-row">'+
      '<label>Contact Date *<input type="date" id="lf-date-'+key+'" value="'+d+'"></label>'+
      '<label>Status<select id="lf-status-'+key+'">'+statusOpts+'</select></label>'+
      '<label>Next Follow-up<input type="date" id="lf-next-'+key+'" value="'+nxt+'"></label>'+
    '</div>'+
    '<label style="margin-top:2px">Notes<textarea id="lf-notes-'+key+'" rows="2" style="min-width:280px">'+notes+'</textarea></label>'+
    '<div class="log-form-actions">'+
      '<button class="submit-btn" id="lf-submit-'+key+'" data-key="'+key+'" onclick="event.stopPropagation();submitLogForm(this.dataset.key)">Submit</button>'+
      '<button class="cancel-btn" onclick="event.stopPropagation();logFormKey=null;render()">Cancel</button>'+
      '<span class="log-msg" id="lf-msg-'+key+'"></span>'+
    '</div>'+
  '</div>';
}}

function submitLogForm(key) {{
  if(!APPS_SCRIPT_URL) {{
    const msg=document.getElementById('lf-msg-'+key);
    if(msg){{msg.textContent='Apps Script URL not configured.';msg.className='log-msg err';}}
    return;
  }}
  const dateEl=document.getElementById('lf-date-'+key);
  if(!dateEl||!dateEl.value) {{
    const msg=document.getElementById('lf-msg-'+key);
    if(msg){{msg.textContent='Contact date is required.';msg.className='log-msg err';}}
    return;
  }}
  const lead=LEADS.find(x=>String(x.k)===String(key));
  const payload={{
    lead_key: key,
    facility_name: lead?lead.n:'',
    territory: lead?lead.tr:'',
    tier: lead?lead.t:'',
    last_contact_date: dateEl.value,
    status: document.getElementById('lf-status-'+key).value,
    crm_notes: document.getElementById('lf-notes-'+key).value,
    next_followup_date: document.getElementById('lf-next-'+key).value,
  }};
  const submitBtn=document.getElementById('lf-submit-'+key);
  const msg=document.getElementById('lf-msg-'+key);
  if(submitBtn) submitBtn.disabled=true;
  if(msg){{msg.textContent='Saving\u2026';msg.className='log-msg';}}
  const qs=new URLSearchParams({{data:JSON.stringify(payload)}});
  fetch(APPS_SCRIPT_URL+'?'+qs.toString(),{{mode:'no-cors'}})
    .then(()=>{{
      if(!CRM[key]) CRM[key]={{}};
      CRM[key]['last_contact_date']=payload.last_contact_date;
      CRM[key]['status']=payload.status;
      CRM[key]['crm_notes']=payload.crm_notes;
      CRM[key]['next_followup_date']=payload.next_followup_date;
      try{{const sv=JSON.parse(localStorage.getItem(LOCAL_KEY)||'{{}}');sv[key]=CRM[key];localStorage.setItem(LOCAL_KEY,JSON.stringify(sv));}}catch(e){{}}
      logFormKey=null;
      render();
    }})
    .catch(err=>{{
      if(msg){{msg.textContent='Error: '+err;msg.className='log-msg err';}}
      if(submitBtn) submitBtn.disabled=false;
    }});
}}

function _editFormHtml(l) {{
  const key=String(l.k);
  const crm=CRM[key]||{{}};
  const oName=(crm['override_contact_name']||'').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const oPhone=(crm['override_contact_phone']||'').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  const oEmail=(crm['override_contact_email']||'').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  return '<div class="log-form" onclick="event.stopPropagation()">'+
    '<div class="log-form-row">'+
      '<label>Override Name<input type="text" id="ef-name-'+key+'" value="'+oName+'" placeholder="Contact name"></label>'+
      '<label>Override Phone<input type="tel" id="ef-phone-'+key+'" value="'+oPhone+'" placeholder="Phone number"></label>'+
      '<label>Override Email<input type="email" id="ef-email-'+key+'" value="'+oEmail+'" placeholder="Email address"></label>'+
    '</div>'+
    '<div class="log-form-actions">'+
      '<button class="submit-btn" id="ef-submit-'+key+'" data-key="'+key+'" onclick="event.stopPropagation();submitEditContact(this.dataset.key)">Save</button>'+
      '<button class="cancel-btn" onclick="event.stopPropagation();editFormKey=null;render()">Cancel</button>'+
      '<span class="log-msg" id="ef-msg-'+key+'"></span>'+
    '</div>'+
  '</div>';
}}

function submitEditContact(key) {{
  if(!APPS_SCRIPT_URL) {{
    const msg=document.getElementById('ef-msg-'+key);
    if(msg){{msg.textContent='Apps Script URL not configured.';msg.className='log-msg err';}}
    return;
  }}
  const lead=LEADS.find(x=>String(x.k)===String(key));
  const payload={{
    lead_key: key,
    facility_name: lead?lead.n:'',
    territory: lead?lead.tr:'',
    tier: lead?lead.t:'',
    override_contact_name: document.getElementById('ef-name-'+key).value,
    override_contact_phone: document.getElementById('ef-phone-'+key).value,
    override_contact_email: document.getElementById('ef-email-'+key).value,
  }};
  const submitBtn=document.getElementById('ef-submit-'+key);
  const msg=document.getElementById('ef-msg-'+key);
  if(submitBtn) submitBtn.disabled=true;
  if(msg){{msg.textContent='Saving\u2026';msg.className='log-msg';}}
  const qs=new URLSearchParams({{data:JSON.stringify(payload)}});
  fetch(APPS_SCRIPT_URL+'?'+qs.toString(),{{mode:'no-cors'}})
    .then(()=>{{
      if(!CRM[key]) CRM[key]={{}};
      CRM[key]['override_contact_name']=payload.override_contact_name;
      CRM[key]['override_contact_phone']=payload.override_contact_phone;
      CRM[key]['override_contact_email']=payload.override_contact_email;
      try{{const sv=JSON.parse(localStorage.getItem(LOCAL_KEY)||'{{}}');sv[key]=CRM[key];localStorage.setItem(LOCAL_KEY,JSON.stringify(sv));}}catch(e){{}}
      editFormKey=null;
      render();
    }})
    .catch(err=>{{
      if(msg){{msg.textContent='Error: '+err;msg.className='log-msg err';}}
      if(submitBtn) submitBtn.disabled=false;
    }});
}}

// ── Table ─────────────────────────────────────────────────────────────────────
let terrFilter='all', tierFilter='all', stateFilter='', search='', page=1, sortCol='t', sortAsc=true, expandedKey=null, logFormKey=null, editFormKey=null;
const PAGE=20;

function tierClass(t){{ return 't'+t; }}
function revalidTag(rv){{
  if(rv==='overdue') return '<span class="tag tag-red">OVERDUE</span>';
  if(rv==='soon')    return '<span class="tag tag-amber">DUE SOON</span>';
  if(rv==='ok')      return '<span class="tag tag-green">OK</span>';
  return '<span class="tag tag-gray">—</span>';
}}
function fmtNH3(v){{
  if(!v) return '<span style="color:var(--muted)">—</span>';
  return v>=1000000 ? (v/1000000).toFixed(1)+'M' : v>=1000 ? Math.round(v/1000)+'K' : String(v);
}}

function getFiltered(){{
  return LEADS.filter(l=>{{
    const ft = terrFilter==='all' ? true : l.tr===terrFilter;
    const fi = tierFilter==='all'  ? true : l.t===parseInt(tierFilter);
    const fs = stateFilter ? l.st===stateFilter : true;
    const fq = l.n.toLowerCase().includes(search);
    return ft&&fi&&fs&&fq;
  }}).sort((a,b)=>{{
    let va=a[sortCol], vb=b[sortCol];
    if(typeof va==='string') return sortAsc?va.localeCompare(vb):vb.localeCompare(va);
    va=va??Infinity; vb=vb??Infinity;
    return sortAsc?va-vb:vb-va;
  }});
}}

function copyLead(key, btn) {{
  const l=LEADS.find(x=>x.k===key); if(!l) return;
  const crm=CRM[String(key)]||null;
  const name  = (crm&&crm['override_contact_name'])  || l.cn || '';
  const phone = (crm&&crm['override_contact_phone']) || l.cp || '';
  const email = (crm&&crm['override_contact_email']) || l.ce || '';
  const lines=[
    `FACILITY: ${{l.n}}`,
    `STATE: ${{l.st}}${{l.ca?' (CERS/CA)':''}}`,
    `TERRITORY: ${{l.tr}}`,
    `TIER: T${{l.t}} ${{l.tl}}`,
    `LOCATIONS: ${{l.lc}}`,
    `NH3 LBS: ${{l.nh||'—'}}`,
    `REVALID: ${{l.rv}}`,
    ...(l.ac?[`ACCIDENTS: ${{l.ac}}`]:[]),
    ...(l.ep?[`EPAID: ${{l.ep}}`]:[]),
    ...((l.ca&&l.cf&&l.cf.length)?['', 'CERS FLAGS:', ...l.cf.map(f=>`• ${{f}}`)]:[]),
    ...((!l.ca&&(name||phone||email))?['', 'CONTACT:', ...(name?[`  Name:  ${{name}}`]:[]), ...(phone?[`  Phone: ${{phone}}`]:[]), ...(email?[`  Email: ${{email}}`]:[])]:[]),
    ...(crm&&crm['crm_notes']?['', `CRM NOTES: ${{crm['crm_notes']}}`]:[]),
  ];
  navigator.clipboard.writeText(lines.join('\\n')).then(()=>{{
    btn.textContent='Copied!'; btn.classList.add('copied');
    setTimeout(()=>{{btn.textContent='Copy Lead'; btn.classList.remove('copied');}}, 1800);
  }});
}}

function _updateCRMBadges() {{
  document.querySelectorAll('tr.expandable[data-key]').forEach(tr=>{{
    const key=tr.dataset.key;
    const lead=LEADS.find(l=>String(l.k)===key);
    if(!lead) return;
    const crm=CRM[key]; if(!crm) return;
    const flag=_followupFlag(lead,crm);
    const status=crm['status']||'';
    const el=tr.querySelector('.fac-crm'); if(!el) return;
    let txt='';
    if(flag) txt+=_flagHtml(flag)+' ';
    if(status) txt+=`<span style="font-size:10px;color:var(--muted)">${{status}}</span>`;
    el.innerHTML=txt;
  }});
}}

function render(){{
  const data=getFiltered(); const pages=Math.ceil(data.length/PAGE)||1;
  const cp=Math.min(page,pages); const slice=data.slice((cp-1)*PAGE,cp*PAGE);
  document.getElementById('table-info').textContent=`${{data.length.toLocaleString()}} results · page ${{cp}} of ${{pages}}`;
  document.getElementById('tbody').innerHTML=slice.map(l=>{{
    const chg=CHANGE_MAP[String(l.k||'')];
    let deltaHtml='';
    if(chg&&chg.dir==='up')   deltaHtml=`<span class="delta-up" title="${{chg.reason}}">&#x25B2;T${{chg.delta}}</span>`;
    if(chg&&chg.dir==='down') deltaHtml=`<span class="delta-down" title="${{chg.reason}}">&#x25BC;T${{Math.abs(chg.delta)}}</span>`;
    if(chg&&chg.dir==='new')  deltaHtml=`<span class="delta-new">NEW</span>`;
    const isOpen=expandedKey===l.k;
    const crmPanelHtml = isOpen ? _crmPanelHtml(l) : '';
    const logForm = isOpen && logFormKey===l.k ? _logFormHtml(l) : '';
    const editForm = isOpen && editFormKey===l.k ? _editFormHtml(l) : '';
    const logUrl=CRM_SHEET_URL.replace('&output=csv','');
    // Contact/flag summary in table cell
    const crmRow = CRM[String(l.k)]||null;
    const crmStatus = crmRow&&crmRow['status'] ? crmRow['status'] : null;
    const hasContact = l.cn||l.cp||l.ce||
      (crmRow&&(crmRow['override_contact_name']||crmRow['override_contact_phone']||crmRow['override_contact_email']));
    const contactCell = l.ca
      ? _cersFlagsHtml(l.cf)||'<span style="color:var(--muted);font-size:10px">CERS</span>'
      : crmStatus ? `<span class="tag tag-green">&#x2713; ${{crmStatus}}</span>`
      : hasContact ? '<span class="tag tag-blue">&#x260E; Info</span>'
      : '<span class="tag tag-gray">&#x2717; No contact</span>';
    // Expanded detail
    let detailContent='';
    if(isOpen) {{
      if(l.ca) {{
        const cersFlagItems = (l.cf||[]).map(f=>{{
          let desc='';
          if(f==='IIAR9') desc='No IIAR 9 MI language in recent CERS inspection notes — strong sales trigger';
          else if(f.startsWith('Violations:')) desc=`${{f.split(':')[1]}} documented violation(s) in CERS data — warm entry point`;
          else if(f==='EPA2024') desc='Program 3 site with last eval pre-May 2024 — EPA 2024 RMP Rule unaddressed';
          else if(f==='Revalid:OVERDUE') desc='RMP revalidation overdue (eval date + 5yr < today)';
          else if(f==='Revalid:SOON')   desc='RMP revalidation due within 18 months';
          else desc=f;
          return `<div class="flag-item"><span class="flag-dot"></span><span>${{desc}}</span></div>`;
        }}).join('');
        detailContent=`<div class="flags-list">${{cersFlagItems||'<div class="flag-item"><span style="color:var(--muted)">No CERS compliance flags detected for this site.</span></div>'}}</div>`;
      }} else {{
        // Non-CA: show site details
        const addr=[l.city,l.state,l.zip].filter(Boolean).join(', ');
        detailContent=`<div class="flags-list">
          <div class="flag-item"><span class="flag-dot" style="background:var(--muted)"></span><span>${{l.co?`Parent: ${{l.co}} &nbsp;·&nbsp; `:''}}<span style="color:var(--muted);font-size:10px">RMP SITES</span> ${{l.lc}}${{l.ac?` &nbsp;·&nbsp; <span style="color:var(--muted);font-size:10px">ACCIDENTS</span> ${{l.ac}}`:''}}</span></div>
          ${{addr?`<div class="flag-item"><span class="flag-dot" style="background:var(--muted)"></span><span>${{addr}}</span></div>`:''}}
          ${{l.nh?`<div class="flag-item"><span class="flag-dot" style="background:var(--muted)"></span><span>NH3: ${{l.nh.toLocaleString()}} lbs on-site</span></div>`:''}}
          ${{l.ep?`<div class="flag-item"><span class="flag-dot" style="background:var(--muted)"></span><span>EPA ID: ${{l.ep}}</span></div>`:''}}
        </div>`;
      }}
    }}
    const detail=isOpen?`<tr class="detail-row"><td colspan="7"><div class="detail-body">
      ${{detailContent}}
      ${{crmPanelHtml}}
      <div class="action-btns">
        <button class="copy-btn" onclick="event.stopPropagation();copyLead('${{l.k}}',this)">Copy Lead</button>
        <button class="log-btn" onclick="event.stopPropagation();logFormKey=logFormKey==='${{l.k}}'?null:'${{l.k}}';render()">${{logFormKey===l.k?'Log Contact &#x25B2;':'Log Contact &#x25BC;'}}</button>
        ${{!l.ca?`<button class="log-btn" onclick="event.stopPropagation();editFormKey=editFormKey==='${{l.k}}'?null:'${{l.k}}';render()">${{editFormKey===l.k?'Edit Contact &#x25B2;':'Edit Contact &#x25BC;'}}</button>`:''}}
      </div>
      ${{logForm}}
      ${{editForm}}
    </div></td></tr>`:'';
    const locLabel = l.ca ? l.cupa||'CA' : l.st;
    return `<tr class="expandable" data-key="${{l.k}}" onclick="expandedKey=expandedKey==='${{l.k}}'?null:'${{l.k}}';render()">
    <td style="white-space:nowrap"><span class="tier-badge ${{tierClass(l.t)}}">T${{l.t}} ${{l.tl}}</span>${{deltaHtml}}</td>
    <td><div class="fac-name">${{l.n}}<span class="expand-icon${{isOpen?' open':''}}">&rsaquo;</span></div><div class="fac-loc">${{locLabel}}</div><div class="fac-crm"></div></td>
    <td style="font-family:var(--mono);font-size:12px;color:#9ca3af">${{l.st}}</td>
    <td style="font-family:var(--mono);font-size:11px;color:var(--muted)">${{l.tr}}</td>
    <td style="font-family:var(--mono);font-size:12px">${{fmtNH3(l.nh)}}</td>
    <td>${{revalidTag(l.rv)}}</td>
    <td>${{contactCell}}</td>
    </tr>${{detail}}`;
  }}).join('');
  const pag=document.getElementById('pagination'); pag.innerHTML='';
  if(pages>1){{
    const pb=(txt,pg,act)=>{{const b=document.createElement('button');b.className='page-btn'+(act?' active':'');b.textContent=txt;b.onclick=()=>{{page=pg;render();}};pag.appendChild(b);}};
    pb('← Prev',Math.max(1,cp-1),false);
    for(let i=1;i<=Math.min(pages,8);i++) pb(i,i,i===cp);
    const info=document.createElement('span');info.className='page-info';info.textContent=`of ${{pages}}`;pag.appendChild(info);
    pb('Next →',Math.min(pages,cp+1),false);
  }}
  if(Object.keys(CRM).length) _updateCRMBadges();
}}

// ── Filter event listeners ────────────────────────────────────────────────────
document.querySelectorAll('.filter-btn[data-tf]').forEach(btn=>{{
  btn.addEventListener('click',()=>{{
    document.querySelectorAll('.filter-btn[data-tf]').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active'); terrFilter=btn.dataset.tf; page=1; render();
  }});
}});
document.querySelectorAll('.filter-btn[data-tier]').forEach(btn=>{{
  btn.addEventListener('click',()=>{{
    document.querySelectorAll('.filter-btn[data-tier]').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active'); tierFilter=btn.dataset.tier; page=1; render();
  }});
}});
document.getElementById('state-select').addEventListener('change',e=>{{stateFilter=e.target.value;page=1;render();}});
document.getElementById('search').addEventListener('input',e=>{{search=e.target.value.toLowerCase();page=1;render();}});
document.querySelectorAll('th[data-col]').forEach(th=>{{
  th.addEventListener('click',()=>{{
    const col=th.dataset.col;
    if(sortCol===col) sortAsc=!sortAsc; else{{sortCol=col;sortAsc=col==='t'?true:false;}}
    document.querySelectorAll('th').forEach(t=>t.classList.remove('sort-active'));
    th.classList.add('sort-active');
    th.textContent=th.textContent.replace(/[↕↑↓]/,'')+(sortAsc?' ↑':' ↓');
    render();
  }});
}});

// ── Changes panel ─────────────────────────────────────────────────────────────
if (!IS_BASELINE) {{
  document.getElementById('changes-section').style.display = '';
  function renderChangeList(items, containerId, countId, type) {{
    const el = document.getElementById(containerId);
    const ct = document.getElementById(countId);
    if (ct) ct.textContent = items.length + ' sites';
    if (!items.length) {{
      el.innerHTML = '<div style="color:var(--muted);font-size:12px;padding:8px 0">None this week</div>';
      return;
    }}
    el.innerHTML = items.map(r => {{
      let badge = '';
      const tier = r.current_tier ?? r.prev_tier;
      const tierLbl = r.tier_label || ('T'+tier);
      if (type === 'up')   badge = `<span class="delta-up">&#x25B2;T${{r.delta}}</span>`;
      if (type === 'down') badge = `<span class="delta-down">&#x25BC;T${{Math.abs(r.delta)}}</span>`;
      if (type === 'new')  badge = `<span class="delta-new">NEW</span>`;
      return `<div class="change-item">
        <div class="ci-top"><span class="tier-badge ${{tierClass(tier)}}">${{tierLbl}}</span>${{badge}}<span class="ci-name">${{r.facility_name}}</span></div>
        <div class="ci-meta">${{r.state||''}} ${{r.territory||''}}</div>
        ${{r.reason ? `<div class="ci-reason">${{r.reason}}</div>` : ''}}
      </div>`;
    }}).join('');
  }}
  renderChangeList(MOVED_UP,   'changes-up',   'up-count',   'up');
  renderChangeList(MOVED_DOWN, 'changes-down', 'down-count', 'down');
  renderChangeList(NEW_SITES,  'changes-new',  'new-count',  'new');
}}

try{{const sv=JSON.parse(localStorage.getItem(LOCAL_KEY)||'{{}}');Object.keys(sv).forEach(k=>{{if(!CRM[k])CRM[k]=sv[k];}});}}catch(e){{}}
render();
</script>
</body>
</html>"""

    with open(OUTPUT_DIR / "dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
