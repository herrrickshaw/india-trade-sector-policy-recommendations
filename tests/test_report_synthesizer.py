"""scripts/report_synthesizer.py: JSON -> HTML/DOCX/PPTX/PDF report building (python-docx/python-pptx real; Chrome/pypdf/hallmark faked)."""
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest


@pytest.fixture
def R(load):
    return load("report_synthesizer")


# ------------------------------------------------------------------ vocabulary helpers
@pytest.mark.parametrize("key,expected", [
    ("fdi_inflow", "FDI Inflow"), ("hs-code_list", "HS Code List"), ("gdp", "GDP"), ("usd_bn", "USD Bn"),
    ("plain", "Plain"), ("aayog_view", "Aayog View"), ("niti_aayog", "NITI Aayog"), ("a__b", "A  B"),
    (123, "123"), ("MIXED_case", "Mixed Case"), ("", ""),
])
def test_humanize(R, key, expected):
    assert R.humanize(key) == expected


@pytest.mark.parametrize("stem,expected", [
    ("pli_report_card_2026_07_19", "PLI Report Card"),
    ("pli-report-card_2026_07_19", "PLI Report Card"),
    ("fdi_2026_07", "FDI 2026 07"),                           # only a full _YYYY_MM_DD suffix is stripped
    ("sector_scorecard", "Sector Scorecard"),
    ("x_2026_07_19_extra", "X 2026 07 19 Extra"),
])
def test_title_from_stem(R, stem, expected):
    assert R.title_from_stem(stem) == expected


def test_stringify_cell_scalars_and_truncation(R):
    assert R.stringify_cell(None) == "" and R.stringify_cell(True) == "True" and R.stringify_cell(3.5) == "3.5" and R.stringify_cell(0) == "0"
    assert R.stringify_cell("a" * 280) == "a" * 280                                    # exactly max_len: untouched
    assert R.stringify_cell("a" * 281) == "a" * 279 + "…"                            # one over: cut to max_len with ellipsis
    assert R.stringify_cell("ab   " + "c" * 10, max_len=5) == "ab\u2026"                # trailing spaces are stripped before the ellipsis
    assert R.stringify_cell("x" * 10, max_len=5) == "xxxx…"
    assert R.stringify_cell(b"raw") == "b'raw'"


def test_stringify_cell_containers(R):
    assert R.stringify_cell(["a", 1, None, 2.5]) == "a; 1; ; 2.5"
    assert R.stringify_cell([{"x": 1}, [2, 3]]) == "X: 1; 2; 3"
    assert R.stringify_cell({"fdi_in": 5, "n": {"a_b": [1, 2]}}) == "FDI In: 5; N: A B: 1; 2"
    assert R.stringify_cell(["z" * 200]) == "z" * 79 + "…"                          # scalar list elements cut at 80
    assert R.stringify_cell([{"k": "y" * 300}]) == "K: " + "y" * 59 + "…"           # dict value cut at 60 inside a 100-char element
    assert R.stringify_cell({}) == "" and R.stringify_cell([]) == ""


def test_list_predicates_and_columns(R):
    assert R.is_list_of_dicts([{"a": 1}]) and not R.is_list_of_dicts([]) and not R.is_list_of_dicts([{"a": 1}, 2]) and not R.is_list_of_dicts({"a": 1})
    assert R.is_list_of_scalars([1, "a", None, True, 1.5]) and not R.is_list_of_scalars([]) and not R.is_list_of_scalars([1, [2]]) and not R.is_list_of_scalars("abc")
    assert R.table_columns([{"b": 1, "a": 2}, {"a": 3, "c": 4}, {}]) == ["b", "a", "c"]
    assert R.table_columns([]) == []


# ------------------------------------------------------------------ chrome
def test_find_chrome_prefers_absolute_paths_then_path_lookup(R, monkeypatch):
    existing = {R.CHROME_CANDIDATES[1]}
    monkeypatch.setattr(R.os.path, "exists", lambda p: p in existing)
    monkeypatch.setattr(R.shutil, "which", lambda c: "/usr/bin/" + c if c == "chromium" else None)
    assert R.find_chrome() == R.CHROME_CANDIDATES[1]
    existing.clear()
    assert R.find_chrome() == "/usr/bin/chromium"
    monkeypatch.setattr(R.shutil, "which", lambda c: None)
    assert R.find_chrome() is None


