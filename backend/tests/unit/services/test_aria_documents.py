"""
ARIA deterministic document understanding and retrieval.

The two properties that matter most: extraction reads structured files without a
model and classifies the table from its headers, and retrieval only ever returns
spans that are actually present in an uploaded document, each tagged with its
source — it never invents contents, and a query with no match returns nothing.
"""

from decimal import Decimal

from app.services import aria_documents as ad


class TestExtraction:
    def test_csv_extracts_table_and_kind(self):
        data = b"supplier,feed_type,bags,amount\nAgrovet,Layers Mash,10,25000\n"
        doc = ad.extract("purchases.csv", "text/csv", data)
        assert doc.deterministic is True
        assert doc.tables[0].kind == "feed_purchases"
        assert doc.tables[0].headers[0] == "supplier"
        assert doc.tables[0].row_count == 1

    def test_vaccination_schedule_detected(self):
        data = b"vaccine,age_days,dose\nNewcastle,7,1 drop\nGumboro,14,1 drop\n"
        doc = ad.extract("vac.csv", "text/csv", data)
        assert doc.tables[0].kind == "vaccination_schedule"

    def test_financial_detected(self):
        assert ad.detect_table_kind(["date", "item", "amount", "total"]) == "financial"

    def test_semicolon_delimiter_sniffed(self):
        data = b"item;qty;price\nfeed;10;500\n"
        doc = ad.extract("x.csv", "text/csv", data)
        assert doc.tables[0].headers == ["item", "qty", "price"]

    def test_txt_extracts_text(self):
        doc = ad.extract("notes.txt", "text/plain", b"Vaccinate on Monday.")
        assert doc.deterministic is True
        assert "Vaccinate" in doc.text

    def test_pdf_needs_ai(self):
        doc = ad.extract("manual.pdf", "application/pdf", b"%PDF-1.4")
        assert doc.deterministic is False
        assert "Gemini" in doc.note or "AI" in doc.note

    def test_parse_money(self):
        assert ad.parse_money("KES 25,000") == Decimal("25000")
        assert ad.parse_money("no number here") is None


class TestRetrieval:
    def _chunks(self):
        text = (
            "Newcastle vaccination should be given at day 7 via eye drop.\n"
            "Gumboro vaccine is given at day 14.\n"
            "Feed layers mash at 120 grams per bird per day.\n"
        )
        return ad.chunk_document("doc1", "manual.txt", text)

    def test_finds_relevant_span(self):
        cites = ad.retrieve("when do I give Newcastle vaccine", self._chunks())
        assert cites
        assert cites[0].filename == "manual.txt"
        assert "newcastle" in cites[0].snippet.lower()

    def test_cites_source(self):
        cites = ad.retrieve("layers mash grams", self._chunks())
        assert all(c.doc_id == "doc1" for c in cites)

    def test_no_match_returns_nothing(self):
        # Nothing about tractors is in the document — retrieval must not invent it.
        assert ad.retrieve("tractor engine oil", self._chunks()) == []

    def test_empty_query_returns_nothing(self):
        assert ad.retrieve("the a of", self._chunks()) == []

    def test_scores_descending(self):
        cites = ad.retrieve("vaccine day", self._chunks())
        scores = [c.score for c in cites]
        assert scores == sorted(scores, reverse=True)
