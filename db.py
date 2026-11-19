"""Database helpers shared by the portal.

Reads the connection details from the .env file:
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT
"""
import hashlib
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
    )


def query(sql, params=None):
    """Run a SELECT and return a list of dictionaries."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    columns = [c[0] for c in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]
    cur.close()
    conn.close()
    return rows


def execute(sql, params=None):
    """Run an INSERT / UPDATE / DELETE."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    cur.close()
    conn.close()


def hash_password(password):
    """Passwords are never stored as plain text."""
    return hashlib.sha256(str(password).encode()).hexdigest()


def get_setting(key, default=None):
    rows = query("SELECT value FROM settings WHERE key = %s", (key,))
    return rows[0]["value"] if rows else default


def set_setting(key, value):
    execute(
        "INSERT INTO settings (key, value) VALUES (%s, %s) "
        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        (key, str(value)),
    )