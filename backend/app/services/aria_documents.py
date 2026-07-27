"""
ARIA — deterministic document understanding and retrieval.

Part 8 lets a farmer upload documents, but the router sends only the *structured*
ones here — CSV, TSV, Excel and plain text — precisely because they can be read
without a model. This module extracts their tables and text deterministically,
guesses what kind of table it is (feed purchases, a vaccination schedule, a
financial record) from its headers, and indexes the text for retrieval.

Two honesty rules shape it. Retrieval **cites its source and never invents
document contents**: a search returns spans that are actually present in an
uploaded file, each tagged with the file it came from, or it returns nothing.
And extraction is **lossless about uncertainty** — a column it cannot interpret
is kept as-is rather than coerced into a number it might get wrong.

It is pure apart from parsing the bytes it is handed (no database, no network),
so the retrieval scoring and table detection can be tested exhaustively.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


# ── Extraction ────────────────────────────────────────────────────────────────


@dataclass
class ExtractedTable:
    headers: list[str]
    rows: list[list[str]]
    #: One of: feed_purchases | vaccination_schedule | financial | inventory | generic
    kind: str

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass
class ExtractedDocument:
    filename: str
    text: str
    tables: list[ExtractedTable] = field(default_factory=list)
    #: True when a real parser ran; False means the format needs Gemini.
    deterministic: bool = True
    note: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.text.strip() and not self.tables


# Header keyword → table kind. First matching kind wins, in this order.
_KIND_SIGNATURES: list[tuple[str, tuple[str, ...]]] = [
    ("vaccination_schedule", ("vaccine", "vaccination", "chanjo", "dose", "age", "administered")),
    ("feed_purchases", ("feed", "mash", "pellets", "supplier", "bags", "chakula")),
    ("financial", ("amount", "total", "price", "cost", "revenue", "expense", "invoice", "kes", "ksh")),
    ("inventory", ("item", "stock", "quantity", "reorder", "unit", "sku")),
]


def detect_table_kind(headers: list[str]) -> str:
    joined = " ".join(h.lower() for h in headers)
    for kind, keywords in _KIND_SIGNATURES:
        if any(k in joined for k in keywords):
            return kind
    return "generic"


def _rows_to_table(rows: list[list[str]]) -> ExtractedTable | None:
    rows = [r for r in rows if any((c or "").strip() for c in r)]
    if not rows:
        return None
    headers = [(_clean(c)) for c in rows[0]]
    body = [[_clean(c) for c in r] for r in rows[1:]]
    return ExtractedTable(headers=headers, rows=body, kind=detect_table_kind(headers))


def _clean(cell) -> str:
    return str(cell if cell is not None else "").strip()


def extract_csv(filename: str, data: bytes, *, delimiter: str | None = None) -> ExtractedDocument:
    text = data.decode("utf-8", errors="replace")
    if delimiter is None:
        delimiter = "\t" if filename.lower().endswith(".tsv") else _sniff_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [list(r) for r in reader]
    table = _rows_to_table(rows)
    tables = [table] if table else []
    return ExtractedDocument(filename=filename, text=text, tables=tables)


def _sniff_delimiter(text: str) -> str:
    sample = text[:2048]
    counts = {d: sample.count(d) for d in (",", ";", "\t", "|")}
    return max(counts, key=counts.get) if any(counts.values()) else ","


def extract_xlsx(filename: str, data: bytes) -> ExtractedDocument:
    try:
        from openpyxl import load_workbook
    except Exception:  # pragma: no cover - openpyxl is a hard dependency
        return ExtractedDocument(filename=filename, text="", deterministic=False,
                                 note="Spreadsheet parser unavailable.")
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    tables: list[ExtractedTable] = []
    text_parts: list[str] = []
    for ws in wb.worksheets:
        rows = [[_clean(c) for c in row] for row in ws.iter_rows(values_only=True)]
        table = _rows_to_table(rows)
        if table:
            tables.append(table)
            text_parts.append(f"[{ws.title}] " + "; ".join(table.headers))
            for r in table.rows:
                text_parts.append(" ".join(r))
    wb.close()
    return ExtractedDocument(filename=filename, text="\n".join(text_parts), tables=tables)


def extract_text(filename: str, data: bytes) -> ExtractedDocument:
    return ExtractedDocument(filename=filename, text=data.decode("utf-8", errors="replace"))


def extract(filename: str, mime: str, data: bytes) -> ExtractedDocument:
    """
    Extract a document deterministically, or declare it needs a model.

    CSV/TSV/XLSX/TXT are parsed here. Anything else (PDF, DOCX, images) returns
    a `deterministic=False` document so the caller routes it to Gemini rather
    than pretending to have read it.
    """
    name = (filename or "").lower()
    m = (mime or "").lower()
    try:
        if name.endswith((".csv", ".tsv")) or "csv" in m:
            return extract_csv(filename, data)
        if name.endswith((".xlsx", ".xls")) or "spreadsheet" in m or "excel" in m:
            return extract_xlsx(filename, data)
        if name.endswith(".txt") or m == "text/plain":
            return extract_text(filename, data)
    except Exception as e:
        return ExtractedDocument(filename=filename, text="", deterministic=True,
                                 note=f"Could not parse: {e}")
    return ExtractedDocument(
        filename=filename, text="", deterministic=False,
        note="This format (PDF/DOCX/image) needs AI to read — routed to Gemini.",
    )


# ── Numeric helpers for downstream record extraction ─────────────────────────


_MONEY_RE = re.compile(r"(?:kes|ksh|sh)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)", re.IGNORECASE)


def parse_money(cell: str) -> Decimal | None:
    m = _MONEY_RE.search(cell or "")
    if not m:
        return None
    try:
        return Decimal(m.group(1).replace(",", ""))
    except InvalidOperation:
        return None


# ── Retrieval ─────────────────────────────────────────────────────────────────


@dataclass
class Chunk:
    """A retrievable span of an uploaded document."""

    doc_id: str
    filename: str
    text: str
    #: 0-based position within the source document, for stable ordering.
    index: int = 0


@dataclass
class Citation:
    doc_id: str
    filename: str
    snippet: str
    score: float
    index: int


_STOPWORDS = {
    "the", "a", "an", "is", "are", "of", "to", "for", "in", "on", "and", "or",
    "what", "how", "when", "why", "which", "who", "do", "does", "my", "me", "i",
    "ni", "na", "ya", "wa", "kwa",
}


def _terms(query: str) -> list[str]:
    words = re.findall(r"[a-z0-9']+", (query or "").lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 1]


def chunk_document(doc_id: str, filename: str, text: str, *, size: int = 400) -> list[Chunk]:
    """Split a document's text into overlapping-free chunks for retrieval."""
    text = (text or "").strip()
    if not text:
        return []
    # Prefer line boundaries; fall back to fixed windows.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    chunks: list[Chunk] = []
    buf = ""
    idx = 0
    for ln in lines:
        if len(buf) + len(ln) + 1 > size and buf:
            chunks.append(Chunk(doc_id, filename, buf.strip(), idx))
            idx += 1
            buf = ""
        buf += ln + "\n"
    if buf.strip():
        chunks.append(Chunk(doc_id, filename, buf.strip(), idx))
    return chunks


