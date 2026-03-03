"""
build_html.py
-------------
Generates a fully self-contained dashboard HTML file from
the scored lead data produced by score.py.
"""

import json
from pathlib import Path

OUTPUT_DIR = Path("output")


def build_html(stats: dict, leads: list, changes: dict = None):
    generated   = stats["generated"]
    total       = stats["total_sites"]
    hot         = stats["hot_leads"]
    total_evals = stats["total_evals"]
    iiar9       = stats["iiar9_gap"]
    overdue     = stats["revalid_overdue"]
    soon        = stats["revalid_soon"]
    violations  = stats["violation_sites"]
    high_s      = stats["high_seismic"]
    med_s       = stats["med_seismic"]
    low_s       = stats["low_seismic"]
    pre2024     = stats["pre_epa2024"]
    p3          = stats["p3_count"]
    score_dist  = stats["score_dist"]
    cupa_stats  = stats["cupa_stats"]

    # Inline JSON for the table (top 200 leads by score for JS)
    table_leads = []
    for r in leads[:200]:
        table_leads.append({
            "sid": r["site_id"],
            "s": r["urgency_score"],
            "n": r["facility_name"],
            "cupa": r["cupa"],
            "e": r["latest_eval"],
            "y": r["years_since"],
            "v": r["total_violations"],
            "r": ("OVERDUE" if r["revalid_overdue"]
                  else "DUE SOON" if r["revalid_soon"]
                  else "OK"),
            "q": r["seismic"],
            "p": r["recommended_pitch"],
            "pp": r["pain_points"],
            "nt": r["notes"],
        })

    score_dist_js  = json.dumps([[int(k), v] for k, v in sorted(score_dist.items())])
    cupa_stats_js  = json.dumps(cupa_stats)
    table_leads_js = json.dumps(table_leads)

    # Build change map: {site_id -> {delta, direction, reason}}
    change_map = {}
    if changes and not changes.get("baseline"):
        for r in changes.get("moved_up", []):
            change_map[str(r["site_id"])] = {"dir": "up",   "delta": r["delta"],  "reason": r.get("reason","")}
        for r in changes.get("moved_down", []):
            change_map[str(r["site_id"])] = {"dir": "down", "delta": r["delta"],  "reason": r.get("reason","")}
        for r in changes.get("new_sites", []):
            change_map[str(r["site_id"])] = {"dir": "new",  "delta": None, "reason": "New site in this data export"}

    change_map_js  = json.dumps(change_map)
    changes_summary = changes.get("summary", {}) if changes else {}
    changes_prev_date = changes.get("prev_date", None) if changes else None
    is_baseline = (changes is None) or changes.get("baseline", True)

    moved_up_js   = json.dumps(changes.get("moved_up",   [])[:20] if changes else [])
    moved_down_js = json.dumps(changes.get("moved_down", [])[:20] if changes else [])
    new_sites_js  = json.dumps(changes.get("new_sites",  [])[:20] if changes else [])

    # Change summary for header badge
    chg_up    = changes_summary.get("moved_up_count", 0)
    chg_down  = changes_summary.get("moved_down_count", 0)
    chg_new   = changes_summary.get("new_count", 0)
    chg_drop  = changes_summary.get("dropped_count", 0)
    prev_lbl  = f"vs {changes_prev_date}" if changes_prev_date else "baseline run"
    chg_badge = "" if is_baseline else f"""
  <div class="change-badge">
    <span class="cb-item cb-up">&#x25B2; {chg_up} up</span>
    <span class="cb-item cb-down">&#x25BC; {chg_down} down</span>
    <span class="cb-item cb-new">+ {chg_new} new</span>
    <span class="cb-sep">{prev_lbl}</span>
  </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CalARP Lead Intelligence Dashboard — {generated}</title>
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
.pitch-list{{margin-top:16px;padding-top:14px;border-top:1px solid var(--border);}}
.pitch-row{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;}}
.pitch-count{{font-family:var(--mono);font-size:11px;color:var(--muted);}}
.tag{{display:inline-block;padding:2px 7px;border-radius:3px;font-family:var(--mono);font-size:10px;letter-spacing:0.04em;margin:1px;}}
.tag-red{{background:rgba(239,68,68,0.15);color:var(--red);}}
.tag-amber{{background:rgba(245,166,35,0.15);color:var(--amber);}}
.tag-green{{background:rgba(45,212,160,0.15);color:var(--green);}}
.tag-blue{{background:rgba(59,130,246,0.15);color:var(--blue);}}
.tag-gray{{background:rgba(107,114,128,0.18);color:#9ca3af;}}
.hbar-list{{display:flex;flex-direction:column;gap:10px;}}
.hbar-row{{display:grid;grid-template-columns:210px 1fr 80px;align-items:center;gap:12px;}}
.hbar-name{{font-size:12px;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.hbar-track{{background:var(--border);border-radius:2px;height:6px;overflow:hidden;}}
.hbar-fill{{height:100%;border-radius:2px;background:var(--accent);width:0;transition:width 1.1s cubic-bezier(0.4,0,0.2,1);}}
.hbar-meta{{font-family:var(--mono);font-size:11px;color:var(--muted);text-align:right;}}
.trigger-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;}}
.trigger-card{{border:1px solid var(--border);border-radius:6px;padding:18px;}}
.trigger-icon{{font-size:20px;display:block;margin-bottom:8px;}}
.trigger-num{{font-family:var(--display);font-size:36px;line-height:1;letter-spacing:1px;}}
.trigger-label{{font-family:var(--mono);font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:0.1em;margin-top:4px;line-height:1.5;}}
.trigger-sub{{font-size:11px;color:var(--muted);margin-top:4px;}}
.filter-row{{display:flex;gap:8px;margin-bottom:14px;align-items:center;flex-wrap:wrap;}}
.filter-label{{font-family:var(--mono);font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.1em;}}
.filter-btn{{background:var(--border);border:1px solid var(--border2);color:var(--muted);font-family:var(--mono);font-size:11px;padding:5px 12px;border-radius:4px;cursor:pointer;transition:all 0.15s;}}
.filter-btn:hover,.filter-btn.active{{background:rgba(255,77,28,0.15);border-color:rgba(255,77,28,0.4);color:var(--accent);}}
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
.score-badge{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:4px;font-family:var(--display);font-size:16px;}}
.s10{{background:rgba(239,68,68,0.2);color:var(--red);border:1px solid rgba(239,68,68,0.3);}}
.s9{{background:rgba(255,77,28,0.2);color:var(--accent);border:1px solid rgba(255,77,28,0.3);}}
.s8{{background:rgba(245,166,35,0.2);color:var(--amber);border:1px solid rgba(245,166,35,0.3);}}
.s7{{background:rgba(59,130,246,0.2);color:var(--blue);border:1px solid rgba(59,130,246,0.3);}}
.slow{{background:var(--border);color:var(--muted);border:1px solid var(--border2);}}
.fac-name{{font-weight:500;color:var(--text);max-width:200px;}}
.fac-cupa{{font-family:var(--mono);font-size:10px;color:var(--muted);margin-top:2px;}}
.pitch-cell{{font-size:11px;color:var(--muted);max-width:180px;line-height:1.4;}}
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
@media(max-width:1100px){{.kpi-grid{{grid-template-columns:repeat(3,1fr);}}.charts-row{{grid-template-columns:1fr;}}.trigger-grid{{grid-template-columns:repeat(2,1fr);}}.hbar-row{{grid-template-columns:160px 1fr 70px;}}}}
@media(max-width:700px){{header,main{{padding-left:20px;padding-right:20px;}}.kpi-grid{{grid-template-columns:repeat(2,1fr);}}.trigger-grid{{grid-template-columns:1fr;}}h1{{font-size:36px;}}}}
.changes-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}}
.change-item{{padding:10px 0;border-bottom:1px solid var(--border);}}
.change-item:last-child{{border-bottom:none;}}
.ci-top{{display:flex;align-items:center;gap:8px;margin-bottom:3px;}}
.ci-name{{font-size:12px;font-weight:500;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.ci-meta{{font-family:var(--mono);font-size:10px;color:var(--muted);padding-left:36px;}}
.ci-reason{{font-size:11px;color:var(--muted);padding-left:36px;margin-top:2px;line-height:1.4;}}
@media(max-width:1100px){{.changes-grid{{grid-template-columns:1fr;}}}}
.cupa-select{{background:var(--border);border:1px solid var(--border2);color:var(--text);font-family:var(--mono);font-size:11px;padding:5px 10px;border-radius:4px;outline:none;cursor:pointer;transition:border-color 0.15s;}}
.cupa-select:focus{{border-color:rgba(255,77,28,0.4);}}
.cupa-select option{{background:var(--surface);}}
tr.expandable{{cursor:pointer;}}
.expand-icon{{font-family:var(--mono);font-size:12px;color:var(--muted);margin-left:5px;display:inline-block;transition:transform 0.15s;line-height:1;}}
.expand-icon.open{{transform:rotate(90deg);}}
.detail-row td{{padding:0;border-bottom:1px solid var(--border);background:rgba(255,255,255,0.01);}}
.detail-body{{padding:14px 16px 14px 52px;display:flex;gap:24px;align-items:flex-start;}}
.pain-list{{flex:1;display:flex;flex-direction:column;gap:7px;}}
.pain-item{{font-size:11px;color:var(--muted);display:flex;gap:8px;align-items:flex-start;line-height:1.5;}}
.pain-dot{{width:5px;height:5px;border-radius:50%;background:var(--accent);flex-shrink:0;margin-top:5px;}}
.copy-btn{{background:var(--border);border:1px solid var(--border2);color:var(--muted);font-family:var(--mono);font-size:11px;padding:6px 14px;border-radius:4px;cursor:pointer;transition:all 0.15s;white-space:nowrap;align-self:flex-start;}}
.copy-btn:hover{{background:rgba(255,77,28,0.15);border-color:rgba(255,77,28,0.4);color:var(--accent);}}
.copy-btn.copied{{background:rgba(45,212,160,0.15);border-color:rgba(45,212,160,0.4);color:#2dd4a0;}}
.notes-list{{margin-top:10px;padding-top:10px;border-top:1px solid var(--border);display:flex;flex-direction:column;gap:5px;}}
.note-item{{font-size:11px;color:var(--muted);display:flex;gap:8px;align-items:flex-start;line-height:1.5;}}
.note-dot{{width:5px;height:5px;border-radius:50%;background:var(--muted);flex-shrink:0;margin-top:5px;}}
</style>
</head>
<body>
<header>
  <div class="live-badge"><span class="live-dot"></span>UPDATED {generated} &nbsp;·&nbsp; AUTO-GENERATED FROM CERS EXPORT</div>
  <h1>CAL<span>ARP</span> LEAD DASHBOARD</h1>
  <div class="header-sub">CALIFORNIA STATEWIDE &nbsp;·&nbsp; AMMONIA REFRIGERATION &nbsp;·&nbsp; PSM/CALARP COMPLIANCE INTELLIGENCE</div>
  <div class="header-meta">
    <div class="meta-item"><span class="meta-label">Total Sites</span><span class="meta-value">{total:,}</span></div>
    <div class="meta-item"><span class="meta-label">Hot Leads (8–10)</span><span class="meta-value meta-hot">{hot:,}</span></div>
    <div class="meta-item"><span class="meta-label">Inspection Records</span><span class="meta-value">{total_evals:,}</span></div>
    <div class="meta-item"><span class="meta-label">Last Updated</span><span class="meta-value" style="font-size:20px;padding-top:6px">{generated}</span></div>
  </div>
</header>
<main>
  <div id="changes-section" style="display:none">
    <div class="section-label"><span>WEEK-OVER-WEEK CHANGES</span></div>
    <div class="changes-grid">
      <div class="card"><div class="card-title">Score Increases <small id="up-count"></small></div><div id="changes-up"></div></div>
      <div class="card"><div class="card-title">Score Decreases <small id="down-count"></small></div><div id="changes-down"></div></div>
      <div class="card"><div class="card-title">New Sites <small id="new-count"></small></div><div id="changes-new"></div></div>
    </div>
  </div>
  <div>
    <div class="section-label"><span>KEY COMPLIANCE TRIGGERS</span></div>
    <div class="kpi-grid">
      <div class="kpi-card" style="--kpi-color:#ef4444"><div class="kpi-num">{iiar9:,}</div><div class="kpi-label">IIAR 9 Gap Detected</div><div class="kpi-sub">No MI update evidence — Jan 2026 deadline passed</div></div>
      <div class="kpi-card" style="--kpi-color:#ff4d1c"><div class="kpi-num">{overdue:,}</div><div class="kpi-label">RMP Revalidation Overdue</div><div class="kpi-sub">Last eval ≤2021 · Call today</div></div>
      <div class="kpi-card" style="--kpi-color:#f5a623"><div class="kpi-num">{soon:,}</div><div class="kpi-label">Revalidation Due Soon</div><div class="kpi-sub">Due within 18 months · Pipeline now</div></div>
      <div class="kpi-card" style="--kpi-color:#a855f7"><div class="kpi-num">{violations:,}</div><div class="kpi-label">Prior Violation History</div><div class="kpi-sub">Documented gaps · Warm entry</div></div>
      <div class="kpi-card" style="--kpi-color:#3b82f6"><div class="kpi-num">{high_s:,}</div><div class="kpi-label">High Seismic Zone Sites</div><div class="kpi-sub">IIAR 9 §6.6 bracing required</div></div>
    </div>
  </div>
  <div class="charts-row">
    <div class="card">
      <div class="card-title">Urgency Score Distribution <small>n={total:,} sites</small></div>
      <div class="histogram" id="histogram"></div>
    </div>
    <div class="card">
      <div class="card-title">Seismic Exposure</div>
      <div class="donut-wrap" id="donut-wrap"></div>
    </div>
    <div class="card">
      <div class="card-title">RMP Revalidation</div>
      <div class="timeline">
        <div class="tl-row"><div class="tl-dot" style="background:#ef4444"></div><div class="tl-label">Overdue now</div><div><div class="tl-val" style="color:#ef4444">{overdue:,}</div><div class="tl-sub">≤2021 · Call today</div></div></div>
        <div class="tl-row"><div class="tl-dot" style="background:#f5a623"></div><div class="tl-label">Due soon</div><div><div class="tl-val" style="color:#f5a623">{soon:,}</div><div class="tl-sub">Due within 18 months · Plan now</div></div></div>
        <div class="tl-row"><div class="tl-dot" style="background:#2dd4a0"></div><div class="tl-label">Within window</div><div><div class="tl-val" style="color:#2dd4a0">{total - overdue - soon:,}</div><div class="tl-sub">2023+ · Still need IIAR 9</div></div></div>
      </div>
      <div class="pitch-list">
        <div class="section-label" style="margin-bottom:10px"><span>PITCH MIX</span></div>
        <div id="pitch-mix"></div>
      </div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">CUPA Jurisdictions <small>site count · avg urgency score</small></div>
    <div class="hbar-list" id="cupa-bars"></div>
  </div>
  <div>
    <div class="section-label"><span>REGULATORY TRIGGER BREAKDOWN</span></div>
    <div class="trigger-grid">
      <div class="trigger-card" style="background:rgba(239,68,68,0.04)"><span class="trigger-icon">⚙️</span><div class="trigger-num" style="color:#ef4444">{iiar9:,}</div><div class="trigger-label">IIAR 9 Mechanical Integrity Gap</div><div class="trigger-sub">{round(iiar9/total*100,1)}% of all CalARP sites — Jan 2026 deadline has passed</div></div>
      <div class="trigger-card" style="background:rgba(255,77,28,0.04)"><span class="trigger-icon">📅</span><div class="trigger-num" style="color:#ff4d1c">{overdue+soon:,}</div><div class="trigger-label">RMP Revalidation Overdue or Imminent</div><div class="trigger-sub">{overdue:,} overdue · {soon:,} due soon · pitch both now</div></div>
      <div class="trigger-card" style="background:rgba(245,166,35,0.04)"><span class="trigger-icon">📋</span><div class="trigger-num" style="color:#f5a623">{pre2024:,}</div><div class="trigger-label">EPA 2024 RMP Rule Unaddressed</div><div class="trigger-sub">No eval post May 2024 — third-party audit + STAA required</div></div>
      <div class="trigger-card" style="background:rgba(168,85,247,0.04)"><span class="trigger-icon">⚠️</span><div class="trigger-num" style="color:#a855f7">{violations:,}</div><div class="trigger-label">Prior Violation on Record</div><div class="trigger-sub">Documented gaps = warm sales entry point</div></div>
      <div class="trigger-card" style="background:rgba(59,130,246,0.04)"><span class="trigger-icon">🌐</span><div class="trigger-num" style="color:#3b82f6">{high_s:,}</div><div class="trigger-label">High Seismic Zone — IIAR 9 §6.6</div><div class="trigger-sub">Bay Area + LA/Ventura — seismic bracing audit upsell</div></div>
      <div class="trigger-card" style="background:rgba(45,212,160,0.04)"><span class="trigger-icon">🏭</span><div class="trigger-num" style="color:#2dd4a0">{p3:,}</div><div class="trigger-label">Program 3 Sites Confirmed</div><div class="trigger-sub">Highest burden — STAA + enhanced audits mandatory</div></div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Lead List <small>top 200 by urgency score · full dataset in output/leads.csv</small></div>
    <div class="filter-row">
      <span class="filter-label">Score:</span>
      <button class="filter-btn active" data-f="all">ALL</button>
      <button class="filter-btn" data-f="hot">HOT 8+</button>
      <button class="filter-btn" data-f="7">7</button>
      <button class="filter-btn" data-f="6">6</button>
      <select class="cupa-select" id="cupa-select"><option value="">ALL CUPAS</option></select>
      <input class="search-box" id="search" type="text" placeholder="Search facility…">
    </div>
    <div class="table-info" id="table-info"></div>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th data-col="s">SCORE ↕</th>
          <th>FACILITY / CUPA</th>
          <th data-col="e">LAST EVAL ↕</th>
          <th data-col="y">YRS ↕</th>
          <th data-col="v">VIOL ↕</th>
          <th>REVALIDATION</th>
          <th>SEISMIC</th>
          <th>PITCH</th>
        </tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
    <div class="pagination" id="pagination"></div>
  </div>
</main>
<script>
const SCORE_DIST  = {score_dist_js};
const CUPA_STATS  = {cupa_stats_js};
const LEADS       = {table_leads_js};
const SCORE_COLORS = {{3:'#6366f1',4:'#6366f1',5:'#8b5cf6',6:'#a855f7',7:'#3b82f6',8:'#f5a623',9:'#ff4d1c',10:'#ef4444'}};
const CHANGE_MAP   = {change_map_js};
const MOVED_UP     = {moved_up_js};
const MOVED_DOWN   = {moved_down_js};
const NEW_SITES    = {new_sites_js};
const IS_BASELINE  = {'true' if is_baseline else 'false'};
const PREV_DATE    = "{changes_prev_date or ''}";

// Histogram
const maxBar = Math.max(...SCORE_DIST.map(d=>d[1]));
const hist   = document.getElementById('histogram');
SCORE_DIST.forEach(([score,count])=>{{
  const pct = (count/maxBar)*100;
  const col = document.createElement('div');
  col.className = 'bar-col';
  col.innerHTML = `<div class="bar" style="height:${{pct}}%;background:${{SCORE_COLORS[score]}}" title="Score ${{score}}: ${{count}} sites"><span class="bar-count">${{count}}</span></div><span class="bar-label">${{score}}</span>`;
  hist.appendChild(col);
}});

// Donut
const total_s={total}, high_s={high_s}, med_s={med_s}, low_s={low_s};
const R=46,cx=60,cy=60,circ=2*Math.PI*R;
const hw=(high_s/total_s)*circ, mw=(med_s/total_s)*circ, lw=(low_s/total_s)*circ;
document.getElementById('donut-wrap').innerHTML=`
  <svg viewBox="0 0 120 120" width="120" height="120">
    <circle cx="${{cx}}" cy="${{cy}}" r="${{R}}" fill="none" stroke="#1e1e2e" stroke-width="18"/>
    <circle cx="${{cx}}" cy="${{cy}}" r="${{R}}" fill="none" stroke="#ef4444" stroke-width="18"
      stroke-dasharray="${{hw}} ${{circ-hw}}" stroke-dashoffset="${{circ/4}}" />
    <circle cx="${{cx}}" cy="${{cy}}" r="${{R}}" fill="none" stroke="#f5a623" stroke-width="18"
      stroke-dasharray="${{mw}} ${{circ-mw}}" stroke-dashoffset="${{circ/4-hw}}" />
    <circle cx="${{cx}}" cy="${{cy}}" r="${{R}}" fill="none" stroke="#2dd4a0" stroke-width="18"
      stroke-dasharray="${{lw}} ${{circ-lw}}" stroke-dashoffset="${{circ/4-hw-mw}}" />
    <text x="${{cx}}" y="56" text-anchor="middle" font-family="Bebas Neue,sans-serif" font-size="22" fill="#e8e8f0">${{high_s}}</text>
    <text x="${{cx}}" y="67" text-anchor="middle" font-family="DM Mono,monospace" font-size="8" fill="#6b6b85">HIGH RISK</text>
  </svg>
  <div class="donut-legend">
    <div class="legend-item"><div class="legend-dot" style="background:#ef4444"></div><span class="legend-label">High Seismic</span><span class="legend-val">${{high_s}} <span style="color:#6b6b85;font-size:10px">${{Math.round(high_s/total_s*100)}}%</span></span></div>
    <div class="legend-item"><div class="legend-dot" style="background:#f5a623"></div><span class="legend-label">Medium Seismic</span><span class="legend-val">${{med_s}} <span style="color:#6b6b85;font-size:10px">${{Math.round(med_s/total_s*100)}}%</span></span></div>
    <div class="legend-item"><div class="legend-dot" style="background:#2dd4a0"></div><span class="legend-label">Low Seismic</span><span class="legend-val">${{low_s}} <span style="color:#6b6b85;font-size:10px">${{Math.round(low_s/total_s*100)}}%</span></span></div>
  </div>`;

// Pitch mix
const pitchCounts = {{}};
LEADS.forEach(l=>{{ pitchCounts[l.p]=(pitchCounts[l.p]||0)+1; }});
const pm = document.getElementById('pitch-mix');
const pitchColors = {{'IIAR 9 MI Gap Analysis + RMP Revalidation Package':'tag-red','IIAR 9 MI Program Development':'tag-amber','RMP 5-Year Revalidation':'tag-blue','EPA 2024 RMP Rule Compliance Review':'tag-gray'}};
Object.entries(pitchCounts).sort((a,b)=>b[1]-a[1]).forEach(([k,v])=>{{
  const cls = pitchColors[k]||'tag-gray';
  pm.innerHTML += `<div class="pitch-row"><span class="tag ${{cls}}">${{k}}</span><span class="pitch-count">${{v}}</span></div>`;
}});

// CUPA bars
const maxC = CUPA_STATS[0]?.count||1;
const cupaEl = document.getElementById('cupa-bars');
CUPA_STATS.forEach((c,i)=>{{
  const pct=(c.count/maxC)*100;
  const ac=c.avg>=8?'#ff4d1c':c.avg>=7.5?'#f5a623':'#3b82f6';
  const row=document.createElement('div'); row.className='hbar-row';
  row.innerHTML=`<span class="hbar-name" title="${{c.name}}">${{c.name}}</span><div class="hbar-track"><div class="hbar-fill" id="bar-${{i}}"></div></div><span class="hbar-meta">${{c.count}} <span style="color:${{ac}};font-size:10px">avg ${{c.avg}}</span></span>`;
  cupaEl.appendChild(row);
}});
setTimeout(()=>{{ CUPA_STATS.forEach((_,i)=>{{ setTimeout(()=>{{ const b=document.getElementById('bar-'+i); if(b)b.style.width=(CUPA_STATS[i].count/maxC*100)+'%'; }},i*55); }}); }},300);

// Table
let filter='all', cupaFilter='', search='', page=1, sortCol='s', sortAsc=false, expandedSid=null;
const PAGE=10;
function scoreClass(s){{return s===10?'s10':s===9?'s9':s===8?'s8':s===7?'s7':'slow';}}
function revalidTag(r){{return r==='OVERDUE'?'<span class="tag tag-red">OVERDUE</span>':r==='DUE SOON'?'<span class="tag tag-amber">DUE SOON</span>':'<span class="tag tag-green">OK</span>';}}
function seismicTag(q){{return q==='High'?'<span class="tag tag-red">High</span>':q==='Medium'?'<span class="tag tag-amber">Medium</span>':'<span class="tag tag-green">Low</span>';}}

// Populate CUPA dropdown
const cupaSelect=document.getElementById('cupa-select');
[...new Set(LEADS.map(l=>l.cupa))].sort().forEach(c=>{{
  const o=document.createElement('option'); o.value=c; o.textContent=c; cupaSelect.appendChild(o);
}});
cupaSelect.addEventListener('change',e=>{{cupaFilter=e.target.value;page=1;render();}});

function getFiltered(){{
  return LEADS.filter(l=>{{
    const so=filter==='all'?true:filter==='hot'?l.s>=8:l.s===parseInt(filter);
    const sc=cupaFilter?l.cupa===cupaFilter:true;
    const se=l.n.toLowerCase().includes(search);
    return so&&sc&&se;
  }}).sort((a,b)=>{{
    let va=a[sortCol],vb=b[sortCol];
    if(typeof va==='string') return sortAsc?va.localeCompare(vb):vb.localeCompare(va);
    return sortAsc?va-vb:vb-va;
  }});
}}

function copyLead(sid, btn) {{
  const l=LEADS.find(x=>x.sid===sid); if(!l) return;
  const lines=[
    `FACILITY: ${{l.n}}`, `CUPA: ${{l.cupa}}`, `URGENCY: ${{l.s}}/10`,
    `LAST EVAL: ${{l.e}} (${{l.y}}y ago)`, `VIOLATIONS: ${{l.v}}`,
    `REVALIDATION: ${{l.r}}`, `SEISMIC: ${{l.q}}`, `PITCH: ${{l.p}}`,
    '', 'PAIN POINTS:', ...(l.pp||[]).map(pt=>`• ${{pt}}`),
    ...((l.nt&&l.nt.length)?['', 'NOTES:', ...l.nt.map(n=>`• ${{n}}`)]: []),
  ];
  navigator.clipboard.writeText(lines.join('\\n')).then(()=>{{
    btn.textContent='Copied!'; btn.classList.add('copied');
    setTimeout(()=>{{btn.textContent='Copy Lead'; btn.classList.remove('copied');}}, 1800);
  }});
}}

function render(){{
  const data=getFiltered(); const pages=Math.ceil(data.length/PAGE)||1;
  const cp=Math.min(page,pages); const slice=data.slice((cp-1)*PAGE,cp*PAGE);
  document.getElementById('table-info').textContent=`${{data.length}} results · page ${{cp}} of ${{pages}}`;
  document.getElementById('tbody').innerHTML=slice.map(l=>{{
    const chg=CHANGE_MAP[String(l.sid||'')];
    let deltaHtml='';
    if(chg&&chg.dir==='up')   deltaHtml=`<span class="delta-up" title="${{chg.reason}}">&#x25B2;+${{chg.delta}}</span>`;
    if(chg&&chg.dir==='down') deltaHtml=`<span class="delta-down" title="${{chg.reason}}">&#x25BC;${{chg.delta}}</span>`;
    if(chg&&chg.dir==='new')  deltaHtml=`<span class="delta-new">NEW</span>`;
    const isOpen=expandedSid===l.sid;
    const notesHtml=(l.nt&&l.nt.length)?`<div class="notes-list">${{l.nt.map(n=>`<div class="note-item"><span class="note-dot"></span><span>${{n}}</span></div>`).join('')}}</div>`:'';
    const detail=isOpen?`<tr class="detail-row"><td colspan="8"><div class="detail-body">
      <div class="pain-list">${{(l.pp||[]).map(pt=>`<div class="pain-item"><span class="pain-dot"></span><span>${{pt}}</span></div>`).join('')}}${{notesHtml}}</div>
      <button class="copy-btn" onclick="event.stopPropagation();copyLead(${{l.sid}},this)">Copy Lead</button>
    </div></td></tr>`:'';
    return `<tr class="expandable" onclick="expandedSid=expandedSid===${{l.sid}}?null:${{l.sid}};render()">
    <td style="white-space:nowrap"><span class="score-badge ${{scoreClass(l.s)}}">${{l.s}}</span>${{deltaHtml}}</td>
    <td><div class="fac-name">${{l.n}}<span class="expand-icon${{isOpen?' open':''}}">&rsaquo;</span></div><div class="fac-cupa">${{l.cupa}}</div></td>
    <td style="font-family:var(--mono);font-size:12px;color:#9ca3af;white-space:nowrap">${{l.e}}</td>
    <td style="font-family:var(--mono);font-size:12px;color:${{l.y>5?'#ef4444':l.y>3?'#f5a623':'#9ca3af'}}">${{l.y}}y</td>
    <td>${{l.v>0?`<span class="tag tag-red">${{l.v}}</span>`:'<span class="tag tag-gray">0</span>'}}</td>
    <td>${{revalidTag(l.r)}}</td><td>${{seismicTag(l.q)}}</td>
    <td class="pitch-cell">${{l.p}}</td></tr>${{detail}}`;
  }}).join('');
  const pag=document.getElementById('pagination'); pag.innerHTML='';
  if(pages>1){{
    const pb=(txt,pg,act)=>{{const b=document.createElement('button');b.className='page-btn'+(act?' active':'');b.textContent=txt;b.onclick=()=>{{page=pg;render();}};pag.appendChild(b);}};
    pb('← Prev',Math.max(1,cp-1),false);
    for(let i=1;i<=Math.min(pages,8);i++) pb(i,i,i===cp);
    const info=document.createElement('span');info.className='page-info';info.textContent=`of ${{pages}}`;pag.appendChild(info);
    pb('Next →',Math.min(pages,cp+1),false);
  }}
}}
document.querySelectorAll('.filter-btn').forEach(btn=>{{
  btn.addEventListener('click',()=>{{
    document.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active'); filter=btn.dataset.f; page=1; render();
  }});
}});
document.getElementById('search').addEventListener('input',e=>{{search=e.target.value.toLowerCase();page=1;render();}});
document.querySelectorAll('th[data-col]').forEach(th=>{{
  th.addEventListener('click',()=>{{
    const col=th.dataset.col;
    if(sortCol===col) sortAsc=!sortAsc; else{{sortCol=col;sortAsc=false;}}
    document.querySelectorAll('th').forEach(t=>t.classList.remove('sort-active'));
    th.classList.add('sort-active');
    th.textContent=th.textContent.replace(/[↕↑↓]/,'')+(sortAsc?' ↑':' ↓');
    render();
  }});
}});
// ── CHANGES PANEL ────────────────────────────────────────────────────────────
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
      if (type === 'up')   badge = `<span class="delta-up">&#x25B2;+${{r.delta}}</span>`;
      if (type === 'down') badge = `<span class="delta-down">&#x25BC;${{r.delta}}</span>`;
      if (type === 'new')  badge = `<span class="delta-new">NEW</span>`;
      const score = r.current_score ?? r.prev_score;
      return `<div class="change-item">
        <div class="ci-top"><span class="score-badge ${{scoreClass(score)}}">${{score}}</span>${{badge}}<span class="ci-name">${{r.facility_name}}</span></div>
        <div class="ci-meta">${{r.cupa}}</div>
        ${{r.reason ? `<div class="ci-reason">${{r.reason}}</div>` : ''}}
      </div>`;
    }}).join('');
  }}
  renderChangeList(MOVED_UP,   'changes-up',   'up-count',   'up');
  renderChangeList(MOVED_DOWN, 'changes-down', 'down-count', 'down');
  renderChangeList(NEW_SITES,  'changes-new',  'new-count',  'new');
}}

render();
</script>
</body>
</html>"""

    with open(OUTPUT_DIR / "dashboard.html", "w", encoding="utf-8") as f:
        f.write(html)
