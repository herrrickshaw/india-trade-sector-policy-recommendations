"""Pass 3 characterisation: quarterly-report HTML and state FDI/IEM main().

Golden values were captured from the pre-pass-3 code. Synthetic input, temp dirs only.
"""
from __future__ import annotations

import contextlib
import datetime
import hashlib
import io
import json
import types
from pathlib import Path

import build_quarterly_report as bqr
import build_state_fdi_iem as bsf

GOLDEN = json.loads((Path(__file__).parent / "golden_pass3.json").read_text())

SYNTH = {
    "fdi_cumulative_annexure_c": {"period": "Oct-2019 to Mar-2026", "url": "u", "rows": [
        {"state": "MAHARASHTRA", "usd_mn": 1000}, {"state": "Gujarat", "usd_mn": 500.5},
        {"state": "Ladakh", "usd_mn": 3}, {"state": "Grand Total", "usd_mn": 9999},
        {"state": "Daman and Diu", "usd_mn": 7}, {"state": "Assam", "usd_mn": 0.01}]},
    "iem_part_b": {"source_title": "B", "rows": [
        {"state": "Maharashtra", "year": 2020, "rs_cr": 100}, {"state": "Gujarat", "year": 2024, "rs_cr": 400},
        {"state": "Gujarat", "year": 2019, "rs_cr": 99999}, {"state": "Sikkim", "year": "Up to Dec 2025", "rs_cr": 5},
        {"state": "Orissa", "year": 2021, "rs_cr": 50}, {"state": "Assam", "year": 2022, "rs_cr": 20}]},
    "iem_part_a": {"rows": [{"state": "Gujarat", "year": 2024, "rs_cr": 200},
                            {"state": "Maharashtra", "year": 2020, "rs_cr": 0}]},
    "extraction_notes": ["n"],
}


def _run_state(tmp: Path, data: dict) -> dict:
    src = tmp / "src.json"
    src.write_text(json.dumps(data))
    (tmp / "data").mkdir(exist_ok=True)
    fake_dt = types.SimpleNamespace(date=types.SimpleNamespace(today=lambda: datetime.date(2026, 7, 1)))
    saved = (bsf.ROOT, bsf.SRC, bsf.datetime)
    bsf.ROOT, bsf.SRC, bsf.datetime = str(tmp), str(src), fake_dt
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            bsf.main()
    finally:
        bsf.ROOT, bsf.SRC, bsf.datetime = saved
    out = (tmp / "data" / "state_fdi_vs_iem_2026-07-01.json").read_text()
    return {"stdout": buf.getvalue().replace(str(tmp), "<T>"), "json": out}


def test_quarterly_html_golden():
    h = bqr.html()
    assert hashlib.sha256(h.encode()).hexdigest() == GOLDEN["html_sha256"]
    assert len(h) == GOLDEN["html_len"]


def test_state_fdi_main_golden(tmp_path):
    assert _run_state(tmp_path, SYNTH) == GOLDEN["state_main"]


def test_state_fdi_main_fy_fallback_golden(tmp_path):
    d = dict(SYNTH)
    d["fdi_cumulative_annexure_c"] = None
    d["fdi_fy_table"] = {"rows": [{"state": "Gujarat", "usd_mn": 5}, {"state": "Assam", "usd_mn": 1},
                                  {"state": "Gujarat", "usd_mn": 2}]}
    assert _run_state(tmp_path, d) == GOLDEN["state_main_fy"]