def test_find_chrome_first_candidate_wins(R, monkeypatch):
    monkeypatch.setattr(R.os.path, "exists", lambda p: True)
    monkeypatch.setattr(R.shutil, "which", lambda c: "/bin/" + c)
    assert R.find_chrome() == R.CHROME_CANDIDATES[0]
    monkeypatch.setattr(R.os.path, "exists", lambda p: False)
    assert R.find_chrome() == "/bin/google-chrome"


def test_html_to_pdf_command(R, tmp_path, monkeypatch):
    seen = {}

    def run(cmd, check, capture_output):
        seen.update(cmd=cmd, check=check, capture=capture_output)
    monkeypatch.setattr(R.subprocess, "run", run)
    html = tmp_path / "in.html"
    html.write_text("x")
    out = R.html_to_pdf(html, tmp_path / "sub/dir/out.pdf", "/usr/bin/chrome")
    assert out == (tmp_path / "sub/dir/out.pdf").resolve() and out.parent.is_dir()
    cmd = seen["cmd"]
    assert cmd[0] == "/usr/bin/chrome" and cmd[1:4] == ["--headless", "--disable-gpu", "--no-sandbox"]
    assert f"--print-to-pdf={out}" in cmd and "--print-to-pdf-no-header" in cmd and "--virtual-time-budget=8000" in cmd
    assert cmd[-1] == f"file://{html.resolve()}" and seen["check"] is True and seen["capture"] is True


def test_report_pdf_pages(R, monkeypatch):
    mod = types.ModuleType("pypdf")
    mod.PdfReader = lambda p: types.SimpleNamespace(pages=[1, 2, 3])
    monkeypatch.setitem(sys.modules, "pypdf", mod)
    assert R.report_pdf_pages("x.pdf") == 3
    mod.PdfReader = lambda p: (_ for _ in ()).throw(ValueError("bad"))
    assert R.report_pdf_pages("x.pdf") is None
    monkeypatch.setitem(sys.modules, "pypdf", None)
    assert R.report_pdf_pages("x.pdf") is None


# ------------------------------------------------------------------ fallback html
DATA = {
    "purpose": "Explain the thing",
    "retrieved": "2026-07-19",
    "method": {"source": "PIB", "n": 3},
    "headline_numbers": [{"metric": "FDI", "value": 5, "note": "x"}, {"metric": "GDP", "extra": ["a", "b"]}],
    "key_points": ["one", "two", None],
    "mixed": [{"a": 1}, "scalar", ["x", "y"]],
    "nested": {"pli_scheme": {"outlay": 10, "items": ["p", "q"]}, "flag": True},
    "single": "just text",
    "number": 42,
}


def test_render_fallback_html_structure(R):
    h = R.render_fallback_html(DATA, "My Title")
    assert h.startswith("<!doctype html><html>") and h.rstrip().endswith("</body></html>")
    assert "<title>My Title</title>" in h and "<h1>My Title</h1>" in h
    assert "<p>Explain the thing</p>" in h
    assert "<p class='src'>Retrieved: 2026-07-19 &middot; Method: Source: PIB; N: 3</p>" in h
    assert "<h2>Headline Numbers</h2>" in h and "<th>Metric</th><th>Value</th><th>Note</th><th>Extra</th>" in h
    assert "<td>FDI</td><td>5</td><td>x</td><td></td>" in h and "<td>GDP</td><td></td><td></td><td>a; b</td>" in h
    assert "<ul><li>one</li><li>two</li><li></li></ul>" in h
    assert ("<h2>Nested</h2>\n<h3>PLI Scheme</h3>\n<h3>Outlay</h3>\n<p>10</p><h3>Items</h3>\n<ul><li>p</li><li>q</li></ul>"
            "<h3>Flag</h3>\n<p>True</p>") in h
    assert "<h2>Single</h2>\n<p>just text</p>" in h and "<h2>Number</h2>\n<p>42</p>" in h
    assert "<h2>Mixed</h2>\n<h3>A</h3>\n<p>1</p><p>scalar</p><ul><li>x</li><li>y</li></ul>" in h
    assert "<h2>Purpose</h2>" not in h and "<h2>Method</h2>" not in h and "<h2>Retrieved</h2>" not in h


