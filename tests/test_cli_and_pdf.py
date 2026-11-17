"""CLI smoke tests (no network) and the PDF rendering branch with Chrome mocked out."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import report_synthesizer as rs

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


@pytest.mark.parametrize("name", ["cci_index.py", "pib_company_scan.py", "report_synthesizer.py", "sebi_index.py"])
def test_cli_help_exits_zero(name):
    proc = subprocess.run([sys.executable, str(SCRIPTS / name), "--help"], capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0
    assert "usage" in proc.stdout.lower()


def test_render_pdf_skips_without_chrome(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(rs, "find_chrome", lambda: None)
    results = {}
    rs._render_pdf({"a": 1}, "T", None, "stem", tmp_path, results)
    assert results == {}
    assert "SKIPPED" in capsys.readouterr().err


def test_render_pdf_generic_layout_uses_fallback_html(monkeypatch, tmp_path, capsys):
    calls = []

    def fake_html_to_pdf(html_path, out_pdf, chrome):
        calls.append((Path(html_path).read_text(), out_pdf, chrome))

    monkeypatch.setattr(rs, "find_chrome", lambda: "chrome")
    monkeypatch.setattr(rs, "html_to_pdf", fake_html_to_pdf)
    monkeypatch.setattr(rs, "report_pdf_pages", lambda p: 3)
    results = {}
    rs._render_pdf({"a": 1}, "My Title", None, "stem", tmp_path, results)
    assert results["pdf"] == str(tmp_path / "stem.pdf")
    assert "My Title" in calls[0][0]
    assert "generic layout" in capsys.readouterr().out


def test_synthesize_one_json_roundtrip(tmp_path):
    src = tmp_path / "d_2026_01_01.json"
    src.write_text(json.dumps({"purpose": "p", "rows": [{"x": 1}]}))
    res = rs.synthesize_one(src, None, {"docx"}, tmp_path / "out")
    assert Path(res["docx"]).exists()
