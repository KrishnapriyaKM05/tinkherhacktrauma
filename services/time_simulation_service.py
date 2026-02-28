"""
services/time_simulation_service.py
=====================================
Manages simulated time for the Cognitive Memory Analytics System.

RATIONALE:
----------
Real memory decay happens over days/weeks. For a demo/hackathon system,
we simulate time progression via a UI slider.

Simulated time is measured in "simulated days" (a float).

RULES:
------
- Each quiz attempt stores the simulated time at which it was taken.
- Time is NOT real — it's a user-controlled value from the UI.
- Time is stored per-attempt in the database.
- The slider in the UI controls what "current simulated time" is.
- Simulated time can only move forward (no going back in time).

USAGE:
------
When a user takes a quiz, the frontend passes the current slider value
as `simulated_time_days`. This value is stored with the attempt.
"""

from typing import Optional


# Default starting time (day 0)
DEFAULT_START_TIME = 0.0

# Maximum simulated time range shown on slider (in days)
MAX_SIMULATED_DAYS = 90.0

# Minimum step size (fractions of a simulated day)
MIN_TIME_STEP = 0.1


def validate_simulated_time(t: float) -> float:
    """
    Validate and clamp simulated time to a reasonable range.

    Args:
        t: Proposed simulated time (days)

    Returns:
        Clamped value in [DEFAULT_START_TIME, MAX_SIMULATED_DAYS]
    """
    return round(max(DEFAULT_START_TIME, min(MAX_SIMULATED_DAYS, float(t))), 2)


def get_last_attempt_time(db, user_id: int, topic: str) -> Optional[float]:
    """
    Get the simulated time of the most recent quiz attempt for user+topic.

    Used to:
    - Prevent taking a quiz at an earlier simulated time than the last attempt
    - Pre-fill the slider minimum value

    Args:
        db: SQLite database connection
        user_id: Current user ID
        topic: Topic name

    Returns:
        Most recent simulated_time_days as float, or None if no attempts exist
    """
    row = db.execute("""
        SELECT MAX(simulated_time_days) as last_t
        FROM attempts
        WHERE user_id = ? AND topic = ?
    """, (user_id, topic)).fetchone()

    if row and row["last_t"] is not None:
        return float(row["last_t"])
    return None


def time_range_for_topic(db, user_id: int, topic: str) -> dict:
    """
    Get the full time range covered by all attempts for a topic.

    Used to set the plotting window for the forgetting curve.

    Args:
        db: SQLite database connection
        user_id: Current user ID
        topic: Topic name

    Returns:
        Dict with keys: t_min (float), t_max (float), has_data (bool)
    """
    row = db.execute("""
        SELECT MIN(simulated_time_days) as t_min, MAX(simulated_time_days) as t_max
        FROM attempts
        WHERE user_id = ? AND topic = ?
    """, (user_id, topic)).fetchone()

    if row and row["t_min"] is not None:
        t_min = float(row["t_min"])
        # Extend t_max a bit to show future decay
        t_max = float(row["t_max"]) + 20.0
        return {"t_min": t_min, "t_max": t_max, "has_data": True}

    return {"t_min": 0.0, "t_max": MAX_SIMULATED_DAYS, "has_data": False}
