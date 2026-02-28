"""
routes/profile_routes.py
=========================
HTTP route for the user profile / analytics page.

Endpoints:
- GET /profile    : Renders the profile page with memory analytics
"""

from flask import Blueprint, session, render_template
from database.db import get_db
from services.profileservices import get_profile_stats
from routes.pdf_routes import login_required

profile_bp = Blueprint("profile", __name__)


@profile_bp.route("/profile")
@login_required
def profile():
    """Render the user memory analytics profile page."""
    db = get_db()
    stats = get_profile_stats(db, session["user_id"])
    return render_template(
        "profile.html",
        stats=stats,
        username=session["username"]
    )