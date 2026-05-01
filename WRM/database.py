import sqlite3
from config import DB_NAME


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS system_stats (
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            cpu  REAL,
            ram  REAL,
            disk REAL
        )
    """)

    # label column stores "heavy" or "light" based on user anomaly response
    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            date    TEXT PRIMARY KEY,
            avg_cpu REAL,
            avg_ram REAL,
            label   TEXT DEFAULT 'light'
        )
    """)

    # Migration: safely add label column if DB already exists without it
    try:
        c.execute("ALTER TABLE daily_stats ADD COLUMN label TEXT DEFAULT 'light'")
    except Exception:
        pass  # column already exists, ignore

    conn.commit()
    conn.close()


def insert_data(data):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        INSERT INTO system_stats (cpu, ram, disk)
        VALUES (?, ?, ?)
    """, (data["cpu"], data["ram"], data["disk"]))

    conn.commit()
    conn.close()


def insert_daily_avg(date, cpu, ram, label="light"):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        INSERT OR REPLACE INTO daily_stats (date, avg_cpu, avg_ram, label)
        VALUES (?, ?, ?, ?)
    """, (date, cpu, ram, label))

    conn.commit()
    conn.close()


def update_today_label(label):
    """
    Update today's label when user clicks Resolve or Ignore on an alert.
      Ignore / no action → "heavy"
      Resolve            → "light"

    FIX: Use INSERT OR REPLACE instead of plain UPDATE.
    UPDATE silently does nothing if today's row doesn't exist yet
    (e.g. main.py hasn't flushed today's first sample yet).
    INSERT OR REPLACE creates the row if missing.
    avg_cpu/avg_ram default to 0 — main.py will overwrite with real
    values on its next flush_today() call (every 5 seconds).
    """
    from datetime import date
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    today = str(date.today())

    # Try update first (preserves existing avg values)
    c.execute("UPDATE daily_stats SET label = ? WHERE date = ?", (label, today))

    # If no row existed, insert one so the label is recorded
    if c.rowcount == 0:
        c.execute("""
            INSERT OR IGNORE INTO daily_stats (date, avg_cpu, avg_ram, label)
            VALUES (?, 0, 0, ?)
        """, (today, label))

    conn.commit()
    conn.close()


def get_avg_for_date(date_str):
    """
    Compute avg CPU/RAM from raw system_stats rows for a given date.
    Returns (avg_cpu, avg_ram) or (0.0, 0.0) if no rows exist.
    """
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        SELECT AVG(cpu), AVG(ram)
        FROM system_stats
        WHERE DATE(timestamp) = ?
    """, (date_str,))

    row = c.fetchone()
    conn.close()

    if row and row[0] is not None:
        return round(row[0], 2), round(row[1], 2)
    return 0.0, 0.0


def get_all_saved_dates():
    """Return set of date strings already saved in daily_stats."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT date FROM daily_stats")
    rows = c.fetchall()
    conn.close()
    return {r[0] for r in rows}


def get_distinct_raw_dates():
    """Return sorted list of distinct dates present in system_stats."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT DISTINCT DATE(timestamp) FROM system_stats ORDER BY 1")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]
