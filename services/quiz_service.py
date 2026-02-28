"""
services/quiz_service.py
=========================
Handles quiz generation from PDF text using the Groq LLM API.

LLM DEPENDENCY (REQUIRED — NOT OPTIONAL):
------------------------------------------
This service uses the Groq SDK to generate multiple-choice questions.
- Provider: Groq (https://console.groq.com)
- Model: llama-3.1-8b-instant
- Requires: GROQ_API_KEY environment variable
- Install: pip install groq
- Offline mode: NOT supported

QUIZ RULES:
-----------
- Always multiple-choice (4 options: A, B, C, D)
- Generated FRESH for every attempt (not cached per PDF)
- Default: 5 questions per quiz
- Retries with fewer questions if JSON is truncated
"""

import os
import json
import re
from typing import List, Dict


GROQ_MODEL = "llama-3.1-8b-instant"
DEFAULT_NUM_QUESTIONS = 5


def _build_prompt(text: str, num_questions: int) -> str:
    """
    Build the prompt sent to the LLM for quiz generation.
    Keeps options short to avoid token limit truncation.
    """
    # Limit text to avoid prompt being too long
    truncated = text[:2000] if len(text) > 2000 else text

    return f"""Generate exactly {num_questions} multiple-choice quiz questions based on this text.

TEXT:
{truncated}

Rules:
- 4 options per question labeled A, B, C, D
- Keep each option under 8 words
- Output ONLY a valid JSON array, nothing else

[
  {{
    "question": "short question here?",
    "option_a": "short answer",
    "option_b": "short answer",
    "option_c": "short answer",
    "option_d": "short answer",
    "correct_option": "A"
  }}
]"""


def generate_quiz(pdf_text: str, num_questions: int = DEFAULT_NUM_QUESTIONS) -> List[Dict]:
    """
    Generate multiple-choice questions from PDF text via the Groq SDK.

    Retries with fewer questions if the response is truncated.

    REQUIRES: GROQ_API_KEY environment variable + `pip install groq`
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GROQ_API_KEY is not set. "
            "Set it with: export GROQ_API_KEY=your_key_here"
        )

    try:
        from groq import Groq
    except ImportError:
        raise ImportError("groq package is not installed. Run: pip install groq")

    client = Groq(api_key=api_key)

    # Try with requested count, then fall back to fewer questions if truncated
    for attempt_count in [num_questions, 3, 2]:
        try:
            raw_content = _call_api(client, pdf_text, attempt_count)
            questions = _parse_questions(raw_content, attempt_count)
            if questions:
                return questions
        except RuntimeError as e:
            if attempt_count == 2:
                raise  # Give up after final retry
            print(f"[WARN] Quiz generation with {attempt_count} questions failed, retrying with fewer... ({e})")
            continue

    raise RuntimeError("Quiz generation failed after all retries.")


def _call_api(client, pdf_text: str, num_questions: int) -> str:
    """
    Make a single API call to Groq and return the raw response string.

    Uses higher max_tokens to prevent mid-JSON truncation.
    """
    prompt = _build_prompt(pdf_text, num_questions)

    # Token budget: ~200 tokens per question is generous for short options
    max_tokens = max(1024, num_questions * 250)

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,      # Lower = more consistent JSON output
            max_tokens=max_tokens
        )
    except Exception as e:
        raise RuntimeError(f"Groq API call failed: {str(e)}")

    return response.choices[0].message.content


def _parse_questions(raw: str, expected: int) -> List[Dict]:
    """
    Parse the LLM's JSON response into a structured list of questions.

    Strips markdown fences. Attempts to recover a partial JSON array
    if the response was truncated.
    """
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

    # Try direct parse first
    try:
        questions = json.loads(cleaned)
        return _validate_questions(questions)
    except json.JSONDecodeError:
        pass

    # Attempt recovery: truncated JSON often ends mid-object.
    # Find the last complete {...} block and close the array.
    recovered = _recover_truncated_json(cleaned)
    if recovered:
        try:
            questions = json.loads(recovered)
            return _validate_questions(questions)
        except json.JSONDecodeError:
            pass

    raise RuntimeError(
        f"Failed to parse LLM response as JSON.\nRaw (first 300 chars): {raw[:300]}"
    )


def _recover_truncated_json(text: str) -> str:
    """
    Attempt to recover a valid JSON array from a truncated response.

    Strategy: find all complete {...} objects using brace matching,
    then wrap them in a valid array.
    """
    objects = []
    depth = 0
    start = None

    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start is not None:
                obj_str = text[start:i+1]
                try:
                    obj = json.loads(obj_str)
                    objects.append(obj)
                except json.JSONDecodeError:
                    pass
                start = None

    if objects:
        return json.dumps(objects)
    return ""


def _validate_questions(questions) -> List[Dict]:
    """
    Validate and normalise parsed question objects.
    Skips malformed entries rather than failing entirely.
    """
    if not isinstance(questions, list):
        raise RuntimeError(f"Expected JSON array, got {type(questions)}")

    required_keys = {"question", "option_a", "option_b", "option_c", "option_d", "correct_option"}
    validated = []

    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            continue
        if required_keys - set(q.keys()):
            print(f"[WARN] Question {i} missing keys — skipping")
            continue

        correct = str(q["correct_option"]).strip().upper()
        if correct not in ("A", "B", "C", "D"):
            correct = "A"

        validated.append({
            "question_text": str(q["question"]).strip(),
            "option_a": str(q["option_a"]).strip(),
            "option_b": str(q["option_b"]).strip(),
            "option_c": str(q["option_c"]).strip(),
            "option_d": str(q["option_d"]).strip(),
            "correct_option": correct
        })

    if not validated:
        raise RuntimeError("No valid questions found in response.")

    return validated


def save_quiz_to_db(db, pdf_id: int, user_id: int, topic: str, questions: List[Dict]) -> int:
    """Save a generated quiz and its questions to the database."""
    cursor = db.execute("""
        INSERT INTO quizzes (pdf_id, user_id, topic)
        VALUES (?, ?, ?)
    """, (pdf_id, user_id, topic))
    quiz_id = cursor.lastrowid

    for q in questions:
        db.execute("""
            INSERT INTO quiz_questions
                (quiz_id, question_text, option_a, option_b, option_c, option_d, correct_option)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            quiz_id,
            q["question_text"],
            q["option_a"],
            q["option_b"],
            q["option_c"],
            q["option_d"],
            q["correct_option"]
        ))

    db.commit()
    return quiz_id