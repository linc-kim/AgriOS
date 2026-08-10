"""
Greena — Upload validation (Gate 3 — Security Standard §16).

A single, shared server-side defense for every upload endpoint. It enforces:

  * a size cap per category (bounded reads, so a huge upload can't exhaust memory),
  * an extension allowlist,
  * magic-byte (content-signature) verification — so a client cannot smuggle a
    file past validation by mislabeling its Content-Type or extension.

Text formats (csv/txt/json) carry no binary signature; they are validated as
NUL-free, UTF-8-decodable text. The function returns a **trusted MIME derived
from the verified content**, so callers stop trusting the client's content_type.

Uploaded bytes in Greena are processed in-memory (image → Gemini Vision, document
→ text extraction, import → row parsing) and are never written to a path the app
serves, so "non-executable storage" holds by construction — this module supplies
the remaining Security §16 controls.
"""

from __future__ import annotations

import os
from typing import Literal

from app.exceptions import ValidationException

# Per-category size caps.
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_IMPORT_BYTES = 16 * 1024 * 1024

Category = Literal["image", "document", "import"]

_MAX: dict[str, int] = {
    "image": MAX_IMAGE_BYTES,
    "document": MAX_DOCUMENT_BYTES,
    "import": MAX_IMPORT_BYTES,
}

# Extension → canonical (trusted) MIME, per category.
_IMAGE_EXT = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
}
_DOC_EXT = {
    ".csv": "text/csv", ".txt": "text/plain", ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_IMPORT_EXT = {".csv": "text/csv", ".json": "application/json", ".txt": "text/plain"}

_ALLOWED: dict[str, dict[str, str]] = {
    "image": _IMAGE_EXT, "document": _DOC_EXT, "import": _IMPORT_EXT,
}

_TEXT_EXT = {".csv", ".txt", ".json"}


def _matches_signature(data: bytes, ext: str) -> bool:
    """True if ``data`` begins with the magic bytes expected for ``ext``."""
    if ext in (".jpg", ".jpeg"):
        return data[:3] == b"\xff\xd8\xff"
    if ext == ".png":
        return data[:8] == b"\x89PNG\r\n\x1a\n"
    if ext == ".gif":
        return data[:6] in (b"GIF87a", b"GIF89a")
    if ext == ".webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if ext == ".pdf":
        return data[:5] == b"%PDF-"
    if ext in (".xlsx", ".docx"):
        # OOXML is a ZIP container.
        return data[:4] == b"PK\x03\x04"
    return False


def _is_utf8_text(data: bytes) -> bool:
    """NUL-free and decodable as UTF-8 — a conservative 'this is text' check."""
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _safe_ext(filename: str) -> str:
    """Lower-cased extension of the final path component (strips any directory)."""
    base = os.path.basename((filename or "").strip().replace("\\", "/").split("/")[-1])
    return os.path.splitext(base.lower())[1]


def validate_upload(*, filename: str, data: bytes, category: Category) -> str:
    """
    Validate an uploaded file's size, extension and content signature.

    Returns the trusted canonical MIME for the verified content.
    Raises ``ValidationException`` (HTTP 422) on any failure.
    """
    max_bytes = _MAX[category]
    if not data:
        raise ValidationException("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise ValidationException(f"File too large — {max_bytes // (1024 * 1024)} MB maximum.")

    ext = _safe_ext(filename)
    allowed = _ALLOWED[category]
    if ext not in allowed:
        raise ValidationException(
            f"Unsupported file type '{ext or 'unknown'}'. "
            f"Allowed: {', '.join(sorted(allowed))}."
        )

    if ext in _TEXT_EXT:
        if not _is_utf8_text(data):
            raise ValidationException("File content is not valid UTF-8 text for its extension.")
    elif not _matches_signature(data, ext):
        raise ValidationException(f"File content does not match its '{ext}' type.")

    return allowed[ext]
