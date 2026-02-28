"""
routes/auth_routes.py
======================
HTTP routes for user registration and login.
Routes contain NO business logic — all logic is delegated to auth_service.
"""

from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from database.db import get_db
from services.auth_service import register_user, login_user

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
def index():
    """Redirect to dashboard if logged in, else to login."""
    if "user_id" in session:
        return redirect(url_for("pdf.dashboard"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """User registration page."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        result = register_user(db, username, password)
        if result["success"]:
            session["user_id"] = result["user_id"]
            session["username"] = username
            return redirect(url_for("pdf.dashboard"))
        else:
            flash(result["message"], "error")
    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """User login page."""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        result = login_user(db, username, password)
        if result["success"]:
            session["user_id"] = result["user_id"]
            session["username"] = result["username"]
            return redirect(url_for("pdf.dashboard"))
        else:
            flash(result["message"], "error")
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Clear session and redirect to login."""
    session.clear()
    return redirect(url_for("auth.login"))
