"""
routes/curve_routes.py
=======================
HTTP routes for forgetting curve visualization.

Endpoints:
- GET /curve/<topic>        : Renders the curve visualization page
- GET /api/curve/<topic>    : Returns JSON curve data for the canvas graph

The /api/curve endpoint returns both:
  - baseline_curve: Using fixed λ = 0.1
  - learned_curve:  Using ML-learned λ
This allows side-by-side comparison in the UI.
"""

from flask import Blueprint, session, redirect, url_for, render_template, jsonify, request
from database.db import get_db
from services.forgetting_curve_service import (
    get_segments_for_topic, build_curve_points, BASELINE_LAMBDA
)
from services.learning_service import get_learned_params
from services.time_simulation_service import time_range_for_topic
from routes.pdf_routes import login_required

curve_bp = Blueprint("curve", __name__)


@curve_bp.route("/curve/<topic>")
@login_required
def curve_view(topic: str):
    """Render the forgetting curve visualization page for a topic."""
    return render_template("curve.html",
                           topic=topic,
                           username=session["username"])


@curve_bp.route("/api/curve/<topic>")
@login_required
def curve_data(topic: str):
    """
    Return JSON data for the forgetting curve graph.

    Query params:
        current_time (float): Current simulated time from the slider

    Returns JSON:
    {
      "baseline_curve": [{"t": float, "retention": float}, ...],
      "learned_curve":  [{"t": float, "retention": float}, ...],
      "attempts": [{"t": float, "score_pct": float}, ...],
      "segments": [...],
      "learned_lambda": float,
      "baseline_lambda": float,
      "has_data": bool
    }
    """
    db = get_db()
    user_id = session["user_id"]

    # Get current simulated time from slider (for extending the x-axis)
    try:
        current_t = float(request.args.get("current_time", 30.0))
    except (ValueError, TypeError):
        current_t = 30.0

    # Time range for plotting
    t_range = time_range_for_topic(db, user_id, topic)
    t_plot_end = max(t_range["t_max"], current_t + 5.0)
    t_plot_start = t_range["t_min"]

    if not t_range["has_data"]:
        return jsonify({
            "baseline_curve": [],
            "learned_curve": [],
            "attempts": [],
            "segments": [],
            "learned_lambda": BASELINE_LAMBDA,
            "baseline_lambda": BASELINE_LAMBDA,
            "has_data": False
        })

    # Get stored decay segments
    segments = get_segments_for_topic(db, user_id, topic)

    # Get ML-learned parameters
    learned = get_learned_params(db, user_id, topic)
    learned_lambda = learned["learned_lambda"]

    # Build baseline curve (fixed λ=0.1)
    baseline_segments = _override_lambda(segments, BASELINE_LAMBDA)
    baseline_curve = build_curve_points(baseline_segments, t_plot_start, t_plot_end)

    # Build learned curve (ML-adjusted λ)
    learned_segments = _override_lambda(segments, learned_lambda)
    learned_curve = build_curve_points(learned_segments, t_plot_start, t_plot_end)

    # Fetch attempt summary for scatter points on graph
    attempt_rows = db.execute("""
        SELECT simulated_time_days, score_pct
        FROM attempts
        WHERE user_id = ? AND topic = ?
        ORDER BY simulated_time_days ASC
    """, (user_id, topic)).fetchall()

    attempts = [{"t": r["simulated_time_days"], "score_pct": r["score_pct"]} for r in attempt_rows]

    return jsonify({
        "baseline_curve": baseline_curve,
        "learned_curve": learned_curve,
        "attempts": attempts,
        "segments": [dict(s) for s in segments],
        "learned_lambda": learned_lambda,
        "baseline_lambda": BASELINE_LAMBDA,
        "has_data": True,
        "t_min": t_plot_start,
        "t_max": t_plot_end
    })


def _override_lambda(segments: list, new_lambda: float) -> list:
    """
    Return a copy of segments with lambda_val replaced by new_lambda.

    Used to generate baseline vs learned curve comparison
    without modifying the original segment records.

    Args:
        segments: List of segment dicts
        new_lambda: Lambda value to substitute

    Returns:
        New list of segment dicts with updated lambda_val
    """
    return [{**seg, "lambda_val": new_lambda} for seg in segments]
