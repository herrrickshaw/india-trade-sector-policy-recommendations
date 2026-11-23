"""scripts/pib_factsheets.py: listing/detail parsing, PDF text extraction fallbacks, markdown output and CLI (requests faked)."""
import sys
import types

import pytest


@pytest.fixture
def F(load, monkeypatch):
    m = load("pib_factsheets")
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    return m


class Resp:
    def __init__(self, text="", content=b"", status=200):
        self.text, self.content, self.status = text, content, status

    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")


def patch_get(F, monkeypatch, router):
    calls = []

    def get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        r = router(url)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(F.requests, "get", get)
    return calls


# ------------------------------------------------------------------ listing
LISTING = ('<a class="x" href="/FactsheetDetails.aspx?Id=150699&reg=3">Ethanol &amp; Biofuels</a>'
           '<a href="/FactsheetDetails.aspx?Id=150701">Newer</a>'
           '<a href="/FactsheetDetails.aspx?Id=150699">Duplicate id</a>'
           '<a href="/FactsheetDetails.aspx?Id=9">ab</a>'          # title shorter than 3 chars is not matched
           '<a href="/FactsheetDetails.aspx?Id=1000">Older one</a>')


def test_list_factsheets_dedups_and_sorts_newest_first(F, monkeypatch):
    calls = patch_get(F, monkeypatch, lambda url: Resp(LISTING))
    got = F.list_factsheets()
    assert [g["id"] for g in got] == ["150701", "150699", "1000"]
    assert got[1] == {"id": "150699", "title": "Ethanol & Biofuels", "url": "https://www.pib.gov.in/FactsheetDetails.aspx?Id=150699"}
    assert calls == [(F.LISTING, F.UA, 60)]


def test_get_raises_on_http_error(F, monkeypatch):
    patch_get(F, monkeypatch, lambda url: Resp("x", status=500))
    with pytest.raises(RuntimeError, match="HTTP 500"):
        F._get("http://x")


# ------------------------------------------------------------------ _strip_html
def test_strip_html(F):
    frag = ("<script>var x = 1;</script><style>p{}</style><h2>Title</h2><p>One&nbsp;&amp; two</p>"
            "line<br/>break<ul><li>a</li><li>b</li></ul><div>  spaced \t out  </div><tr><td>cell</td></tr>")
    assert F._strip_html(frag) == "Title\nOne & two\nline\nbreak a\nb\nspaced out\ncell"
    assert F._strip_html("") == "" and F._strip_html("<p></p>") == ""
    assert "var x" not in F._strip_html("<SCRIPT type='x'>var x</SCRIPT>text")


# ------------------------------------------------------------------ parse_factsheet
DETAIL = ('<html><meta name="og:title" content="Ethanol &amp; Biofuels"><div>Posted 05 MAR 2026 14:30 by PIB</div>'
          '<h2 class="pageHead big">Ethanol</h2><p>Body para one.</p><p>Body &amp; two.</p>'
          '<a href="https://pib.gov.in/docs/a.pdf?x=1">pdf</a><a href="http://x.in/b.PDF">pdf2</a><a href="/rel.pdf">rel</a>'
          '<a href="https://pib.gov.in/docs/a.pdf?x=1">dup</a>'
          '<a id="ContentPlaceHolder1_FeedbackLink">Feedback</a><p>after</p></html>')


def test_parse_factsheet_full(F, monkeypatch):
    calls = patch_get(F, monkeypatch, lambda url: Resp(DETAIL))
    fs = F.parse_factsheet("150699")
    assert calls[0][0] == "https://www.pib.gov.in/FactsheetDetails.aspx?Id=150699"
    assert fs["id"] == "150699" and fs["title"] == "Ethanol & Biofuels" and fs["date"] == "05 MAR 2026 14:30"
    assert fs["body"] == "Ethanol\nBody para one.\nBody & two.\npdf pdf2 rel dup"
    assert "after" not in fs["body"] and "Feedback" not in fs["body"]
    assert fs["pdf_urls"] == ["http://x.in/b.PDF", "https://pib.gov.in/docs/a.pdf?x=1"]       # sorted, de-duplicated, absolute only