def test_render_fallback_html_minimal(R):
    h = R.render_fallback_html({"x": 1}, "T")
    assert "class='src'" not in h and "<p>" in h
    h = R.render_fallback_html({"purpose": 5, "retrieved": "r"}, "T")
    assert "<p>5</p>" not in h and "Retrieved: r" in h and "Method" not in h
    h = R.render_fallback_html({"method": "m"}, "T")
    assert "<p class='src'>Method: m</p>" in h


def test_html_value_long_scalars_use_larger_limits(R):
    assert R._html_value("x" * 1000) == "<p>" + "x" * 1000 + "</p>"
    assert R._html_value("x" * 1001) == "<p>" + "x" * 999 + "…</p>"
    assert R._html_value(["y" * 501]) == "<ul><li>" + "y" * 499 + "…</li></ul>"


def test_html_section_level_caps_at_h6(R):
    assert R._html_section("k", 1, level=2).startswith("<h2>K</h2>")
    assert R._html_section("k", 1, level=9).startswith("<h6>K</h6>")


# ------------------------------------------------------------------ docx
def test_build_docx_roundtrip(R, tmp_path):
    from docx import Document
    out = R.build_docx(DATA, "My Title", tmp_path / "sub/out.docx")
    assert out == tmp_path / "sub/out.docx" and out.exists()
    doc = Document(str(out))
    heads = [(p.style.name, p.text) for p in doc.paragraphs if p.style.name.startswith(("Heading", "Title"))]
    assert heads[0] == ("Title", "My Title")
    assert ("Heading 2", "Headline Numbers") in heads and ("Heading 2", "Key Points") in heads
    assert ("Heading 3", "PLI Scheme") in heads and ("Heading 4", "Outlay") in heads and ("Heading 4", "A") in heads
    texts = [p.text for p in doc.paragraphs]
    assert "Explain the thing" in texts and "Retrieved: 2026-07-19 | Method: Source: PIB; N: 3" in texts
    meta = next(p for p in doc.paragraphs if p.text.startswith("Retrieved:"))
    assert meta.runs[0].italic is True and meta.runs[0].font.size.pt == 9
    bullets = [p.text for p in doc.paragraphs if p.style.name == "List Bullet"]
    assert bullets[:3] == ["one", "two", ""] and "p" in bullets and "q" in bullets
    t = doc.tables[0]
    assert [c.text for c in t.rows[0].cells] == ["Metric", "Value", "Note", "Extra"]
    assert [c.text for c in t.rows[1].cells] == ["FDI", "5", "x", ""] and [c.text for c in t.rows[2].cells] == ["GDP", "", "", "a; b"]
    assert "just text" in texts and "42" in texts


def test_build_docx_minimal_and_style_fallback(R, tmp_path, monkeypatch):
    from docx import Document
    out = R.build_docx({"only": 1}, "T", tmp_path / "o.docx")
    doc = Document(str(out))
    assert [p.text for p in doc.paragraphs][:3] == ["T", "Only", "1"]
    assert not any(p.text.startswith("Retrieved") for p in doc.paragraphs)
    # an unknown table style must not abort the build
    import docx.table

    def bad(self, v):
        if isinstance(v, str):
            raise KeyError("no style")
    monkeypatch.setattr(docx.table.Table, "style", property(docx.table.Table.style.fget, bad))
    out = R.build_docx({"rows": [{"a": 1}]}, "T", tmp_path / "o2.docx")
    assert [c.text for c in Document(str(out)).tables[0].rows[1].cells] == ["1"]


