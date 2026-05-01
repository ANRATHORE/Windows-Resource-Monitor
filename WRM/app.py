from flask import Flask, render_template, jsonify, request
import sqlite3
import psutil
import sys

from config import DB_NAME
from analyzer import Analyzer
from database import update_today_label

app = Flask(__name__)

# Custom Jinja filter so day cards can show "MON", "TUE" etc from a date string
from datetime import datetime as _dt
app.jinja_env.filters['strftime'] = lambda s, fmt: _dt.strptime(s, '%Y-%m-%d').strftime(fmt)

DISK_PATH = "C:\\" if sys.platform == "win32" else "/"


@app.route("/")
def dashboard():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT timestamp, cpu, ram, disk
        FROM system_stats
        ORDER BY timestamp DESC LIMIT 50
    """)
    data = c.fetchall()[::-1]
    conn.close()

    live = {
        "cpu":  psutil.cpu_percent(interval=1),
        "ram":  psutil.virtual_memory().percent,
        "disk": psutil.disk_usage(DISK_PATH).percent,
    }

    analyzer = Analyzer()
    analyzer.load_7_days()
    zones  = analyzer.compute_zones()
    window = list(analyzer.window)

    recent  = [{"cpu": d[1], "ram": d[2]} for d in data[-3:]] if len(data) >= 3 else []
    anomaly = analyzer.detect_anomaly(recent) if len(recent) == 3 else None
    alerts  = anomaly if anomaly else []

    return render_template(
        "index.html",
        data=data,
        live=live,
        zones=zones,
        window=window,
        alerts=alerts,
    )


@app.route("/api/data")
def get_data():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT timestamp, cpu, ram, disk
        FROM system_stats
        ORDER BY timestamp DESC LIMIT 50
    """)
    data = c.fetchall()[::-1]
    conn.close()

    return jsonify(data)


@app.route("/api/anomaly", methods=["POST"])
def anomaly_response():
    """
    Called by Resolve / Ignore buttons on critical alert toasts.
    We use the DB as shared state — main.py reads today's label
    from daily_stats on every cycle, so updating it here is enough.

    Resolve     → label = "light"
    Ignore      → label = "heavy"
    Warning     → no label change (is_critical = False)
    """
    action      = request.json.get("action")
    is_critical = request.json.get("is_critical", False)

    if is_critical:
        label = "light" if action == "resolve" else "heavy"
        update_today_label(label)
        return jsonify({"status": "ok", "label": label})

    return jsonify({"status": "ok", "label": "no_change"})


@app.route("/api/toggle_label", methods=["POST"])
def toggle_label():
    """
    Manual label toggle from clicking a 7-day window card.
    Body: {"date": "2025-01-01", "current_label": "light"}
    """
    date_str      = request.json.get("date")
    current_label = request.json.get("current_label")
    new_label     = "heavy" if current_label == "light" else "light"

    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()
    c.execute("UPDATE daily_stats SET label = ? WHERE date = ?",
              (new_label, date_str))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "new_label": new_label})


if __name__ == "__main__":
    app.run(debug=True)
