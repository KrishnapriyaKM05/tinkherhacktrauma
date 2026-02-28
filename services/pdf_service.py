"""
services/pdf_service.py
========================
Handles PDF upload, storage, and text extraction.

SECURITY GUARANTEES:
--------------------
- PDFs are strictly scoped to users
- Ownership is enforced on every read
- No raw BLOBs are exposed unintentionally
"""

import io
from typing import Optional, Tuple


# -------------------------
# PDF TEXT EXTRACTION
# -------------------------

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract plain text from PDF binary data using pypdf.

    Args:
        pdf_bytes: Raw PDF file content as bytes

    Returns:
        Extracted text as a single string

    Raises:
        ImportError: If pypdf is not installed
        RuntimeError: If the PDF cannot be read
    """
    if not pdf_bytes:
        return ""

    try:
        from pypdf import PdfReader
    except ImportError:
        raise ImportError("pypdf is required. Install it with: pip install pypdf")

    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        pages = []

        for page in reader.pages:
            try:
                text = page.extract_text()
                if text:
                    pages.append(text.strip())
            except Exception:
                # Skip unreadable pages, do not fail whole PDF
                continue

        return "\n\n".join(pages)

    except Exception as e:
        raise RuntimeError(f"Failed to extract text from PDF: {e}")


# -------------------------
# PDF WRITE OPERATIONS
# -------------------------

def save_pdf(
    db,
    user_id: int,
    topic: str,
    filename: str,
    pdf_bytes: bytes
) -> Tuple[int, str]:
    """
    Store a PDF in the database and extract its text.

    SECURITY:
    ---------
    - PDF is always bound to the current user
    - Topic is normalised
    """

    if not user_id:
        raise PermissionError("Unauthenticated PDF upload")

    if not filename:
        raise ValueError("Filename is required")

    topic_clean = topic.strip()
    if not topic_clean:
        raise ValueError("Topic cannot be empty")

    extracted_text = extract_text_from_pdf(pdf_bytes)

    cursor = db.execute("""
        INSERT INTO pdfs (user_id, topic, filename, content, extracted_text)
        VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        topic_clean,
        filename,
        pdf_bytes,
        extracted_text
    ))

    db.commit()
    return cursor.lastrowid, extracted_text


# -------------------------
# PDF READ OPERATIONS
# -------------------------

def get_user_pdfs(db, user_id: int):
    """
    Retrieve all PDFs belonging to a user (metadata only).

    SECURITY:
    ---------
    - No BLOB content returned
    - Strict user scoping
    """
    if not user_id:
        return []

    rows = db.execute("""
        SELECT id, topic, filename, uploaded_at
        FROM pdfs
        WHERE user_id = ?
        ORDER BY uploaded_at DESC
    """, (user_id,)).fetchall()

    return [dict(row) for row in rows]


def get_pdf_text(db, pdf_id: int, user_id: int) -> Optional[str]:
    """
    Retrieve extracted text for a specific PDF (access-controlled).

    SECURITY:
    ---------
    - Enforces PDF ownership
    - Returns None if unauthorized or missing
    """

    if not user_id or not pdf_id:
        return None

    row = db.execute("""
        SELECT extracted_text
        FROM pdfs
        WHERE id = ? AND user_id = ?
    """, (pdf_id, user_id)).fetchone()

    return row["extracted_text"] if row else None