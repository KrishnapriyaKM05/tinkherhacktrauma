"""
routes/quiz_routes.py
======================
HTTP routes for quiz generation, display, and attempt submission.

FLOW:
1. User selects a PDF from the topic view
2. System generates fresh MCQs via Groq LLM API
3. User submits answers
4. Attempt is stored; decay segment created; ML params updated
"""

from flask import Blueprint, request, session, redirect, url_for, render_template, flash, jsonify
from database.db import get_db
from services.pdf_service import get_user_pdfs, get_pdf_text
from services.quiz_service import generate_quiz, save_quiz_to_db
from services.forgetting_curve_service import (
    close_active_segment, create_decay_segment, get_segments_for_topic
)
from services.learning_service import update_learned_params, get_learned_params
from services.time_simulation_service import validate_simulated_time, get_last_attempt_time
from routes.pdf_routes import login_required

quiz_bp = Blueprint("quiz", __name__)


@quiz_bp.route("/topic/<topic>")
@login_required
def topic_view(topic: str):
    """
    Show all PDFs for a topic, attempt history, and the forgetting curve link.
    """
    db = get_db()
    user_id = session["user_id"]

    pdfs = [p for p in get_user_pdfs(db, user_id) if p["topic"] == topic]

    # Retrieve attempt history for this topic
    attempts = db.execute("""
        SELECT a.id, a.simulated_time_days, a.score_pct, a.completed_at,
               q.id as quiz_id
        FROM attempts a
        JOIN quizzes q ON a.quiz_id = q.id
        WHERE a.user_id = ? AND a.topic = ?
        ORDER BY a.simulated_time_days ASC
    """, (user_id, topic)).fetchall()

    last_time = get_last_attempt_time(db, user_id, topic)
    learned = get_learned_params(db, user_id, topic)

    return render_template("topic_view.html",
                           topic=topic,
                           pdfs=pdfs,
                           attempts=[dict(a) for a in attempts],
                           last_time=last_time,
                           learned_lambda=learned["learned_lambda"],
                           username=session["username"])


@quiz_bp.route("/quiz/generate/<int:pdf_id>", methods=["GET", "POST"])
@login_required
def generate(pdf_id: int):
    """
    Generate a fresh quiz for a given PDF and render the quiz form.

    GET: Show simulated time selector before generating
    POST: Generate quiz and show questions
    """
    db = get_db()
    user_id = session["user_id"]

    # Verify PDF ownership
    pdf_text = get_pdf_text(db, pdf_id, user_id)
    if pdf_text is None:
        flash("PDF not found or access denied.", "error")
        return redirect(url_for("pdf.dashboard"))

    if not pdf_text.strip():
        flash("This PDF appears to have no extractable text.", "error")
        return redirect(url_for("pdf.dashboard"))

    # Get PDF metadata for topic
    pdf_row = db.execute("SELECT topic FROM pdfs WHERE id = ?", (pdf_id,)).fetchone()
    topic = pdf_row["topic"]

    last_time = get_last_attempt_time(db, user_id, topic) or 0.0

    if request.method == "POST":
        raw_time = request.form.get("simulated_time", last_time + 1.0)
        try:
            sim_time = validate_simulated_time(float(raw_time))
        except (ValueError, TypeError):
            sim_time = last_time + 1.0

        # Enforce time moves forward
        if sim_time <= last_time and last_time > 0:
            flash(f"Simulated time must be after your last attempt (day {last_time}).", "error")
            return render_template("pre_quiz.html", pdf_id=pdf_id, topic=topic,
                                   last_time=last_time, min_time=last_time + 0.1)

        try:
            questions = generate_quiz(pdf_text)
        except EnvironmentError as e:
            flash(str(e), "error")
            return redirect(url_for("quiz.topic_view", topic=topic))
        except RuntimeError as e:
            flash(f"Quiz generation failed: {str(e)}", "error")
            return redirect(url_for("quiz.topic_view", topic=topic))

        quiz_id = save_quiz_to_db(db, pdf_id, user_id, topic, questions)

        # Reload questions from DB (with IDs)
        db_questions = db.execute("""
            SELECT * FROM quiz_questions WHERE quiz_id = ?
        """, (quiz_id,)).fetchall()

        return render_template("quiz.html",
                               quiz_id=quiz_id,
                               topic=topic,
                               questions=[dict(q) for q in db_questions],
                               simulated_time=sim_time)

    # GET: Show time selector
    return render_template("pre_quiz.html",
                           pdf_id=pdf_id,
                           topic=topic,
                           last_time=last_time,
                           min_time=last_time + 0.1)


@quiz_bp.route("/quiz/submit/<int:quiz_id>", methods=["POST"])
@login_required
def submit(quiz_id: int):
    """
    Process a quiz submission:
    1. Score the attempt
    2. Store attempt + answers
    3. Close previous decay segment
    4. Create new decay segment
    5. Update ML learned parameters
    """
    db = get_db()
    user_id = session["user_id"]

    # Verify quiz ownership
    quiz = db.execute(
        "SELECT * FROM quizzes WHERE id = ? AND user_id = ?", (quiz_id, user_id)
    ).fetchone()
    if not quiz:
        flash("Quiz not found.", "error")
        return redirect(url_for("pdf.dashboard"))

    topic = quiz["topic"]

    raw_time = request.form.get("simulated_time", "1.0")
    try:
        sim_time = validate_simulated_time(float(raw_time))
    except (ValueError, TypeError):
        sim_time = 1.0

    # Retrieve all questions for this quiz
    questions = db.execute(
        "SELECT * FROM quiz_questions WHERE quiz_id = ?", (quiz_id,)
    ).fetchall()

    if not questions:
        flash("No questions found for this quiz.", "error")
        return redirect(url_for("quiz.topic_view", topic=topic))

    # Score the submission
    correct_count = 0
    answers = []
    for q in questions:
        selected = request.form.get(f"q_{q['id']}", "").upper()
        is_correct = int(selected == q["correct_option"])
        correct_count += is_correct
        answers.append({
            "question_id": q["id"],
            "selected_option": selected or None,
            "is_correct": is_correct
        })

    score_pct = round(correct_count / len(questions), 4)

    # Store attempt record
    cursor = db.execute("""
        INSERT INTO attempts (quiz_id, user_id, topic, simulated_time_days, score_pct)
        VALUES (?, ?, ?, ?, ?)
    """, (quiz_id, user_id, topic, sim_time, score_pct))
    attempt_id = cursor.lastrowid

    # Store per-question answers
    for ans in answers:
        db.execute("""
            INSERT INTO attempt_answers (attempt_id, question_id, selected_option, is_correct)
            VALUES (?, ?, ?, ?)
        """, (attempt_id, ans["question_id"], ans["selected_option"], ans["is_correct"]))

    db.commit()

    # Close previous decay segment (ends at sim_time)
    close_active_segment(db, user_id, topic, sim_time)

    # Get ML-learned lambda (or baseline)
    learned = get_learned_params(db, user_id, topic)
    lambda_val = learned["learned_lambda"]

    # Create new decay segment starting at sim_time
    create_decay_segment(db, attempt_id, user_id, topic, sim_time, score_pct, lambda_val)

    # Update ML parameters with new data
    ml_result = update_learned_params(db, user_id, topic)

    return render_template("result.html",
                           topic=topic,
                           score_pct=score_pct,
                           correct_count=correct_count,
                           total=len(questions),
                           sim_time=sim_time,
                           ml_result=ml_result,
                           questions=[dict(q) for q in questions],
                           answers=answers)
