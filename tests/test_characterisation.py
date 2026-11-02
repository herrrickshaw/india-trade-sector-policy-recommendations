"""Characterisation tests: outputs of the scripts must match golden.json,
which was captured from the pre-refactor code on `main`. No network access.
"""
from __future__ import annotations

import contextlib
import io
import json
import sqlite3
from pathlib import Path

import cci_index as cci
import pib_company_scan as pcs
import report_synthesizer as rs
import sebi_index as sebi

GOLDEN = json.loads((Path(__file__).parent / "golden.json").read_text())


def _compute(tmp: Path) -> dict:
    g = {}
    g["humanize"] = {k: rs.humanize(k) for k in ["fdi_pli-launch", "usd_total", "plain", "", "iem_part_b"]}
    g["title_from_stem"] = {k: rs.title_from_stem(k) for k in ["fdi_vs_pli_launch_2026_07_19", "master-report", "x"]}
    cells = [None, "a", 3, [1, "b", None], {"fdi_x": "y", "z": [1, 2]}, "x" * 400, [{"a": 1}, {"b": 2}]]
    g["stringify_cell"] = [rs.stringify_cell(c) for c in cells]
    rows = [{"a": 1, "b": 2}, {"b": 3, "c": 4}]
    g["table_columns"] = rs.table_columns(rows)
    data = {"purpose": "Why", "retrieved": "2026-07-19", "method": {"k": "v"},
            "scores": [{"sector": "Steel", "fdi": 1.5}, {"sector": "Pharma", "pli": 2}],
            "notes": ["one", "two"], "nested": {"inner": {"a": 1}, "list": [1, 2]}, "scalar": "hello"}
    g["flatten"] = rs.flatten_for_bullets(data["nested"])
    g["fallback_html"] = rs.render_fallback_html(data, "My Title")
    rs.build_docx(data, "My Title", tmp / "o.docx")
    rs.build_pptx(data, "My Title", tmp / "o.pptx")
    from docx import Document
    from pptx import Presentation
    d = Document(str(tmp / "o.docx"))
    g["docx_paras"] = [p.text for p in d.paragraphs]
    g["docx_tables"] = [[[c.text for c in r.cells] for r in t.rows] for t in d.tables]
    p = Presentation(str(tmp / "o.pptx"))
    g["pptx_titles"] = [s.shapes.title.text for s in p.slides]
    g["pptx_bodies"] = [[para.text for para in s.placeholders[1].text_frame.paragraphs] if len(s.placeholders) > 1 else [] for s in p.slides]
    (tmp / "d.json").write_text(json.dumps(data))
    out = tmp / "out"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        res = rs.synthesize_one(tmp / "d.json", None, {"docx", "pptx"}, out)
    g["synth_keys"] = sorted(res)
    g["synth_stdout"] = buf.getvalue().replace(str(out), "<OUT>")
    g["synth_files"] = sorted(x.name for x in out.iterdir())

    g["cci_parse_pdf"] = [cci.parse_pdf_field(x) for x in [None, "", "garbage",
        '[{&quot;title&quot;:&quot;Order&quot;,&quot;file_name&quot;:&quot;images\\/caseorders\\/en\\/o1.pdf&quot;}]']]
    g["cci_dates"] = [cci.normalize_date(x) for x in [None, "", "2026-01-02", "31/12/2025", "bad", " 01/02/2024 "]]
    g["cci_dt_url"] = cci.build_datatable_url("https://x.example/list?a=1", 100, 50)
    row = {"id": 7, "combination_no": "C-1", "order_type": "Under Section 31", "order_status": "Approved",
           "decision_date": "05/03/2026", "party_name": "Acme", "order_file_content": g["cci_parse_pdf"] and '[{&quot;file_name&quot;:&quot;a.pdf&quot;}]'}
    con = cci.db(); cci.upsert_row(con, "section31", row); cci.upsert_row(con, "section31", {"id": None}); con.commit()
    g["cci_rows"] = [list(r)[:11] for r in con.execute("SELECT * FROM cci_orders")]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cci.cmd_stats()
    g["cci_stats"] = buf.getvalue()

    g["sebi_dates"] = [sebi.normalize_date(x) for x in [None, "Jun 11, 2026", "bad", " Jan 02, 2025 "]]
    g["sebi_titles"] = [sebi.parse_title(t) for t in ["Foo Ltd - DRHP", "Foo - UDRHP2", "Foo - Addendum to DRHP", "Foo - Corrigendum to DRHP", "odd title"]]

    samples = [("2026-01-01", "Min", "Ministry signs MoU with Tata Steel Ltd and Acme Pvt. Ltd", "u"),
               ("2026-01-02", "Min", "CCI approves acquisition of Foo Limited by Bar Limited", "u"),
               ("2026-01-03", "Min", "TDB supports Xyz Technologies Pvt Ltd for indigenous drone", "u"),
               ("2026-01-04", "Min", "Nothing here", "u")]
    g["pcs_hits"] = [[fn.__name__, fn(*s)] for s in samples for fn in pcs.PATTERNS]
    g["pcs_cat"] = [pcs.categorize(n) for n in list(pcs.CATEGORY)[:3] + ["Zzz"]]
    # scan
    src = tmp / "src.sqlite"
    c = sqlite3.connect(src)
    c.execute("CREATE TABLE pib_items(id INTEGER, kind TEXT, date TEXT, ministry TEXT, title TEXT, url TEXT)")
    for i, s in enumerate(samples):
        c.execute("INSERT INTO pib_items VALUES (?,?,?,?,?,?)", (i, "release", s[0], s[1], s[2], s[3]))
    c.execute("INSERT INTO pib_items VALUES (99,'factsheet','2026-01-05','M','Foo Ltd','u')"); c.commit(); c.close()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        pcs.scan()
        pcs.cmd_stats()
    g["pcs_scan_out"] = buf.getvalue()
    o = sqlite3.connect(pcs.OUT_DB)
    g["pcs_mentions"] = sorted([list(r)[:10] for r in o.execute("SELECT * FROM mentions")], key=str)
    return json.loads(json.dumps(g, default=str, sort_keys=True))


def test_outputs_match_pre_refactor_golden(tmp_path, monkeypatch):
    monkeypatch.setattr(cci, "DB_PATH", tmp_path / "cci.sqlite")
    monkeypatch.setattr(pcs, "SRC_DB", tmp_path / "src.sqlite")
    monkeypatch.setattr(pcs, "OUT_DB", tmp_path / "out.sqlite")
    got = _compute(tmp_path)
    assert set(got) == set(GOLDEN)
    for key in GOLDEN:
        assert got[key] == GOLDEN[key], key
