"""
SQLite database layer.

Tables:
  credentials — Fernet-encrypted VFS password
  sessions    — JWT tokens per country (for session reuse)
  results     — appointment check history
"""
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
from cryptography.fernet import Fernet

from config import DB_PATH


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS credentials (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    encrypted_password BLOB    NOT NULL,
    created_at         TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT    NOT NULL,
    jwt_token    TEXT    NOT NULL,
    expires_at   TEXT    NOT NULL,
    created_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT    NOT NULL,
    country_name TEXT    NOT NULL,
    status       TEXT    NOT NULL,
    detail       TEXT,
    checked_at   TEXT    NOT NULL
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create all tables if they don't exist yet."""
    with _connect() as conn:
        conn.executescript(_DDL)
    logging.info(f"Database initialised at: {DB_PATH}")


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def save_credentials(plaintext_password: str, master_key: str) -> None:
    """Encrypt and store VFS password. Replaces any existing row."""
    fernet = Fernet(master_key.encode())
    encrypted = fernet.encrypt(plaintext_password.encode())
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute("DELETE FROM credentials")
        conn.execute(
            "INSERT INTO credentials (encrypted_password, created_at) VALUES (?, ?)",
            (encrypted, now),
        )
    logging.info("Password saved to DB (Fernet-encrypted).")


def get_encrypted_password() -> Optional[bytes]:
    """Return the encrypted password blob, or None if not set."""
    with _connect() as conn:
        row = conn.execute("SELECT encrypted_password FROM credentials LIMIT 1").fetchone()
    if row is None:
        return None
    return bytes(row["encrypted_password"])


def decrypt_password(encrypted_password: bytes, master_key: str) -> str:
    """Decrypt a Fernet-encrypted password blob. Returns plaintext string."""
    fernet = Fernet(master_key.encode())
    return fernet.decrypt(encrypted_password).decode()


# ---------------------------------------------------------------------------
# Sessions (JWT)
# ---------------------------------------------------------------------------

def save_jwt(country_code: str, jwt_token: str) -> None:
    """
    Decode the JWT to extract its expiry, then store it.
    If decoding fails, assume 1-hour expiry as a safe default.
    """
    now = datetime.now(timezone.utc)
    try:
        payload = jwt.decode(jwt_token, options={"verify_signature": False})
        exp_ts = payload.get("exp")
        expires_at = (
            datetime.fromtimestamp(exp_ts, tz=timezone.utc).isoformat()
            if exp_ts
            else (now + timedelta(hours=1)).isoformat()
        )
    except Exception:
        expires_at = (now + timedelta(hours=1)).isoformat()

    with _connect() as conn:
        conn.execute(
            "DELETE FROM sessions WHERE country_code = ?", (country_code,)
        )
        conn.execute(
            "INSERT INTO sessions (country_code, jwt_token, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (country_code, jwt_token, expires_at, now.isoformat()),
        )
    logging.info(f"[{country_code}] JWT saved, expires at: {expires_at}")


def get_valid_jwt(country_code: str) -> Optional[str]:
    """
    Return a stored JWT token for this country if it hasn't expired yet.
    Returns None if no token exists or the token is expired/expiring soon.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT jwt_token, expires_at FROM sessions WHERE country_code = ? ORDER BY id DESC LIMIT 1",
            (country_code,),
        ).fetchone()

    if row is None:
        return None

    expires_at = datetime.fromisoformat(row["expires_at"])
    # Treat token as expired if less than 5 minutes remain
    buffer = timedelta(minutes=5)
    if datetime.now(timezone.utc) + buffer >= expires_at:
        logging.info(f"[{country_code}] Stored JWT is expired or expiring soon.")
        return None

    logging.info(f"[{country_code}] Reusing stored JWT (valid until {row['expires_at']}).")
    return row["jwt_token"]


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

def save_result(country_code: str, country_name: str, status: str, detail: str) -> None:
    """Persist one appointment check result."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO results (country_code, country_name, status, detail, checked_at) VALUES (?, ?, ?, ?, ?)",
            (country_code, country_name, status, detail, now),
        )


def get_all_results(limit: int = 50) -> list[dict]:
    """Return the most recent results as a list of dicts."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM results ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