def retrieve(query: str, chunks: list[Chunk], *, limit: int = 5) -> list[Citation]:
    """
    Keyword retrieval with citations.

    Scores each chunk by how many query terms it contains (term frequency,
    length-normalised), and returns the best spans tagged with their source
    file. A chunk with no query term scores zero and is never returned — so
    ARIA can only ever cite text that is actually in an uploaded document.
    """
    terms = _terms(query)
    if not terms:
        return []
    scored: list[Citation] = []
    for c in chunks:
        low = c.text.lower()
        hits = sum(low.count(t) for t in terms)
        if hits == 0:
            continue
        distinct = sum(1 for t in terms if t in low)
        score = distinct + hits / (1 + len(c.text) / 200)
        scored.append(Citation(
            doc_id=c.doc_id, filename=c.filename,
            snippet=_snippet(c.text, terms), score=round(score, 3), index=c.index,
        ))
    scored.sort(key=lambda x: (-x.score, x.filename, x.index))
    return scored[:limit]


def _snippet(text: str, terms: list[str], *, width: int = 160) -> str:
    low = text.lower()
    pos = min((low.find(t) for t in terms if t in low), default=-1)
    if pos < 0:
        return text[:width].strip()
    start = max(0, pos - width // 3)
    end = min(len(text), start + width)
    snippet = text[start:end].strip()
    return ("…" if start > 0 else "") + snippet + ("…" if end < len(text) else "")
