"""scripts/build_quarterly_report.py, build_quarterly_series.py and build_compendium.py with WeasyPrint, Chrome and pypdf faked."""
import json
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest


class FakeWeasy:
    """Stand-in for the weasyprint module: records every HTML() and writes a marker PDF."""

    def __init__(self):
        self.calls = []
        outer = self

        class Doc:
            pages = [1, 2, 3]

            def __init__(self, html):
                self.html = html

            def write_pdf(self, path):
                Path(path).write_bytes(b"%PDF " + self.html[:40].encode())
                outer.calls.append(("write_pdf", str(path)))

        class HTML:
            def __init__(self, string=None, base_url=None):
                self.string, self.base_url = string, base_url
                outer.calls.append(("HTML", string, base_url))

            def render(self):
                return Doc(self.string)

            def write_pdf(self, path):
                Doc(self.string).write_pdf(path)
        self.HTML = HTML


@pytest.fixture
def weasy(monkeypatch):
    fake = FakeWeasy()
    mod = types.ModuleType("weasyprint")
    mod.HTML = fake.HTML
    monkeypatch.setitem(sys.modules, "weasyprint", mod)
    return fake


# ================================================================== build_quarterly_report
def test_quarterly_report_html_structure(load):
    Q = load("build_quarterly_report")
    h = Q.html()
    assert h.startswith("<!doctype html><html>") and h.rstrip().endswith("</html>")
    assert Q.EDITION in h and Q.SITE in h and "India Trade Watch<br>Quarterly" in h
    ids = re.findall(r'<section id="(s\d+b?)"', h)
    assert ids == ["s0", "s1", "s2", "s3", "s4", "s4b", "s5", "s6", "s7"]
    assert "<h2>Contents</h2>" in h and "A3 · Where the deep data lives" in h
    assert h.count("<section") == h.count("</section>")
    assert "{EDITION}" not in h and "{SITE}" not in h and "{CSS}" not in h                                  # every f-string field was filled


def test_quarterly_report_main_writes_pdf(load, repo, weasy, capsys):
    Q = load("build_quarterly_report")
    Q.main()
    assert [c[0] for c in weasy.calls] == ["HTML", "write_pdf"]
    kind, string, base = weasy.calls[0]
    assert base == str(repo) and string == Q.html()
    assert weasy.calls[1][1] == str(repo / "reports/published/India_Trade_Watch_Quarterly_2026Q2.pdf")
    assert capsys.readouterr().out.strip() == "India_Trade_Watch_Quarterly_2026Q2.pdf: 3 pages"
    assert Q.OUT == repo / "reports/published/India_Trade_Watch_Quarterly_2026Q2.pdf"


# ================================================================== build_quarterly_series
def test_series_years_are_well_formed(load):
    B = load("build_quarterly_series")
    fys = [y["fy"] for y in B.YEARS]
    assert len(fys) == 13 and fys[0] == "FY2014-15" and fys[-1].startswith("FY2026-27")
    assert len(set(fys)) == 13
    for y in B.YEARS:
        assert set(y) == {"fy", "era", "q", "anchors", "roster"}
        labels = [q for q, _ in y["q"]]
        assert 1 <= len(labels) <= 4 and labels == sorted(set(labels)) and set(labels) <= {"Q1", "Q2", "Q3", "Q4"}
        assert y["anchors"] and all(len(a) == 3 and all(a) for a in y["anchors"])
    # consecutive fiscal years
    starts = [int(f[2:6]) for f in fys]
    assert starts == list(range(2014, 2027))


def test_series_doc_renders_rows(load):
    B = load("build_quarterly_series")
    y = {"fy": "FY2099-00", "era": "Test era", "q": [("Q1", "launch <b>A</b>"), ("Q2", "launch B")],
         "anchors": [("Deficit", "-$1bn", "SRC")], "roster": "<b>Linkage:</b> x"}
    h = B.doc(y)
    assert "<h1>India Trade Watch — FY2099-00</h1>" in h and '<p class="era">Test era</p>' in h
    assert "<tr><td class='q'>Q1</td><td>launch <b>A</b></td></tr><tr><td class='q'>Q2</td><td>launch B</td></tr>" in h
    assert "<tr><td>Deficit</td><td class='n'>-$1bn</td><td class='src'>SRC</td></tr>" in h
    assert '<div class="roster"><b>Linkage:</b> x</div>' in h and B.SITE in h