def test_parse_factsheet_fallbacks(F, monkeypatch):
    page = '<h2 class="pageHead">  Heading Title </h2><p>text</p>'
    patch_get(F, monkeypatch, lambda url: Resp(page))
    fs = F.parse_factsheet("7")
    assert fs["title"] == "Heading Title" and fs["date"] == "" and fs["pdf_urls"] == []
    assert fs["body"] == "Heading Title\ntext"                         # no feedback marker: whole page is the body
    patch_get(F, monkeypatch, lambda url: Resp("<p>bare</p>"))
    fs = F.parse_factsheet("8")
    assert fs["title"] == "8" and fs["body"] == "bare"


# ------------------------------------------------------------------ pdf_text
class FakePdf:
    def __init__(self, pages):
        self.pages = [types.SimpleNamespace(extract_text=(lambda t=t: t)) for t in pages]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_pdfplumber(monkeypatch, pages=None, error=None):
    mod = types.ModuleType("pdfplumber")

    def open_(buf):
        if error:
            raise error
        return FakePdf(pages)
    mod.open = open_
    monkeypatch.setitem(sys.modules, "pdfplumber", mod)


def fake_ocr(monkeypatch, configured=True, result="OCR TEXT"):
    pkg = types.ModuleType("ocr")
    mod = types.ModuleType("ocr.unlimited_ocr")
    mod.is_configured = lambda: configured
    mod.ocr_pdf_bytes = lambda b: result
    monkeypatch.setitem(sys.modules, "ocr", pkg)
    monkeypatch.setitem(sys.modules, "ocr.unlimited_ocr", mod)


def test_pdf_text_pdfplumber(F, monkeypatch):
    fake_pdfplumber(monkeypatch, ["page one", None, "page three"])
    assert F.pdf_text(b"%PDF") == ("page one\n\npage three", "pdfplumber")


def test_pdf_text_falls_back_to_ocr(F, monkeypatch):
    fake_pdfplumber(monkeypatch, [None, ""])
    fake_ocr(monkeypatch, configured=True, result="scanned text")
    assert F.pdf_text(b"x") == ("scanned text", "unlimited-ocr")
    fake_pdfplumber(monkeypatch, error=ValueError("corrupt"))
    assert F.pdf_text(b"x") == ("scanned text", "unlimited-ocr")


def test_pdf_text_no_text_no_ocr(F, monkeypatch):
    fake_pdfplumber(monkeypatch, [""])
    fake_ocr(monkeypatch, configured=False)
    assert F.pdf_text(b"x") == ("", "none (scanned PDF, UNLIMITED_OCR_URL not configured)")
    monkeypatch.setitem(sys.modules, "ocr", None)                       # import fails entirely
    assert F.pdf_text(b"x") == ("", "none (scanned PDF, UNLIMITED_OCR_URL not configured)")


def test_pdf_text_adds_home_to_syspath_once(F, monkeypatch, repo):
    fake_pdfplumber(monkeypatch, ["t"])
    monkeypatch.setattr(sys, "path", list(sys.path))
    fake_pdfplumber(monkeypatch, [""])
    monkeypatch.setitem(sys.modules, "ocr", None)
    home = str(repo / "_home")
    F.pdf_text(b"x")
    F.pdf_text(b"x")
    assert sys.path.count(home) == 1


# ------------------------------------------------------------------ write_markdown
FS = {"id": "150699", "title": "Ethanol & Biofuels!", "date": "05 MAR 2026 14:30", "body": "Body text",
      "pdf_urls": ["https://pib.gov.in/docs/a.pdf", "https://pib.gov.in/docs/b.pdf"]}


def test_write_markdown_without_pdfs(F, tmp_path, monkeypatch):
    patch_get(F, monkeypatch, lambda url: pytest.fail("no download expected"))
    p = F.write_markdown(FS, tmp_path, with_pdfs=False)
    assert p.name == "150699_ethanol-biofuels.md"
    assert p.read_text() == ("# Ethanol & Biofuels!\n\n"
                             "Source: https://www.pib.gov.in/FactsheetDetails.aspx?Id=150699  \nPublished: 05 MAR 2026 14:30\n\n"
                             "## Page body\n\nBody text\n")


