import sqlite3
import urllib.parse

import pytest

import cci_index as cci


@pytest.mark.parametrize("raw,iso", [
    ("2024-03-05", "2024-03-05"), ("05/03/2024", "2024-03-05"),
    (" 05/03/2024 ", "2024-03-05"), ("5/3/2024", None), ("", None), (None, None),
])
def test_normalize_date(raw, iso):
    assert cci.normalize_date(raw) == iso


def test_parse_pdf_field_unescapes_entity_json():
    raw = ('[{&quot;title&quot;:&quot;Order&quot;,&quot;file_name&quot;:'
           '&quot;images\\/caseorders\\/en\\/order123.pdf&quot;}]')
    assert cci.parse_pdf_field(raw) == ["https://cci.gov.in/images/caseorders/en/order123.pdf"]


@pytest.mark.parametrize("raw", ["", None, "not json", "[{&quot;title&quot;:1}]"])
def test_parse_pdf_field_bad_input(raw):
    assert cci.parse_pdf_field(raw) == []


def test_build_datatable_url_paging_params():
    u = cci.build_datatable_url("https://cci.gov.in/x", 200, 100)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
    assert q["start"] == ["200"] and q["length"] == ["100"]
    assert q["columns[0][data]"] == [cci.DATATABLE_COLUMNS[0]]


def test_upsert_row_prefers_decision_date_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(cci, "DB_PATH", tmp_path / "cci.sqlite")
    con = cci.db()
    row = {"id": 7, "combination_no": "C-2024/01/1", "decision_date": "05/03/2024",
           "date_of_order": "2024-01-01", "party_name": "Buyer", "order_type": "31(1)"}
    cci.upsert_row(con, "approved", row)
    cci.upsert_row(con, "approved", dict(row, party_name="Buyer 2"))
    cci.upsert_row(con, "approved", {"combination_no": "no id"})        # skipped
    got = con.execute("SELECT order_id, order_date, acquirer FROM cci_orders").fetchall()
    assert got == [(7, "2024-03-05", "Buyer 2")]
