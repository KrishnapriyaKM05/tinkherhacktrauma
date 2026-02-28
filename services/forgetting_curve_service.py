"""
services/forgetting_curve_service.py
=====================================
Core mathematical engine for the Cognitive Memory Analytics System.

SECURITY & ISOLATION GUARANTEES:
--------------------------------
- All decay segments are strictly scoped to (user_id, topic)
- Attempts are verified for ownership before segment creation
- Active segment closure cannot affect other users
- Curve reads are user-isolated and immutable
"""

import math
from typing import List, Dict


# -----------------------------
# Constants
# -----------------------------

BASELINE_LAMBDA = 0.1
MIN_RETENTION = 0.2
MAX_RETENTION = 1.0
R0_MIN_FLOOR = 0.2


# -----------------------------
# Core Math
# -----------------------------

def score_to_r0(score_pct: float) -> float:
    """Convert quiz score (0.0–1.0) to initial retention R₀."""
    try:
        score = float(score_pct)
    except (TypeError, ValueError):
        score = 0.0

    r0 = max(R0_MIN_FLOOR, min(MAX_RETENTION, score))
    return round(r0, 4)


def retention_at(r0: float, lambda_val: float, t0: float, t: float) -> float:
    """Compute retention at time t for a single decay segment."""
    if t < t0:
        return 0.0

    try:
        raw = r0 * math.exp(-lambda_val * (t - t0))
    except Exception:
        raw = MIN_RETENTION

    return round(max(MIN_RETENTION, min(MAX_RETENTION, raw)), 4)


# -----------------------------
# Curve Construction
# -----------------------------

def build_curve_points(
    segments: List[Dict],
    t_start: float,
    t_end: float,
    num_points: int = 200
) -> List[Dict]:
    """
    Generate (time, retention) points for the piecewise forgetting curve.
    """
    if not segments or num_points < 2 or t_end <= t_start:
        return []

    step = (t_end - t_start) / (num_points - 1)
    curve = []

    for i in range(num_points):
        t = t_start + i * step
        r = _retention_for_time(segments, t)
        curve.append({"t": round(t, 3), "retention": r})

    return curve


def _retention_for_time(segments: List[Dict], t: float) -> float:
    """
    Find the active decay segment for time t.
    Segments must be sorted by t0 DESC (newest first).
    """
    for seg in segments:
        t0 = seg.get("t0")
        t_end = seg.get("t_end")

        if t0 is None:
            continue

        if t >= t0 and (t_end is None or t < t_end):
            return retention_at(
                r0=seg["r0"],
                lambda_val=seg["lambda_val"],
                t0=t0,
                t=t
            )

    return MIN_RETENTION


# -----------------------------
# DB Mutation (SECURE)
# -----------------------------

def close_active_segment(db, user_id: int, topic: str, t_close: float):
    """
    Close the currently open decay segment for a user+topic.

    SECURITY:
    ---------
    - Only affects the current user's open segment
    - No cross-user mutation possible
    """
    if not user_id or not topic:
        raise PermissionError("Invalid user or topic")

    db.execute("""
        UPDATE decay_segments
        SET t_end = ?
        WHERE user_id = ?
          AND topic = ?
          AND t_end IS NULL
    """, (t_close, user_id, topic))

    db.commit()


def create_decay_segment(
    db,
    attempt_id: int,
    user_id: int,
    topic: str,
    t0: float,
    score_pct: float,
    lambda_val: float
) -> int:
    """
    Create a new decay segment after a quiz attempt.

    SECURITY (CRITICAL):
    -------------------
    - Verifies that the attempt belongs to the user
    - Prevents attaching segments to foreign attempts
    """
    if not user_id or not attempt_id or not topic:
        raise PermissionError("Invalid decay segment creation request")

    # 🔐 Ownership check: attempt must belong to user
    owner = db.execute("""
        SELECT 1 FROM attempts
        WHERE id = ? AND user_id = ?
    """, (attempt_id, user_id)).fetchone()

    if owner is None:
        raise PermissionError("Attempt does not belong to user")

    r0 = score_to_r0(score_pct)

    cursor = db.execute("""
        INSERT INTO decay_segments
            (attempt_id, user_id, topic, t0, r0, lambda_val, t_end)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
    """, (
        attempt_id,
        user_id,
        topic,
        float(t0),
        r0,
        float(lambda_val)
    ))

    db.commit()
    return cursor.lastrowid


# -----------------------------
# DB Reads (SECURE)
# -----------------------------

def get_segments_for_topic(db, user_id: int, topic: str) -> List[Dict]:
    """
    Retrieve decay segments for a user+topic.

    SECURITY:
    ---------
    - Fully user-scoped
    - Ordered newest-first for correct curve resolution
    """
    if not user_id or not topic:
        return []

    rows = db.execute("""
        SELECT id, t0, r0, lambda_val, t_end
        FROM decay_segments
        WHERE user_id = ?
          AND topic = ?
        ORDER BY t0 DESC
    """, (user_id, topic)).fetchall()

    return [dict(row) for row in rows]