def test_series_main_writes_one_pdf_per_year(load, repo, weasy, capsys):
    B = load("build_quarterly_series")
    B.main()
    outdir = repo / "reports/published/series"
    names = sorted(p.name for p in outdir.iterdir())
    assert len(names) == 13 and names[0] == "India_Trade_Watch_FY2014-15.pdf" and "India_Trade_Watch_FY2026-27.pdf" in names
    writes = [c[1] for c in weasy.calls if c[0] == "write_pdf"]
    assert writes == [str(outdir / f"India_Trade_Watch_{y['fy'].split(' ')[0]}.pdf") for y in B.YEARS]
    html_calls = [c for c in weasy.calls if c[0] == "HTML"]
    assert html_calls[0][1] == B.doc(B.YEARS[0]) and html_calls[0][2] is None
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "  India_Trade_Watch_FY2014-15.pdf" and out[-1] == f"13 documents in {outdir}"


# ================================================================== build_compendium
@pytest.fixture
def CP(load, repo, monkeypatch):
    (repo / "print/print.css").write_text("@page{size:A4}")
    real_mkdir = Path.mkdir

    def mkdir(self, *a, **k):
        if str(self).startswith("/tmp/build_top10"):               # the script's scratch dir: keep it inside the test sandbox
            self = repo / "tmp_build" / Path(str(self)).name
        return real_mkdir(self, *a, **k)
    monkeypatch.setattr(Path, "mkdir", mkdir)
    m = load("build_compendium")
    m.TMP = repo / "tmp_build"
    m.TMP.mkdir(parents=True, exist_ok=True)
    return m


def test_prepare_injects_css_counter_and_strips_scripts(CP):
    raw = '<html data-theme="dark" lang="en"><head><title>t</title><script src="x.js"></script></head><body><script>var a=1;</script><p>hi</p></body></html>'
    out = CP.prepare(raw, 5, "123")
    assert "<script" not in out and "var a=1" not in out
    assert out.count('data-theme="light"') == 1 and 'data-theme="dark"' not in out and 'lang="en"' in out
    assert "html{counter-reset: page 4}" in out and "@page{size:A4}" in out and "<span id='pgtotal'>123</span>" in out
    assert out.index("counter-reset") < out.index("</head>")


def test_prepare_without_head_prepends_and_without_theme_adds_one(CP):
    out = CP.prepare("<html><p>x</p></html>", 1, "?")
    assert out.startswith("<style>") and '<html data-theme="light">' in out and "counter-reset: page 0" in out
    two = CP.prepare('<html a="1"><html b="2"></head>', 2, "9")
    assert two.count('data-theme="light"') == 1                                # only the first <html> is touched


def test_dump_dom_runs_chrome_headless(CP, tmp_path, monkeypatch):
    seen = {}

    def run(cmd, capture_output, text, timeout):
        seen.update(cmd=cmd, capture=capture_output, text=text, timeout=timeout)
        return types.SimpleNamespace(stdout="<dom/>")
    monkeypatch.setattr(subprocess, "run", run)
    assert CP.dump_dom(tmp_path / "p.html") == "<dom/>"
    assert seen["cmd"][0] == CP.CHROME and "--headless" in seen["cmd"] and "--dump-dom" in seen["cmd"]
    assert "--virtual-time-budget=8000" in seen["cmd"] and seen["cmd"][-1] == f"file://{tmp_path / 'p.html'}"
    assert seen["timeout"] == 120 and seen["capture"] is True and seen["text"] is True


def test_cover_toc_lists_every_section_and_appendix(CP):
    entries = [("Alpha", 1), ("Beta", 12)]
    h = CP.cover_toc(entries, 40)
    assert "<tr><td>Alpha</td><td class='p'>1</td></tr><tr><td>Beta</td><td class='p'>12</td></tr>" in h
    assert "Appendix: FDI Pitch Deck (23 slides, landscape)</td><td class='p'>41</td>" in h
    assert "Compiled 19 July 2026 · 40 pages + appendix" in h


def test_master_html_renders_json_with_fallback_layout(CP, repo):
    (repo / "data").mkdir(exist_ok=True)
    (repo / "data/master_report_2026-07-19.json").write_text(json.dumps({"purpose": "P", "findings": [{"a": 1}]}))
    h = CP.master_html()
    assert "<h1>Master Report \u2014 Findings, Grades & Corrections</h1>" in h
    assert "<h2>Findings</h2>" in h and "<td>1</td>" in h and str(repo / "scripts") in sys.path


