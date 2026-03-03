# CalARP Lead Intelligence Dashboard
### Auto-updating PSM/CalARP compliance lead generator for California

---

## What this does

Every Monday morning this repo:
1. Reads your latest CERS CalARP inspection export from the `data/` folder
2. Scores all 1,100+ sites on a 1–10 urgency scale using real compliance triggers
3. Rebuilds `output/dashboard.html` — the full interactive dashboard
4. Publishes it automatically to your public GitHub Pages URL

Anyone with your Pages URL always sees the latest data.

---

## One-time setup (~15 minutes)

### 1. Create the GitHub repo
- Go to [github.com/new](https://github.com/new)
- Name it `calarp-dashboard` (or anything you like)
- Set to **Private** if you want (Pages still works)
- Click **Create repository**

### 2. Upload these files
Upload the entire contents of this folder to your new repo.  
The structure should look like:
```
calarp-dashboard/
├── .github/
│   └── workflows/
│       ├── weekly_update.yml
│       └── pages.yml
├── data/
│   └── CERS_Data_CalARP_Sites.xlsx   ← your CERS export goes here
├── output/
│   ├── dashboard.html
│   ├── leads.csv
│   └── leads.json
├── score.py
├── build_html.py
├── requirements.txt
└── README.md
```

### 3. Enable GitHub Pages
- Go to your repo → **Settings** → **Pages**
- Under **Source**, select **GitHub Actions**
- Click Save

### 4. Run it manually first
- Go to **Actions** → **Weekly CalARP Dashboard Update**
- Click **Run workflow** → **Run workflow**
- Watch it run (takes ~30 seconds)
- Then go to **Actions** → **Deploy Dashboard to GitHub Pages** → wait ~1 minute

### 5. Get your public URL
Your dashboard will be live at:
```
https://<your-github-username>.github.io/calarp-dashboard/
```
Share this URL with anyone. It always shows the latest data.

---

## Weekly update process

**Automatic (no action needed):**  
Every Monday at 7 AM UTC the workflow runs automatically using whatever file is in `data/`.

**When you get a fresh CERS export:**
1. Replace the file in `data/` with your new export (keep the same filename, or any `.xlsx`/`.csv`)
2. Commit and push — the workflow will auto-trigger on the next Monday
3. Or: go to Actions → **Weekly CalARP Dashboard Update** → **Run workflow** to update immediately

---

## Urgency scoring rubric

| Factor | Points |
|--------|--------|
| Base score | +2 |
| IIAR 9 gap (no evidence of MI update) | +3 |
| RMP revalidation overdue (last eval ≤2021) | +3 |
| EPA 2024 RMP Rule unaddressed (no eval post May 2024) | +2 |
| Prior violation history | +1 |
| High seismic zone (IIAR 9 §6.6) | +1 |
| Program 3 confirmed | +1 |
| **Maximum** | **10** |

> **Note on IIAR 9 scoring:** The gap is inferred from inspection notes — absence of "IIAR 9" or "RAGAGEP" language does not guarantee non-compliance, but is a strong proxy signal. Confirm on first call.

---

## Running locally

```bash
pip install -r requirements.txt
python score.py --input data/CERS_Data_CalARP_Sites.xlsx
open output/dashboard.html
```

---

## Files

| File | Purpose |
|------|---------|
| `score.py` | Main scoring engine — reads CERS data, scores sites, calls build_html |
| `build_html.py` | Generates the self-contained dashboard HTML |
| `requirements.txt` | Python dependencies (pandas, openpyxl) |
| `.github/workflows/weekly_update.yml` | Runs score.py every Monday |
| `.github/workflows/pages.yml` | Deploys dashboard.html to GitHub Pages |
| `data/` | Drop your CERS export here |
| `output/` | Generated files — dashboard.html, leads.csv, leads.json |
