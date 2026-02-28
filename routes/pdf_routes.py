"""
routes/pdf_routes.py
=====================
HTTP routes for PDF upload and dashboard.
Routes contain NO business logic — delegates to pdf_service.
"""

from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from database.db import get_db
from services.pdf_service import save_pdf, get_user_pdfs
from functools import wraps

pdf_bp = Blueprint("pdf", __name__)


def login_required(f):
    """Decorator to enforce authentication on routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


@pdf_bp.route("/dashboard")
@login_required
def dashboard():
    """Main dashboard: lists user's uploaded PDFs and topics."""
    db = get_db()
    pdfs = get_user_pdfs(db, session["user_id"])

    # Collect unique topics for navigation
    topics = list({p["topic"] for p in pdfs})

    return render_template("dashboard.html",
                           pdfs=pdfs,
                           topics=sorted(topics),
                           username=session["username"])


@pdf_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    """PDF upload form."""
    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        file = request.files.get("pdf_file")

        if not topic:
            flash("Please enter a topic.", "error")
            return render_template("upload.html")

        if not file or file.filename == "":
            flash("Please select a PDF file.", "error")
            return render_template("upload.html")

        if not file.filename.lower().endswith(".pdf"):
            flash("Only PDF files are supported.", "error")
            return render_template("upload.html")

        pdf_bytes = file.read()
        if len(pdf_bytes) == 0:
            flash("The uploaded file is empty.", "error")
            return render_template("upload.html")

        db = get_db()
        try:
            pdf_id, _ = save_pdf(db, session["user_id"], topic, file.filename, pdf_bytes)
            flash(f"PDF uploaded successfully under topic '{topic}'.", "success")
            return redirect(url_for("quiz.topic_view", topic=topic))
        except Exception as e:
            flash(f"Upload failed: {str(e)}", "error")

    return render_template("upload.html")
