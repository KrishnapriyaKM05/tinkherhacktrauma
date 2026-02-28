"""
services/auth_service.py
=========================
Handles user registration, login, and password hashing.

SECURITY GUARANTEES:
--------------------
- Passwords are never stored or logged in plaintext
- Timing-safe password verification via werkzeug
- No sensitive data returned to callers
- User existence is not leaked during login
"""

from werkzeug.security import generate_password_hash, check_password_hash
from typing import Optional, Dict


# -----------------------------
# Registration
# -----------------------------

def register_user(db, username: str, password: str) -> Dict:
    """
    Register a new user with a securely hashed password.
    """
    if not isinstance(username, str) or not isinstance(password, str):
        return {
            "success": False,
            "message": "Invalid input.",
            "user_id": None
        }

    username = username.strip()

    if not username or not password:
        return {
            "success": False,
            "message": "Username and password are required.",
            "user_id": None
        }

    if len(username) < 3:
        return {
            "success": False,
            "message": "Username must be at least 3 characters.",
            "user_id": None
        }

    if len(password) < 4:
        return {
            "success": False,
            "message": "Password must be at least 4 characters.",
            "user_id": None
        }

    # Prevent duplicate usernames
    existing = db.execute(
        "SELECT 1 FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if existing:
        return {
            "success": False,
            "message": "Username already taken.",
            "user_id": None
        }

    password_hash = generate_password_hash(password)

    cursor = db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username, password_hash)
    )
    db.commit()

    return {
        "success": True,
        "message": "Account created successfully.",
        "user_id": cursor.lastrowid
    }


# -----------------------------
# Login
# -----------------------------

def login_user(db, username: str, password: str) -> Dict:
    """
    Authenticate a user using username and password.

    NOTE:
    -----
    Error messages are intentionally generic to prevent
    username enumeration attacks.
    """
    if not isinstance(username, str) or not isinstance(password, str):
        return _login_failed()

    username = username.strip()

    if not username or not password:
        return _login_failed()

    row = db.execute(
        "SELECT id, password_hash FROM users WHERE username = ?",
        (username,)
    ).fetchone()

    if not row:
        return _login_failed()

    if not check_password_hash(row["password_hash"], password):
        return _login_failed()

    return {
        "success": True,
        "message": "Login successful.",
        "user_id": row["id"],
        "username": username
    }


def _login_failed() -> Dict:
    """Uniform login failure response (prevents user enumeration)."""
    return {
        "success": False,
        "message": "Invalid username or password.",
        "user_id": None,
        "username": None
    }


# -----------------------------
# User Lookup
# -----------------------------

def get_user_by_id(db, user_id: int) -> Optional[Dict]:
    """
    Retrieve minimal user info by ID.

    SECURITY:
    ---------
    - Returns only non-sensitive fields
    - Safe to expose to session validation logic
    """
    if not user_id:
        return None

    row = db.execute(
        "SELECT id, username FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    return dict(row) if row else None