def test_docx_truncates_cells_and_text(R, tmp_path):
    from docx import Document
    out = R.build_docx({"rows": [{"a": "x" * 300}], "txt": "y" * 2001, "lst": ["z" * 1001]}, "T", tmp_path / "o.docx")
    doc = Document(str(out))
    assert doc.tables[0].rows[1].cells[0].text == "x" * 279 + "…"
    texts = [p.text for p in doc.paragraphs]
    assert "y" * 1999 + "…" in texts and "z" * 999 + "…" in texts


# ------------------------------------------------------------------ pptx bullets
def test_flatten_for_bullets_shapes(R):
    rows = [{"name": "Alpha", "fdi_in": 5, "tags": ["a", "b"]}, {"name": "Beta"}]
    assert R.flatten_for_bullets(rows) == [(0, "Alpha"), (1, "FDI In: 5"), (1, "Tags: a; b"), (0, "Beta")]
    assert R.flatten_for_bullets(["a", "b"]) == [(0, "a"), (0, "b")]
    assert R.flatten_for_bullets({"k": 1, "sub": {"x": [1, 2]}}) == [(0, "K: 1"), (0, "Sub"), (1, "X"), (2, "1"), (2, "2")]
    assert R.flatten_for_bullets("text") == [(0, "text")]
    assert R.flatten_for_bullets([["a"], ["b"]]) == [(0, "a"), (0, "b")]
    assert R.flatten_for_bullets({"k": 1}, depth=2) == [(2, "K: 1")]
    assert R.flatten_for_bullets([]) == []


def test_flatten_for_bullets_nested_dict_indents(R):
    got = R.flatten_for_bullets({"k": 1, "sub": {"x": 2, "deeper": {"y": 3}}})
    assert got == [(0, "K: 1"), (0, "Sub"), (1, "X: 2"), (1, "Deeper"), (2, "Y: 3")]


def test_flatten_for_bullets_budget_truncates(R):
    items = [f"item{i:03d}" + "x" * 90 for i in range(30)]             # ~96 chars each
    got = R.flatten_for_bullets(items, max_chars=1300)
    assert got[-1] == (0, "… (truncated — see the PDF/DOCX report for full detail)")
    assert 13 <= len(got) - 1 <= 15
    total = sum(len(t) for _, t in got[:-1])
    assert total >= 1300 and total - len(got[-2][1]) < 1300             # stopped right after the budget ran out
    short = R.flatten_for_bullets(["a", "b"], max_chars=1300)
    assert short == [(0, "a"), (0, "b")]
    assert R.flatten_for_bullets(["abc"], max_chars=3)[-1][1].startswith("…")      # budget exactly used up still flags truncation
    assert R.flatten_for_bullets(["abc"], max_chars=4) == [(0, "abc")]


def test_flatten_long_text_cut_to_220(R):
    assert R.flatten_for_bullets(["q" * 300]) == [(0, "q" * 219 + "…")]
    got = R.flatten_for_bullets([{"label": "L", "nest": {"a": "n" * 400}}])
    assert got[1][0] == 1 and got[1][1].startswith("Nest: A: ") and len(got[1][1]) <= 150


# ------------------------------------------------------------------ pptx build
def test_build_pptx_roundtrip(R, tmp_path):
    from pptx import Presentation
    out = R.build_pptx(DATA, "My Title", tmp_path / "sub/o.pptx")
    assert out.exists()
    prs = Presentation(str(out))
    assert round(prs.slide_width.inches, 3) == 13.333 and round(prs.slide_height.inches, 3) == 7.5
    titles = [s.shapes.title.text for s in prs.slides]
    assert titles == ["My Title", "Headline Numbers", "Key Points", "Mixed", "Nested", "Single", "Number"]
    assert prs.slides[0].placeholders[1].text == "Explain the thing"
    s1 = prs.slides[1].placeholders[1].text_frame
    assert [p.text for p in s1.paragraphs][:3] == ["FDI", "Metric: FDI" if False else "Value: 5", "Note: x"]
    assert s1.paragraphs[0].level == 0 and s1.paragraphs[1].level == 1
    assert s1.paragraphs[0].font.size.pt == 18 and s1.paragraphs[1].font.size.pt == 16
    single = prs.slides[5].placeholders[1].text_frame
    assert [p.text for p in single.paragraphs] == ["just text"]
    assert [p.text for p in prs.slides[6].placeholders[1].text_frame.paragraphs] == ["42"]


