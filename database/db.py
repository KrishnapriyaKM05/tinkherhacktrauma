"""
database/db.py
==============
Manages SQLite connection and schema initialization.

Schema overview:
- users: Authentication records
- pdfs: Uploaded PDF blobs, linked to user and topic
- quizzes: Quiz metadata per attempt (fresh quiz each time)
- quiz_questions: Individual MCQ questions per quiz
- attempts: Each quiz attempt is a memory event with simulated time
- attempt_answers: Per-question answers for each attempt
- decay_segments: Piecewise exponential decay segments (NEVER modified after creation)
- learned_params: ML-learned λ and R₀ per user+topic
"""

import sqlite3
from flask import g, current_app
import os

DATABASE = os.path.join(os.path.dirname(__file__), "..", "memory.db")


def get_db():
    """Return a database connection, creating one if needed for this request context."""
    if "db" not in g:
        g.db = sqlite3.connect(
            DATABASE,
            
        )
        g.db.row_factory = sqlite3.Row  # Allows dict-like row access
    return g.db


def close_db(e=None):
    """Close the database connection at the end of a request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    db_path = DATABASE
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        PRAGMA foreign_keys = ON;

        -- Users table: authentication
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- PDFs table: stored as BLOBs, linked to user and topic
        CREATE TABLE IF NOT EXISTS pdfs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            topic TEXT NOT NULL,
            filename TEXT NOT NULL,
            content BLOB NOT NULL,
            extracted_text TEXT,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Quizzes: one record per quiz generation event
        CREATE TABLE IF NOT EXISTS quizzes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pdf_id INTEGER NOT NULL REFERENCES pdfs(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            topic TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Quiz questions: MCQs stored per quiz
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
            question_text TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_option TEXT NOT NULL  -- 'A', 'B', 'C', or 'D'
        );

        -- Attempts: each quiz attempt = one memory event
        -- simulated_time_days: the simulated "day" this attempt was taken
        -- score_pct: 0.0 to 1.0 (fraction correct)
        -- Attempts are NEVER deleted or modified after creation
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id INTEGER NOT NULL REFERENCES quizzes(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            topic TEXT NOT NULL,
            simulated_time_days REAL NOT NULL,
            score_pct REAL NOT NULL,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Per-question answers for each attempt
        CREATE TABLE IF NOT EXISTS attempt_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL REFERENCES attempts(id),
            question_id INTEGER NOT NULL REFERENCES quiz_questions(id),
            selected_option TEXT,
            is_correct INTEGER NOT NULL DEFAULT 0
        );

        -- Decay segments: piecewise forgetting curve history
        -- Each segment: R(t) = r0 * exp(-lambda_val * (t - t0))
        -- Segments are IMMUTABLE — never update, only insert
        CREATE TABLE IF NOT EXISTS decay_segments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            attempt_id INTEGER NOT NULL REFERENCES attempts(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            topic TEXT NOT NULL,
            t0 REAL NOT NULL,         -- Start time (simulated days)
            r0 REAL NOT NULL,         -- Initial retention at t0 (0.0 to 1.0)
            lambda_val REAL NOT NULL, -- Decay rate
            t_end REAL,               -- End time (NULL = still active segment)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Learned parameters: ML-updated λ and R₀ boost per user+topic
        CREATE TABLE IF NOT EXISTS learned_params (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            topic TEXT NOT NULL,
            learned_lambda REAL NOT NULL DEFAULT 0.1,
            learned_r0_boost REAL NOT NULL DEFAULT 0.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, topic)
        );
    """)
    conn.commit()
    conn.close()
    print(f"[DB] Database initialized at {db_path}")