def test_render_and_n_pages(CP, repo, monkeypatch, weasy):
    out = repo / "o.pdf"
    CP.render("<p>x</p>", out)
    assert weasy.calls[0] == ("HTML", "<p>x</p>", str(repo / "charts") + "/") and out.exists()
    pypdf = types.ModuleType("pypdf")
    pypdf.PdfReader = lambda p: types.SimpleNamespace(pages=[0] * 7)
    monkeypatch.setitem(sys.modules, "pypdf", pypdf)
    assert CP.n_pages(out) == 7


class FakeWriter:
    instances = []

    def __init__(self):
        self.appended, self.outline = [], []
        FakeWriter.instances.append(self)

    def append(self, path, import_outline):
        self.appended.append((Path(path).name, import_outline))

    def add_outline_item(self, title, page):
        self.outline.append((title, page))

    def write(self, fh):
        fh.write(b"%PDF merged")


def test_main_two_pass_pagination_and_merge(CP, repo, monkeypatch, weasy, capsys):
    FakeWriter.instances.clear()
    monkeypatch.setattr(CP, "SECTIONS", [("First", "a"), ("Master", None), ("Third", "c")])
    monkeypatch.setattr(CP, "dump_dom", lambda p: f"<html>{Path(p).stem}</html>")
    monkeypatch.setattr(CP, "master_html", lambda: "<html>master</html>")
    page_counts = {"pass1_01.pdf": 3, "pass1_02.pdf": 2, "pass1_03.pdf": 4, "front.pdf": 2}
    deck = repo / "fdi_pitch/India_Trade_FDI_Pitch_Deck.pdf"
    deck.parent.mkdir(exist_ok=True)
    deck.write_bytes(b"%PDF deck")
    monkeypatch.setattr(CP, "DECK", deck)
    monkeypatch.setattr(CP, "OUT", repo / "reports/published/out.pdf")
    rendered = []
    monkeypatch.setattr(CP, "render", lambda html, out: (rendered.append((html, Path(out).name)), Path(out).write_bytes(b"x"))[0])
    monkeypatch.setattr(CP, "n_pages", lambda p: page_counts.get(Path(p).name, 5 if Path(p).name.startswith("final_") else 6 if Path(p).name == "out.pdf" else 10))
    pypdf = types.ModuleType("pypdf")
    pypdf.PdfWriter = FakeWriter
    pypdf.PdfReader = None
    monkeypatch.setitem(sys.modules, "pypdf", pypdf)
    CP.main()
    # pass 1 renders each raw section once with a placeholder total, pass 2 with real page offsets 1, 4, 6 and total 9
    names = [n for _, n in rendered]
    assert names == ["pass1_01.pdf", "pass1_02.pdf", "pass1_03.pdf", "final_00.pdf", "final_01.pdf", "final_02.pdf", "front.pdf"]
    assert "counter-reset: page 0" in rendered[0][0] and "<span id='pgtotal'>?</span>" in rendered[0][0]
    assert "counter-reset: page 0" in rendered[3][0] and "<span id='pgtotal'>9</span>" in rendered[3][0]
    assert "counter-reset: page 3" in rendered[4][0] and "counter-reset: page 5" in rendered[5][0]
    assert "<tr><td>First</td><td class='p'>1</td></tr><tr><td>Master</td><td class='p'>4</td></tr><tr><td>Third</td><td class='p'>6</td></tr>" in rendered[6][0]
    assert "9 pages + appendix" in rendered[6][0]
    w = FakeWriter.instances[0]
    assert w.appended == [("front.pdf", False), ("final_00.pdf", True), ("final_01.pdf", True), ("final_02.pdf", True), (deck.name, False)]
    assert w.outline == [("Cover & Contents", 0), ("First", 2), ("Master", 7), ("Third", 12), ("Appendix: FDI Pitch Deck", 17)]
    assert (repo / "reports/published/out.pdf").read_bytes() == b"%PDF merged"
    out = capsys.readouterr().out
    assert "pass1 First" in out and "  3p" in out and "out.pdf: 6 pages (2 front + 9 content + 10 deck)" in out
