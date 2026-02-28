"""
services/learning_service.py
=============================
Machine Learning layer for the Cognitive Memory Analytics System.

SECURITY & ISOLATION GUARANTEES:
--------------------------------
- Learning is strictly scoped to (user_id, topic)
- No global aggregation is possible
- Safe fallbacks on insufficient or bad data
- All learned parameters are explainable and auditable
"""

import math
from typing import List, Dict, Tuple
from services.forgetting_curve_service import BASELINE_LAMBDA


# -----------------------------
# Constants
# -----------------------------

EMA_ALPHA = 0.3
MIN_DELTA_T = 0.01
LAMBDA_MIN = 0.01
LAMBDA_MAX = 2.0
R0_BOOST_MIN = -0.2
R0_BOOST_MAX = 0.3


# -----------------------------
# Lambda Learning
# -----------------------------

def learn_lambda_from_attempts(attempts: List[Dict]) -> Tuple[float, str]:
    """
    Estimate personalized decay rate λ from historical attempts.

    Uses log-linear regression on consecutive attempt pairs.
    """
    if len(attempts) < 2:
        return BASELINE_LAMBDA, "Insufficient data — using baseline λ"

    # Ensure correct ordering
    sorted_attempts = sorted(
        attempts,
        key=lambda a: float(a.get("simulated_time_days", 0.0))
    )

    estimates = []

    for i in range(len(sorted_attempts) - 1):
        prev = sorted_attempts[i]
        nxt = sorted_attempts[i + 1]

        try:
            t_prev = float(prev["simulated_time_days"])
            t_next = float(nxt["simulated_time_days"])
            r_prev = max(0.01, float(prev["score_pct"]))
            r_next = max(0.01, float(nxt["score_pct"]))
        except (KeyError, TypeError, ValueError):
            continue

        delta_t = t_next - t_prev
        if delta_t < MIN_DELTA_T:
            continue

        try:
            lam = -math.log(r_next / r_prev) / delta_t
            if LAMBDA_MIN <= lam <= LAMBDA_MAX:
                estimates.append(lam)
        except (ValueError, ZeroDivisionError):
            continue

    if not estimates:
        return BASELINE_LAMBDA, "No valid λ estimates — using baseline λ"

    learned = sum(estimates) / len(estimates)
    learned = round(max(LAMBDA_MIN, min(LAMBDA_MAX, learned)), 4)

    explanation = (
        f"Learned λ={learned:.4f} from {len(estimates)} attempt pair(s). "
        f"Raw estimates={list(map(lambda x: round(x,4), estimates))}. "
        f"Method=mean log-linear regression."
    )

    return learned, explanation


# -----------------------------
# R₀ Boost Learning
# -----------------------------

def learn_r0_boost_from_attempts(attempts: List[Dict]) -> Tuple[float, str]:
    """
    Estimate R₀ boost using exponential moving average of score deltas.
    """
    if len(attempts) < 2:
        return 0.0, "Insufficient data — no R₀ boost"

    sorted_attempts = sorted(
        attempts,
        key=lambda a: float(a.get("simulated_time_days", 0.0))
    )

    ema = 0.0
    deltas = []

    for i in range(len(sorted_attempts) - 1):
        try:
            r_prev = float(sorted_attempts[i]["score_pct"])
            r_next = float(sorted_attempts[i + 1]["score_pct"])
        except (KeyError, TypeError, ValueError):
            continue

        delta = r_next - r_prev
        deltas.append(round(delta, 4))
        ema = EMA_ALPHA * delta + (1 - EMA_ALPHA) * ema

    boost = round(max(R0_BOOST_MIN, min(R0_BOOST_MAX, ema)), 4)

    explanation = (
        f"R₀ boost={boost:.4f} (EMA α={EMA_ALPHA}). "
        f"Score deltas={deltas}. "
        f"Applied additively to initial retention."
    )

    return boost, explanation


# -----------------------------
# DB Integration
# -----------------------------

def update_learned_params(db, user_id: int, topic: str) -> Dict:
    """
    Run ML learning for a specific user+topic and persist results.

    SECURITY:
    ---------
    - user_id is mandatory
    - topic is mandatory
    - Data is strictly scoped
    """

    if not user_id or not topic:
        raise PermissionError("Invalid user or topic for learning")

    rows = db.execute("""
        SELECT simulated_time_days, score_pct
        FROM attempts
        WHERE user_id = ? AND topic = ?
        ORDER BY simulated_time_days ASC
    """, (user_id, topic)).fetchall()

    attempts = [dict(r) for r in rows]

    learned_lambda, lambda_exp = learn_lambda_from_attempts(attempts)
    learned_r0_boost, boost_exp = learn_r0_boost_from_attempts(attempts)

    db.execute("""
        INSERT INTO learned_params
            (user_id, topic, learned_lambda, learned_r0_boost, updated_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, topic) DO UPDATE SET
            learned_lambda = excluded.learned_lambda,
            learned_r0_boost = excluded.learned_r0_boost,
            updated_at = excluded.updated_at
    """, (user_id, topic, learned_lambda, learned_r0_boost))

    db.commit()

    return {
        "learned_lambda": learned_lambda,
        "learned_r0_boost": learned_r0_boost,
        "lambda_explanation": lambda_exp,
        "boost_explanation": boost_exp,
        "num_attempts": len(attempts)
    }


def get_learned_params(db, user_id: int, topic: str) -> Dict:
    """
    Retrieve learned parameters for a user+topic.

    Falls back to baseline if none exist.
    """

    if not user_id or not topic:
        return {
            "learned_lambda": BASELINE_LAMBDA,
            "learned_r0_boost": 0.0
        }

    row = db.execute("""
        SELECT learned_lambda, learned_r0_boost
        FROM learned_params
        WHERE user_id = ? AND topic = ?
    """, (user_id, topic)).fetchone()

    if row:
        return {
            "learned_lambda": row["learned_lambda"],
            "learned_r0_boost": row["learned_r0_boost"]
        }

    return {
        "learned_lambda": BASELINE_LAMBDA,
        "learned_r0_boost": 0.0
    }