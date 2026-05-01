from collections import deque
import sqlite3
from config import DB_NAME
from datetime import datetime, timedelta

FALLBACK_LIGHT = 40.0
FALLBACK_HEAVY = 70.0


class Analyzer:
    def __init__(self):
        self.window = deque(maxlen=7)

    def load_7_days(self):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        c.execute("""
            SELECT date, avg_cpu, avg_ram, label
            FROM daily_stats
            ORDER BY date DESC LIMIT 7
        """)
        rows = c.fetchall()[::-1]   # oldest -> newest
        conn.close()

        self.window.clear()
        db_map = {r[0]: (r[1], r[2], r[3]) for r in rows}
        today  = datetime.now().date()

        for offset in range(6, -1, -1):
            d  = today - timedelta(days=offset)
            ds = str(d)
            if ds in db_map:
                cpu, ram, label = db_map[ds]
            else:
                cpu, ram, label = 0.0, 0.0, "light"
            self.window.append((ds, cpu, ram, label))

    def compute_zones(self):
        heavy_cpu, light_cpu = [], []
        heavy_ram, light_ram = [], []

        for _, cpu, ram, label in self.window:
            if label == "heavy":
                heavy_cpu.append(cpu)
                heavy_ram.append(ram)
            else:
                light_cpu.append(cpu)
                light_ram.append(ram)

        def avg(lst, fallback):
            return round(sum(lst) / len(lst), 2) if lst else fallback

        heavy_cpu_avg = avg(heavy_cpu, FALLBACK_HEAVY)
        light_cpu_avg = avg(light_cpu, FALLBACK_LIGHT)
        heavy_ram_avg = avg(heavy_ram, FALLBACK_HEAVY)
        light_ram_avg = avg(light_ram, FALLBACK_LIGHT)

        # GUARD: If light_avg >= heavy_avg (happens when all days share the
        # same label, or on a fresh install with only fallbacks), force a
        # sensible gap so the warning zone is never inverted or zero-width.
        if light_cpu_avg >= heavy_cpu_avg:
            light_cpu_avg = max(0.0, round(heavy_cpu_avg - 15, 2))

        if light_ram_avg >= heavy_ram_avg:
            light_ram_avg = max(0.0, round(heavy_ram_avg - 15, 2))

        return {
            "light_cpu":    light_cpu_avg,
            "heavy_cpu":    heavy_cpu_avg,
            "critical_cpu": round(heavy_cpu_avg + 0.5 * (100 - heavy_cpu_avg), 2),
            "light_ram":    light_ram_avg,
            "heavy_ram":    heavy_ram_avg,
            "critical_ram": round(heavy_ram_avg + 0.5 * (100 - heavy_ram_avg), 2),
        }

    def detect_anomaly(self, readings):
        """
        Alert fires only when ALL 3 consecutive readings are in the same zone.

        IMPORTANT: Only Critical alerts mark the day as heavy.
                   Warning alerts fire a toast but do NOT mark the day heavy.

        Returns list of tuples: [(alert_message, is_critical), ...]
        """
        if len(readings) < 3:
            return None

        zones  = self.compute_zones()
        alerts = []

        cpu_vals = [r["cpu"] for r in readings]
        ram_vals = [r["ram"] for r in readings]

        # CPU
        if all(v > zones["critical_cpu"] for v in cpu_vals):
            alerts.append((f"CPU Critical (>{zones['critical_cpu']}%)", True))
        elif all(zones["light_cpu"] <= v <= zones["heavy_cpu"] for v in cpu_vals):
            alerts.append((f"CPU Warning ({zones['light_cpu']}–{zones['heavy_cpu']}%)", False))

        # RAM
        if all(v > zones["critical_ram"] for v in ram_vals):
            alerts.append((f"RAM Critical (>{zones['critical_ram']}%)", True))
        elif all(zones["light_ram"] <= v <= zones["heavy_ram"] for v in ram_vals):
            alerts.append((f"RAM Warning ({zones['light_ram']}–{zones['heavy_ram']}%)", False))

        return alerts if alerts else None