def test_write_markdown_slug_edge_cases(F, tmp_path):
    fs = dict(FS, title="!!!", date="")
    p = F.write_markdown(fs, tmp_path, with_pdfs=False)
    assert p.name == "150699_150699.md" and "Published" not in p.read_text()
    fs = dict(FS, title="A" * 100)
    assert F.write_markdown(fs, tmp_path, with_pdfs=False).name == "150699_" + "a" * 60 + ".md"
    fs = dict(FS, title="Spaces   and--dashes__x")
    assert F.write_markdown(fs, tmp_path, with_pdfs=False).name == "150699_spaces-and-dashes-x.md"


def test_write_markdown_with_pdfs(F, tmp_path, monkeypatch):
    def router(url):
        if url.endswith("a.pdf"):
            return Resp(content=b"%PDF-a")
        return RuntimeError("boom")
    calls = patch_get(F, monkeypatch, router)
    monkeypatch.setattr(F, "pdf_text", lambda b: ("extracted text", "pdfplumber") if b == b"%PDF-a" else pytest.fail("unexpected"))
    text = F.write_markdown(FS, tmp_path, with_pdfs=True).read_text()
    assert [c[2] for c in calls] == [120, 120]
    assert "## Attachment: [a.pdf](https://pib.gov.in/docs/a.pdf)  \n_extracted via pdfplumber_\n\nextracted text" in text
    assert "## Attachment: [b.pdf](https://pib.gov.in/docs/b.pdf)  \n_extracted via download failed: boom_\n\n_(no text extracted)_" in text


def test_write_markdown_pdf_without_text(F, tmp_path, monkeypatch):
    patch_get(F, monkeypatch, lambda url: Resp(content=b"x"))
    monkeypatch.setattr(F, "pdf_text", lambda b: ("", "none"))
    text = F.write_markdown(dict(FS, pdf_urls=["https://h/c.pdf"]), tmp_path, with_pdfs=True).read_text()
    assert "_extracted via none_\n\n_(no text extracted)_" in text


# ------------------------------------------------------------------ main
def run_main(F, monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["pib_factsheets.py", *argv])
    return F.main()


def test_main_single_id(F, tmp_path, monkeypatch, capsys):
    out = tmp_path / "out"
    monkeypatch.setattr(F, "parse_factsheet", lambda fid: dict(FS, id=fid))
    written = []
    monkeypatch.setattr(F, "write_markdown", lambda fs, d, with_pdfs: written.append(with_pdfs) or (d / f"{fs['id']}.md"))
    assert run_main(F, monkeypatch, "--id", "55", "--out", str(out), "--no-pdfs") == 0
    assert written == [False]
    text = (out / "INDEX.md").read_text()
    assert text == "# PIB factsheets\n\n| Id | Title | PDFs | File |\n|---|---|---|---|\n| 55 | Ethanol & Biofuels! | 2 | 55.md |\n"
    o = capsys.readouterr().out
    assert "55  Ethanol & Biofuels!  (2 PDFs) ->" in o and o.strip().endswith("INDEX.md (1 factsheets)")


def test_main_all_listing_with_pdfs_and_sleep(F, tmp_path, monkeypatch, capsys):
    sleeps = []
    monkeypatch.setattr(F.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(F, "list_factsheets", lambda: [{"id": "2"}, {"id": "1"}])
    monkeypatch.setattr(F, "parse_factsheet", lambda fid: dict(FS, id=fid, pdf_urls=[]))
    written = []
    monkeypatch.setattr(F, "write_markdown", lambda fs, d, with_pdfs: written.append(with_pdfs) or (d / f"{fs['id']}.md"))
    run_main(F, monkeypatch, "--out", str(tmp_path / "o"), "--sleep", "0.25")
    assert written == [True, True] and sleeps == [0.25, 0.25]
    rows = (tmp_path / "o/INDEX.md").read_text().splitlines()[4:]
    assert rows == ["| 2 | Ethanol & Biofuels! | 0 | 2.md |", "| 1 | Ethanol & Biofuels! | 0 | 1.md |"]
    assert "(2 factsheets)" in capsys.readouterr().out
