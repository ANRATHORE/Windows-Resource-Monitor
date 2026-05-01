import time
import sqlite3                          # FIX 1: was missing entirely
from datetime import datetime, timedelta, date

from collector import collect_data
from database import (init_db, insert_data, insert_daily_avg,
                      get_avg_for_date, get_all_saved_dates,
                      get_distinct_raw_dates)
from analyzer import Analyzer
from config import INTERVAL, DB_NAME   # FIX 4: DB_NAME was never imported


def get_today_label():
    """
    Read today's current label directly from the DB.
    app.py writes to it when user clicks Resolve/Ignore,
    main.py reads it here — DB is the shared state between the two processes.
    Defaults to 'light' if today has no row yet.
    """
    conn = sqlite3.connect(DB_NAME)
    c    = conn.cursor()
    c.execute("SELECT label FROM daily_stats WHERE date = ?", (str(date.today()),))
    row = c.fetchone()
    conn.close()
    return row[0] if row else "light"


def flush_past_days():
    """
    On startup, find any past days in system_stats that were never saved
    to daily_stats (because main.py was closed before midnight).
    Compute their averages from raw rows and save them.
    Also zero-fill any days with no raw data at all (PC was fully off).
    """
    today_str = str(date.today())
    saved     = get_all_saved_dates()
    raw_dates = get_distinct_raw_dates()

    for d in raw_dates:
        if d == today_str:
            continue            # today is handled separately as a live card
        if d in saved:
            continue            # already flushed

        avg_cpu, avg_ram = get_avg_for_date(d)
        # Past days we can't ask the user anymore — default to light
        insert_daily_avg(d, avg_cpu, avg_ram, label="light")
        print(f"[startup flush] {d}  CPU:{avg_cpu:.2f}  RAM:{avg_ram:.2f}")

    # Zero-fill days with no raw data at all (PC was fully off those days)
    if raw_dates:
        earliest  = date.fromisoformat(raw_dates[0])
        yesterday = date.today() - timedelta(days=1)
        cursor    = earliest
        while cursor <= yesterday:
            ds = str(cursor)
            if ds not in saved and ds not in raw_dates:
                insert_daily_avg(ds, 0.0, 0.0, label="light")
                print(f"[startup flush] zero-fill {ds}")
            cursor += timedelta(days=1)


def flush_today(daily_cpu, daily_ram, label="light"):
    """
    Save today's current running average with INSERT OR REPLACE.
    Called every sample cycle so the today card is always live.
    Also called on Ctrl+C for final save.
    """
    if not daily_cpu:
        return
    avg_cpu   = round(sum(daily_cpu) / len(daily_cpu), 2)
    avg_ram   = round(sum(daily_ram) / len(daily_ram), 2)
    today_str = str(date.today())
    insert_daily_avg(today_str, avg_cpu, avg_ram, label=label)


def main():
    init_db()
    flush_past_days()

    analyzer  = Analyzer()
    analyzer.load_7_days()

    recent    = []
    daily_cpu = []
    daily_ram = []

    print("Monitoring started. Press Ctrl+C to stop.")

    try:
        while True:
            data = collect_data()
            print("Live:", data)

            insert_data(data)

            recent.append(data)
            if len(recent) > 3:
                recent.pop(0)

            daily_cpu.append(data["cpu"])
            daily_ram.append(data["ram"])

            # Anomaly check — only Critical alerts mark the day heavy
            if len(recent) == 3:
                alerts = analyzer.detect_anomaly(recent)
                if alerts:
                    print("ALERT:", alerts)
                    if any(is_critical for _, is_critical in alerts):
                        # FIX 2: Don't write 0,0 for averages — only update the
                        # label column. We do this by reading current averages
                        # first and preserving them, or just letting flush_today
                        # handle it (which runs right after with real averages).
                        # We set a flag via DB so the label is correct at flush.
                        conn = sqlite3.connect(DB_NAME)
                        c_   = conn.cursor()
                        c_.execute(
                            "UPDATE daily_stats SET label='heavy' WHERE date=?",
                            (str(date.today()),)
                        )
                        conn.commit()
                        conn.close()

            # Read today's label from DB (respects user's Resolve/Ignore clicks)
            today_label = get_today_label()

            # Flush today's running average every cycle (live today card)
            flush_today(daily_cpu, daily_ram, label=today_label)

            analyzer.load_7_days()
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        print("\nStopping — saving today's final average...")
        flush_today(daily_cpu, daily_ram, label=get_today_label())
        print("Done. Goodbye.")


if __name__ == "__main__":
    main()
