"""Unit tests for the shared upload validator (Gate 3 — Security §16)."""

import pytest

from app.core.uploads import (
    MAX_DOCUMENT_BYTES,
    MAX_IMAGE_BYTES,
    validate_upload,
)
from app.exceptions import ValidationException

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
_PDF = b"%PDF-1.4\n%..." + b"x" * 32
_CSV = b"a,b,c\n1,2,3\n"
_JSON = b'{"rows": [1, 2, 3]}'


class TestAcceptsValid:
    def test_png_returns_trusted_mime(self):
        assert validate_upload(filename="x.png", data=_PNG, category="image") == "image/png"

    def test_jpeg(self):
        assert validate_upload(filename="photo.JPG", data=_JPEG, category="image") == "image/jpeg"

    def test_pdf_document(self):
        assert validate_upload(filename="manual.pdf", data=_PDF, category="document") == "application/pdf"

    def test_csv_document(self):
        assert validate_upload(filename="feed.csv", data=_CSV, category="document") == "text/csv"

    def test_json_import(self):
        assert validate_upload(filename="data.json", data=_JSON, category="import") == "application/json"


class TestRejects:
    def test_empty(self):
        with pytest.raises(ValidationException):
            validate_upload(filename="x.png", data=b"", category="image")

    def test_oversize_image(self):
        with pytest.raises(ValidationException):
            validate_upload(filename="x.png", data=b"\x89PNG\r\n\x1a\n" + b"0" * MAX_IMAGE_BYTES,
                            category="image")

    def test_disallowed_extension(self):
        # An executable masquerading as an image upload.
        with pytest.raises(ValidationException):
            validate_upload(filename="evil.exe", data=b"MZ\x90\x00", category="image")

    def test_extension_content_mismatch(self):
        # Claims .png but the bytes are not a PNG — the core magic-byte defense.
        with pytest.raises(ValidationException):
            validate_upload(filename="fake.png", data=b"not really an image", category="image")

    def test_html_smuggled_as_csv_is_text_but_wrong_category_is_rejected(self):
        # A binary payload with NUL bytes cannot pass as text/csv.
        with pytest.raises(ValidationException):
            validate_upload(filename="x.csv", data=b"PK\x03\x04\x00\x00", category="import")

    def test_pdf_bytes_under_image_category_rejected(self):
        with pytest.raises(ValidationException):
            validate_upload(filename="x.pdf", data=_PDF, category="image")  # .pdf not an image ext

    def test_document_size_boundary_ok(self):
        data = b"%PDF-" + b"x" * (MAX_DOCUMENT_BYTES - 5)
        assert validate_upload(filename="big.pdf", data=data, category="document") == "application/pdf"
