# WRN — System Resource Monitor

> A lightweight, intelligent system monitor with adaptive anomaly detection, a 7-day sliding window analysis engine, and a real-time terminal-style dashboard.

---

## What It Does

WRN continuously tracks your CPU, RAM, and disk usage and learns what "normal" looks like for your specific machine. Instead of using hardcoded alert thresholds, it builds a dynamic profile from the last 7 days of usage and alerts you only when something genuinely unusual is happening — not on every spike.

---

## Features

- **5-second live sampling** of CPU, RAM, and disk
- **7-day sliding window** — daily averages stored and analyzed over a rolling week
- **Adaptive zone thresholds** — Normal / Warning / Critical boundaries derived from your actual usage history, not fixed numbers
- **Smart anomaly detection** — alerts only when 3 consecutive readings are all in the same zone (prevents false alarms from single spikes)
- **Heavy / Light day classification** — driven by your responses to alerts, not hardcoded rules
- **Disk rate-of-change monitoring** — catches slow creep and sudden fills
- **Real-time dashboard** — terminal-style UI with live charts, zone badges, and 7-day history cards
- **Manual label override** — click any day card to flip it between Heavy and Light
- **Resilient data pipeline** — startup flush recovers missed days, every-5-second flush means force-closing the terminal loses at most 5 seconds of data

---

## How the Zone Logic Works

Zones are computed dynamically from your 7-day window:

```
light_avg  = average of all "light" days in the window
heavy_avg  = average of all "heavy" days in the window

Zone boundaries:
  Normal   →  cpu < light_avg
  Warning  →  light_avg ≤ cpu ≤ heavy_avg
  Critical →  cpu > heavy_avg + 0.5 × (100 - heavy_avg)
```

The Critical threshold sits halfway between `heavy_avg` and 100% — so it scales proportionally with your actual usage patterns. If your heavy days average 72%, Critical fires above 86%. If they average 90%, Critical fires above 95%.

---

## How Heavy / Light Days Work

| Situation | Day Label |
|-----------|-----------|
| No anomaly detected | Light |
| Critical alert → user clicks **Resolve** | Light |
| Critical alert → user clicks **Ignore** | Heavy |
| Critical alert → no action taken | Heavy |
| Warning alert (any response) | Light (warnings don't affect label) |

---

## Project Structure

```
WRN/
├── main.py          # Sampling loop, daily flush, anomaly detection
├── app.py           # Flask server, API endpoints, dashboard route
├── analyzer.py      # Sliding window, zone computation, anomaly logic
├── collector.py     # psutil data collection
├── database.py      # SQLite helpers, all DB read/write functions
├── config.py        # INTERVAL and DB_NAME constants
└── templates/
    └── index.html   # Dashboard UI
```

---

## Setup

**Requirements**
```
Python 3.10+
```

**Install dependencies**
```bash
pip install flask psutil
```

**Run**

Open two terminals in the project folder:

```bash
# Terminal 1 — data collection
python main.py

# Terminal 2 — dashboard
python app.py
```

Then open `http://localhost:5000` in your browser.

---

## Data Storage

All data is stored in a local SQLite file — `system_data.db` — created automatically on first run.

| Table | Contents |
|-------|----------|
| `system_stats` | Raw 5-second samples (timestamp, cpu, ram, disk) |
| `daily_stats` | Daily averages with Heavy/Light label (one row per day) |

To inspect your data: download [DB Browser for SQLite](https://sqlitebrowser.org) and open `system_data.db`.

---

## Dashboard

The terminal-style dashboard (built with Chart.js and vanilla JS) shows:

- **Live stat cards** — CPU, RAM, Disk, and system status — color-coded by zone
- **Zone sidebar** — current Normal / Warning / Critical thresholds for CPU and RAM
- **Live charts** — rolling 50-sample graphs for all three metrics
- **7-day window** — one card per day showing daily averages as mini bar graphs, color-coded Heavy (red) / Light (green). Click any card to manually toggle its label
- **Alert toasts** — floating notifications for Warning and Critical events with Resolve / Ignore / Dismiss actions

---

## Alert Behavior

```
3 consecutive readings in Warning zone  →  Warning toast  (day label unchanged)
3 consecutive readings in Critical zone →  Critical toast (day marked Heavy until resolved)

Resolve button  →  day flips to Light
Ignore button   →  day stays Heavy
No action       →  day stays Heavy
```

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python, Flask |
| Data | SQLite via `sqlite3` |
| System metrics | `psutil` |
| Frontend | Vanilla JS, Chart.js |
| Fonts | Share Tech Mono, Rajdhani |