def test_build_pptx_title_only_and_empty_values(R, tmp_path):
    from pptx import Presentation
    out = R.build_pptx({"empty": [], "blank": None}, "T", tmp_path / "o.pptx")
    prs = Presentation(str(out))
    assert [s.shapes.title.text for s in prs.slides] == ["T", "Empty", "Blank"]
    assert prs.slides[0].placeholders[1].text == ""                     # no purpose -> subtitle untouched
    assert [p.text for p in prs.slides[1].placeholders[1].text_frame.paragraphs] == [""]     # empty value still gets one blank bullet


def test_build_pptx_font_size_floor_and_level_cap(R, tmp_path):
    from pptx import Presentation
    deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": 1}}}}}}}
    out = R.build_pptx({"deep": deep}, "T", tmp_path / "o.pptx")
    ps = list(Presentation(str(out)).slides[1].placeholders[1].text_frame.paragraphs)
    assert max(p.level for p in ps) == 4 and min(p.font.size.pt for p in ps) == 11
    assert ps[0].font.size.pt == 18


# ------------------------------------------------------------------ synthesize_one
@pytest.fixture
def jfile(tmp_path):
    p = tmp_path / "in/pli_report_card_2026_07_19.json"
    p.parent.mkdir()
    p.write_text(json.dumps(DATA))
    return p


def patch_pdf(R, monkeypatch, chrome="/usr/bin/chrome"):
    calls = []
    monkeypatch.setattr(R, "find_chrome", lambda: chrome)

    def h2p(html_path, out_pdf, chrome_path):
        calls.append((Path(html_path), Path(out_pdf), chrome_path))
        Path(out_pdf).write_bytes(b"%PDF")
        return Path(out_pdf)
    monkeypatch.setattr(R, "html_to_pdf", h2p)
    monkeypatch.setattr(R, "report_pdf_pages", lambda p: 4)
    return calls


def test_synthesize_one_all_formats_with_html(R, jfile, tmp_path, monkeypatch, capsys):
    calls = patch_pdf(R, monkeypatch)
    chart = tmp_path / "chart.html"
    chart.write_text("<html/>")
    res = R.synthesize_one(jfile, chart, {"pdf", "docx", "pptx"}, tmp_path / "out")
    assert set(res) == {"pdf", "docx", "pptx"}
    assert res["pdf"] == str(tmp_path / "out/pli_report_card_2026_07_19.pdf") and calls[0][0] == chart and calls[0][2] == "/usr/bin/chrome"
    assert Path(res["docx"]).exists() and Path(res["pptx"]).exists()
    out = capsys.readouterr().out
    assert "(4 pages)" in out and "[docx]" in out and "[pptx]" in out and "generic layout" not in out
    from docx import Document
    assert Document(res["docx"]).paragraphs[0].text == "PLI Report Card"          # default title from the file stem


def test_synthesize_one_fallback_html_and_title_override(R, jfile, tmp_path, monkeypatch, capsys):
    calls = patch_pdf(R, monkeypatch)
    captured = {}
    orig = R.html_to_pdf

    def spy(html_path, out_pdf, chrome):
        captured["html"] = Path(html_path).read_text()
        captured["existed"] = Path(html_path).exists()
        return orig(html_path, out_pdf, chrome)
    monkeypatch.setattr(R, "html_to_pdf", spy)
    res = R.synthesize_one(jfile, None, {"pdf"}, tmp_path / "out", title_override="Custom Title")
    assert "<h1>Custom Title</h1>" in captured["html"] and set(res) == {"pdf"}
    assert not Path(calls[0][0]).exists()                                         # temp html cleaned up
    assert "(generic layout — no --html given), 4 pages" in capsys.readouterr().out
    # html_path given but missing on disk -> fallback layout as well
    res = R.synthesize_one(jfile, tmp_path / "missing.html", {"pdf"}, tmp_path / "out")
    assert "pdf" in res and "<h1>PLI Report Card</h1>" in captured["html"]


