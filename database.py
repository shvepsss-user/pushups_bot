import sqlite3
from datetime import date, timedelta
from contextlib import contextmanager

DB_PATH = "pushups.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_seen TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pushups (
                user_id INTEGER,
                date TEXT,
                count INTEGER,
                PRIMARY KEY (user_id, date),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def register_user(user_id, username, first_name):
    today = date.today().isoformat()
    with get_db() as db:
        db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, last_seen) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, today)
        )
        db.execute(
            "UPDATE users SET username = ?, first_name = ?, last_seen = ? WHERE user_id = ?",
            (username, first_name, today, user_id)
        )

def add_or_update_pushups(user_id, count, pushup_date=None):
    if pushup_date is None:
        pushup_date = date.today().isoformat()
    with get_db() as db:
        existing = db.execute(
            "SELECT count FROM pushups WHERE user_id = ? AND date = ?",
            (user_id, pushup_date)
        ).fetchone()
        new_count = count + (existing["count"] if existing else 0)
        db.execute(
            "INSERT OR REPLACE INTO pushups (user_id, date, count) VALUES (?, ?, ?)",
            (user_id, pushup_date, new_count)
        )
    return new_count

def get_user_today(user_id):
    today = date.today().isoformat()
    with get_db() as db:
        row = db.execute(
            "SELECT count FROM pushups WHERE user_id = ? AND date = ?",
            (user_id, today)
        ).fetchone()
    return row["count"] if row else 0

def get_user_on_date(user_id, target_date):
    with get_db() as db:
        row = db.execute(
            "SELECT count FROM pushups WHERE user_id = ? AND date = ?",
            (user_id, target_date)
        ).fetchone()
    return row["count"] if row else 0

def get_all_registered_users():
    with get_db() as db:
        rows = db.execute("SELECT user_id, username, first_name FROM users").fetchall()
    return [(row["user_id"], row["username"], row["first_name"]) for row in rows]

def get_debtors_for_date(target_date):
    goal = 100
    debtors = []
    with get_db() as db:
        users = db.execute("SELECT user_id, username, first_name FROM users").fetchall()
        for user in users:
            user_id = user["user_id"]
            row = db.execute(
                "SELECT count FROM pushups WHERE user_id = ? AND date = ?",
                (user_id, target_date)
            ).fetchone()
            count = row["count"] if row else 0
            if count < goal:
                debtors.append((user_id, user["username"], user["first_name"], count))
    return debtors

def get_today_debtors():
    today = date.today().isoformat()
    return get_debtors_for_date(today)

def get_yesterday_debtors():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    return get_debtors_for_date(yesterday)

def get_leaderboard_today():
    today = date.today().isoformat()
    with get_db() as db:
        rows = db.execute("""
            SELECT u.first_name, u.username, p.count
            FROM pushups p
            JOIN users u ON u.user_id = p.user_id
            WHERE p.date = ?
            ORDER BY p.count DESC
        """, (today,)).fetchall()
    return [(row["first_name"], row["username"], row["count"]) for row in rows]
