"""
services/profile_service.py
============================
Aggregates user-level memory analytics for the profile page.

Provides:
- Per-topic retention stats (current, best, worst, trend)
- Average forgetting rate (lambda) across all topics
- Average retention across all topics
- Total study stats (quizzes, attempts, days active)
"""

import math
from typing import List, Dict, Optional
from services.forgetting_curve_service import retention_at, BASELINE_LAMBDA


def get_profile_stats(db, user_id: int) -> Dict:
    """
    Compute full profile analytics for a user.

    Args:
        db: SQLite database connection
        user_id: Current user's ID

    Returns:
        Dict with keys:
            - topics: list of per-topic stat dicts
            - avg_lambda: float (average decay rate across topics)
            - avg_retention: float (average current retention across topics)
            - total_attempts: int
            - total_topics: int
            - best_topic: str or None
            - worst_topic: str or None
            - total_quizzes: int
    """
    # Get all topics for this user
    topic_rows = db.execute("""
        SELECT DISTINCT topic FROM attempts WHERE user_id = ?
        ORDER BY topic ASC
    """, (user_id,)).fetchall()

    topics_data = []
    lambda_values = []
    retention_values = []

    for row in topic_rows:
        topic = row["topic"]
        stats = get_topic_stats(db, user_id, topic)
        topics_data.append(stats)

        if stats["learned_lambda"] is not None:
            lambda_values.append(stats["learned_lambda"])
        if stats["current_retention"] is not None:
            retention_values.append(stats["current_retention"])

    # Compute averages
    avg_lambda = round(sum(lambda_values) / len(lambda_values), 4) if lambda_values else BASELINE_LAMBDA
    avg_retention = round(sum(retention_values) / len(retention_values), 4) if retention_values else None

    # Best/worst topics by current retention
    topics_with_retention = [t for t in topics_data if t["current_retention"] is not None]
    best_topic = max(topics_with_retention, key=lambda t: t["current_retention"])["topic"] if topics_with_retention else None
    worst_topic = min(topics_with_retention, key=lambda t: t["current_retention"])["topic"] if topics_with_retention else None

    # Total attempts
    total_attempts_row = db.execute("""
        SELECT COUNT(*) as cnt FROM attempts WHERE user_id = ?
    """, (user_id,)).fetchone()
    total_attempts = total_attempts_row["cnt"] if total_attempts_row else 0

    # Total quizzes
    total_quizzes_row = db.execute("""
        SELECT COUNT(*) as cnt FROM quizzes WHERE user_id = ?
    """, (user_id,)).fetchone()
    total_quizzes = total_quizzes_row["cnt"] if total_quizzes_row else 0

    return {
        "topics": topics_data,
        "avg_lambda": avg_lambda,
        "avg_retention": avg_retention,
        "total_attempts": total_attempts,
        "total_topics": len(topics_data),
        "best_topic": best_topic,
        "worst_topic": worst_topic,
        "total_quizzes": total_quizzes,
    }


def get_topic_stats(db, user_id: int, topic: str) -> Dict:
    """
    Compute memory stats for a single topic.

    Args:
        db: SQLite database connection
        user_id: Current user's ID
        topic: Topic name

    Returns:
        Dict with:
            - topic: str
            - attempt_count: int
            - best_score: float
            - worst_score: float
            - latest_score: float
            - current_retention: float (R(t_now) from active segment)
            - learned_lambda: float
            - trend: 'improving' | 'declining' | 'stable' | 'new'
            - first_attempt_day: float
            - latest_attempt_day: float
    """
    attempts = db.execute("""
        SELECT simulated_time_days, score_pct
        FROM attempts
        WHERE user_id = ? AND topic = ?
        ORDER BY simulated_time_days ASC
    """, (user_id, topic)).fetchall()

    if not attempts:
        return {
            "topic": topic,
            "attempt_count": 0,
            "best_score": None,
            "worst_score": None,
            "latest_score": None,
            "current_retention": None,
            "learned_lambda": BASELINE_LAMBDA,
            "trend": "new",
            "first_attempt_day": None,
            "latest_attempt_day": None,
        }

    scores = [a["score_pct"] for a in attempts]
    times = [a["simulated_time_days"] for a in attempts]

    best_score = max(scores)
    worst_score = min(scores)
    latest_score = scores[-1]
    latest_time = times[-1]

    # Get learned lambda
    lp_row = db.execute("""
        SELECT learned_lambda FROM learned_params
        WHERE user_id = ? AND topic = ?
    """, (user_id, topic)).fetchone()
    learned_lambda = lp_row["learned_lambda"] if lp_row else BASELINE_LAMBDA

    # Compute current retention from the active decay segment
    active_seg = db.execute("""
        SELECT t0, r0, lambda_val FROM decay_segments
        WHERE user_id = ? AND topic = ? AND t_end IS NULL
        ORDER BY t0 DESC LIMIT 1
    """, (user_id, topic)).fetchone()

    current_retention = None
    if active_seg:
        # Use the latest attempt time as "now" for demo purposes
        t_now = latest_time
        current_retention = retention_at(
            r0=active_seg["r0"],
            lambda_val=active_seg["lambda_val"],
            t0=active_seg["t0"],
            t=t_now
        )

    # Determine trend (compare last 2 scores)
    if len(scores) < 2:
        trend = "new"
    else:
        delta = scores[-1] - scores[-2]
        if delta > 0.05:
            trend = "improving"
        elif delta < -0.05:
            trend = "declining"
        else:
            trend = "stable"

    return {
        "topic": topic,
        "attempt_count": len(attempts),
        "best_score": round(best_score, 4),
        "worst_score": round(worst_score, 4),
        "latest_score": round(latest_score, 4),
        "current_retention": round(current_retention, 4) if current_retention is not None else None,
        "learned_lambda": round(learned_lambda, 4),
        "trend": trend,
        "first_attempt_day": round(times[0], 2),
        "latest_attempt_day": round(latest_time, 2),
    }