def test_synthesize_one_pdf_page_count_optional(R, jfile, tmp_path, monkeypatch, capsys):
    patch_pdf(R, monkeypatch)
    monkeypatch.setattr(R, "report_pdf_pages", lambda p: None)
    chart = tmp_path / "c.html"
    chart.write_text("x")
    R.synthesize_one(jfile, chart, {"pdf"}, tmp_path / "out")
    assert "pages" not in capsys.readouterr().out.split("[pdf]")[1]


def test_synthesize_one_no_chrome_skips_pdf(R, jfile, tmp_path, monkeypatch, capsys):
    patch_pdf(R, monkeypatch, chrome=None)
    chart = tmp_path / "c.html"
    chart.write_text("x")
    assert R.synthesize_one(jfile, chart, {"pdf"}, tmp_path / "out") == {}
    assert R.synthesize_one(jfile, None, {"pdf"}, tmp_path / "out") == {}
    assert capsys.readouterr().err.count("SKIPPED — no Chrome/Chromium found") == 2


def test_synthesize_one_chrome_failure_is_reported(R, jfile, tmp_path, monkeypatch, capsys):
    patch_pdf(R, monkeypatch)

    def boom(*a):
        raise subprocess.CalledProcessError(1, ["chrome"])
    monkeypatch.setattr(R, "html_to_pdf", boom)
    res = R.synthesize_one(jfile, None, {"pdf", "docx"}, tmp_path / "out")
    assert set(res) == {"docx"} and "[pdf] FAILED" in capsys.readouterr().err


def test_synthesize_one_format_selection(R, jfile, tmp_path, monkeypatch):
    patch_pdf(R, monkeypatch)
    assert set(R.synthesize_one(jfile, None, {"pptx"}, tmp_path / "o1")) == {"pptx"}
    assert set(R.synthesize_one(jfile, None, {"docx"}, tmp_path / "o2")) == {"docx"}
    assert R.synthesize_one(jfile, None, set(), tmp_path / "o3") == {}


# ------------------------------------------------------------------ hallmark gate
def hallmark_module(monkeypatch, result=None, error=None, seen=None):
    mod = types.ModuleType("hallmark_report_integration")

    def validate(**kw):
        if seen is not None:
            seen.update(kw)
        if error:
            raise error
        return result
    mod.validate_and_publish_report = validate
    monkeypatch.setitem(sys.modules, "hallmark_report_integration", mod)


def reload_synth(load):
    for n in [n for n in sys.modules if n == "report_synthesizer"]:
        del sys.modules[n]
    return load("report_synthesizer")


def test_hallmark_unavailable_by_default(R):
    assert R.HALLMARK_AVAILABLE is False


@pytest.mark.parametrize("publishable,errors,marker", [(True, 0, "\u2705 "), (False, 2, "\u26a0\ufe0f  "), (False, 0, "\u2139\ufe0f  ")])
def test_hallmark_results_are_reported(load, jfile, tmp_path, monkeypatch, capsys, publishable, errors, marker):
    seen = {}
    res_in = {"publishable": publishable, "status": "ok", "violations": ["v1", "v2"], "severity_counts": {"error": errors}, "summary": "SUMMARY"}
    hallmark_module(monkeypatch, res_in, seen=seen)
    R = reload_synth(load)
    assert R.HALLMARK_AVAILABLE is True
    patch_pdf(R, monkeypatch)
    res = R.synthesize_one(jfile, None, {"docx"}, tmp_path / "out")
    assert res["validation"] == {"publishable": publishable, "status": "ok", "violations_count": 2, "severity_counts": {"error": errors}}
    assert f"  {marker}SUMMARY" in capsys.readouterr().out
    assert seen["report_name"] == "report_pli_report_card_2026_07_19" and seen["strict_mode"] is False and seen["on_warning"] == "alert"
    assert seen["expected_sections"] == ["Introduction", "Data", "Methodology", "Retrieved"]    # DATA has 'retrieved'
    assert "<h1>PLI Report Card</h1>" in seen["html_content"]


