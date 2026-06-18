import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(os.environ.get("DB_PATH", Path(__file__).resolve().parent.parent / "data" / "runs.db"))


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                start_time TEXT,
                distance_km REAL,
                moving_time_min REAL,
                avg_hr REAL,
                max_hr REAL,
                zone1_pct REAL,
                zone2_pct REAL,
                zone3_pct REAL,
                zone4_pct REAL,
                zone5_pct REAL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                timestamp TEXT,
                heart_rate INTEGER,
                distance_km REAL,
                speed REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_run_id ON records(run_id)")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_run(run: dict, records: list[dict]) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO runs
               (filename, start_time, distance_km, moving_time_min, avg_hr, max_hr,
                zone1_pct, zone2_pct, zone3_pct, zone4_pct, zone5_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run["filename"], run["start_time"], run["distance_km"], run["moving_time_min"],
                run["avg_hr"], run["max_hr"], run["zone1_pct"], run["zone2_pct"],
                run["zone3_pct"], run["zone4_pct"], run["zone5_pct"],
            ),
        )
        run_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO records (run_id, timestamp, heart_rate, distance_km, speed) VALUES (?, ?, ?, ?, ?)",
            [(run_id, r["timestamp"], r["heart_rate"], r["distance_km"], r["speed"]) for r in records],
        )
        return run_id


def list_runs() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM runs ORDER BY start_time DESC, id DESC").fetchall()
        return [dict(r) for r in rows]


def get_run(run_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


def get_run_records(run_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT timestamp, heart_rate, distance_km, speed FROM records WHERE run_id = ? ORDER BY id",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_run(run_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM runs WHERE id = ?", (run_id,))
