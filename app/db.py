import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ["DATABASE_URL"]


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
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
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        conn.execute("ALTER TABLE runs ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                id SERIAL PRIMARY KEY,
                run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
                timestamp TEXT,
                heart_rate INTEGER,
                distance_km REAL,
                speed REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_records_run_id ON records(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_user_id ON runs(user_id)")


@contextmanager
def get_conn():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_user(email: str, password_hash: str, is_admin: bool = False) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "INSERT INTO users (email, password_hash, is_admin) VALUES (%s, %s, %s) RETURNING *",
            (email, password_hash, is_admin),
        ).fetchone()
        return dict(row)


def get_user_by_email(email: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = %s", (user_id,)).fetchone()
        return dict(row) if row else None


def update_password(user_id: int, password_hash: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))


def any_users_exist() -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM users LIMIT 1").fetchone()
        return row is not None


def insert_run(run: dict, records: list[dict], user_id: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO runs
               (user_id, filename, start_time, distance_km, moving_time_min, avg_hr, max_hr,
                zone1_pct, zone2_pct, zone3_pct, zone4_pct, zone5_pct)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                user_id, run["filename"], run["start_time"], run["distance_km"], run["moving_time_min"],
                run["avg_hr"], run["max_hr"], run["zone1_pct"], run["zone2_pct"],
                run["zone3_pct"], run["zone4_pct"], run["zone5_pct"],
            ),
        )
        run_id = cur.fetchone()["id"]
        conn.cursor().executemany(
            "INSERT INTO records (run_id, timestamp, heart_rate, distance_km, speed) VALUES (%s, %s, %s, %s, %s)",
            [(run_id, r["timestamp"], r["heart_rate"], r["distance_km"], r["speed"]) for r in records],
        )
        return run_id


def list_runs(user_id: int, is_admin: bool = False) -> list[dict]:
    with get_conn() as conn:
        if is_admin:
            rows = conn.execute(
                """SELECT runs.*, users.email AS owner_email FROM runs
                   JOIN users ON users.id = runs.user_id
                   ORDER BY start_time DESC, runs.id DESC"""
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM runs WHERE user_id = %s ORDER BY start_time DESC, id DESC",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_run(run_id: int, user_id: int, is_admin: bool = False) -> dict | None:
    with get_conn() as conn:
        if is_admin:
            row = conn.execute("SELECT * FROM runs WHERE id = %s", (run_id,)).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM runs WHERE id = %s AND user_id = %s", (run_id, user_id)
            ).fetchone()
        return dict(row) if row else None


def get_run_records(run_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT timestamp, heart_rate, distance_km, speed FROM records WHERE run_id = %s ORDER BY id",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_run(run_id: int, user_id: int, is_admin: bool = False) -> bool:
    with get_conn() as conn:
        if is_admin:
            cur = conn.execute("DELETE FROM runs WHERE id = %s", (run_id,))
        else:
            cur = conn.execute("DELETE FROM runs WHERE id = %s AND user_id = %s", (run_id, user_id))
        return cur.rowcount > 0