def test_hallmark_expected_sections_none_without_retrieved(load, tmp_path, monkeypatch):
    seen = {}
    hallmark_module(monkeypatch, {"publishable": True, "status": "ok", "violations": [], "severity_counts": {"error": 0}, "summary": "s"}, seen=seen)
    R = reload_synth(load)
    p = tmp_path / "d.json"
    p.write_text(json.dumps({"a": 1}))
    R.synthesize_one(p, None, {"docx"}, tmp_path / "o")
    assert seen["expected_sections"] is None


def test_hallmark_not_run_for_pptx_only(load, tmp_path, monkeypatch):
    seen = {}
    hallmark_module(monkeypatch, {}, seen=seen)
    R = reload_synth(load)
    p = tmp_path / "d.json"
    p.write_text(json.dumps({"a": 1}))
    assert "validation" not in R.synthesize_one(p, None, {"pptx"}, tmp_path / "o") and seen == {}


def test_hallmark_exception_is_recorded_not_raised(load, jfile, tmp_path, monkeypatch):
    hallmark_module(monkeypatch, error=RuntimeError("gate down"))
    R = reload_synth(load)
    res = R.synthesize_one(jfile, None, {"docx"}, tmp_path / "out")
    assert res["validation"] == {"status": "error", "message": "gate down"}


# ------------------------------------------------------------------ main
def run_main(R, monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["report_synthesizer.py", *argv])
    return R.main()


def test_main_single_file(R, jfile, tmp_path, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(R, "synthesize_one", lambda *a, **k: calls.append((a, k)) or {})
    run_main(R, monkeypatch, str(jfile), "--html", "c.html", "--formats", "PDF, docx,,", "--out-dir", "outdir")
    assert calls == [((str(jfile), "c.html", {"pdf", "docx"}, "outdir"), {})]
    assert "=== pli_report_card_2026_07_19 ===" in capsys.readouterr().out
    run_main(R, monkeypatch, str(jfile))
    assert calls[-1][0][2:] == ({"pdf", "docx", "pptx"}, "reports")


def test_main_rejects_bad_input(R, monkeypatch, capsys):
    with pytest.raises(SystemExit):
        run_main(R, monkeypatch, "x.json", "--formats", "pdf,xlsx")
    assert "unknown format(s): xlsx" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        run_main(R, monkeypatch)
    assert "provide a json_path, or use --manifest" in capsys.readouterr().err


def test_main_manifest_batch(R, tmp_path, monkeypatch, capsys):
    repo = tmp_path / "proj"
    (repo / "data").mkdir(parents=True)
    (repo / "data/a.json").write_text("{}")
    manifest = repo / "data/repo_manifest_x.json"
    manifest.write_text(json.dumps({"entries": [
        {"title": "Alpha", "data": ["data/a.json"], "chart": "charts/a.html"},
        {"title": "NoData", "data": []},
        {"title": "Missing", "data": ["data/missing.json"], "chart": "charts/m.html"},
        {"data": ["data/a.json"], "chart": "charts/readme.md"},
        {"title": "NoDataKey"},
    ]}))
    calls = []
    monkeypatch.setattr(R, "synthesize_one", lambda *a, **k: calls.append((a, k)) or {})
    run_main(R, monkeypatch, "--manifest", str(manifest), "--formats", "docx", "--out-dir", "o")
    assert len(calls) == 2
    (a1, k1), (a2, k2) = calls
    assert a1 == (repo / "data/a.json", repo / "charts/a.html", {"docx"}, "o") and k1 == {"title_override": "Alpha"}
    assert a2[1] is None and k2 == {"title_override": None}                  # non-html chart -> no html; no title -> None
    cap = capsys.readouterr()
    assert "=== Alpha ===" in cap.out and "=== NoData — no data JSON, skipping ===" in cap.out and "=== a ===" in cap.out
    assert f"MISSING: {repo / 'data/missing.json'}" in cap.err
