"""scripts/pib_idex_birac_body_scan.py: company-name cleanup/extraction, cached body fetch and the end-to-end CSV build."""
import csv
import sqlite3
import sys
import urllib.request

import pytest


@pytest.fixture
def B(load, monkeypatch):
    m = load("pib_idex_birac_body_scan")
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    return m


class Resp:
    def __init__(self, text):
        self.b = text.encode()

    def read(self):
        return self.b


# ------------------------------------------------------------------ clean_name / norm_key
@pytest.mark.parametrize("raw,expected", [
    ('"Zen Technologies Pvt Ltd,', "Zen Technologies Pvt Ltd"),
    ("“Zen Technologies Pvt Ltd.", "Zen Technologies Pvt Ltd"),
    ("CEO of Alpha Robotics Pvt Ltd", "Alpha Robotics Pvt Ltd"),
    ("Dr. Rao, Beta Labs Private Limited", "Beta Labs Private Limited"),
    ("Founder & CEO, Gamma Pvt. Ltd.", "Gamma Pvt. Ltd"),
    ("Managing Director Delta Systems Ltd", "Delta Systems Ltd"),
    ("Shri Epsilon Corporation", "Epsilon Corporation"),
    ("Acme Pvt Ltd", "Acme Pvt Ltd"),
    ("Chairman of Big Group of Zeta Ltd", "Zeta Ltd"),                  # last 'of' segment wins
    ("  Plain Co.  ", "Plain Co"),
])
def test_clean_name(B, raw, expected):
    assert B.clean_name(raw) == expected


def test_clean_name_comma_segments_pick_last_company_suffix(B):
    assert B.clean_name("Minister, Alpha Pvt Ltd, Beta Ltd, Gamma") == "Beta Ltd"
    assert B.clean_name("No, Suffix, Here") == "No, Suffix, Here"


def test_norm_key(B):
    assert B.norm_key("Beta Technologies Private Limited") == "beta technologies pvt ltd"
    assert B.norm_key("Beta Technologies Pvt Ltd") == "beta technologies pvt ltd"
    assert B.norm_key("Beta Technologies Pvt. Ltd") == "beta technologies pvt ltd"
    assert B.norm_key("AlphaPvt Ltd") == "alpha pvt ltd"                  # glued suffix split
    assert B.norm_key("BetaTechnologies Pvt Ltd") == "beta technologies pvt ltd"
    assert B.norm_key("Gamma    Ltd") == "gamma ltd"


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="pib_idex_birac_body_scan.py:136-138: `\\bltd\\.?\\b` cannot match a trailing 'Ltd.' at end of string, "
                          "so 'Delta Ltd.' and 'Delta Ltd' get different keys and are counted as two companies")
def test_norm_key_trailing_dot_equivalence(B):
    assert B.norm_key("Delta Ltd.") == B.norm_key("Delta Ltd")


# ------------------------------------------------------------------ extract_names
def test_extract_names_basic_and_blocklists(B):
    text = "\n".join([
        "Zen Technologies Pvt Ltd won the contract.",
        "Bharat Electronics Limited was also present",                 # BLOCK_EXACT
        "The Defence Minister Inc attended",                            # BLOCK_SUBSTR 'minister inc'
        "A Ltd is short",                                               # < 6 chars
        "CEO of Omega Robotics Pvt Ltd said",
    ])
    got = B.extract_names(text, None)
    assert {"Zen Technologies Pvt Ltd", "Omega Robotics Pvt Ltd"} <= got
    assert "Bharat Electronics Limited" not in got and not any("Minister" in n for n in got)
    assert "A Ltd" not in got and "Ltd" not in got


def test_extract_names_length_boundary(B):
    assert B.extract_names("deal with A Ltd today", None) == set()              # 5 chars: dropped
    assert B.extract_names("deal with Ab Ltd today", None) == {"Ab Ltd"}        # 6 chars: kept


def test_extract_names_splits_multi_company_phrases(B):
    got = B.extract_names("Alpha Pvt Ltd and Beta Pvt Ltd signed", None)
    assert "Alpha Pvt Ltd" in got and "Beta Pvt Ltd" in got
    assert not any(" and " in n for n in got)


def test_extract_names_lowercase_start_rejected(B):
    assert all(n[0].isupper() for n in B.extract_names("some text 123 Pvt Ltd here", None))
    assert B.extract_names("nothing to see", None) == set()


# ------------------------------------------------------------------ fetch_body
PAGE = ('<html><div id="PrDateTime">05 JUN 2022</div><p>First <b>para</b> &amp; Zen Technologies Pvt Ltd.</p>\n\n\n'
        '<p>Second</p><div class="print-icons">footer junk Foo Ltd</div></html>')


def test_fetch_body_downloads_and_caches(B, repo, monkeypatch):
    calls = []

    def urlopen(req, timeout=None):
        calls.append((req.full_url, timeout, req.get_header("User-agent")))
        return Resp(PAGE)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    body = B.fetch_body(123, "My Title")
    assert calls == [("https://www.pib.gov.in/PressReleasePage.aspx?PRID=123", 45, B.UA["User-Agent"])]
    assert body.startswith("My Title\n---\n") and "First para & Zen Technologies Pvt Ltd." in body
    assert "footer junk" not in body and "Second" in body
    assert (repo / "data/pib_idex_birac_bodies/123.txt").read_text(encoding="utf-8") == body
    assert B.fetch_body(123, "other") == body and len(calls) == 1                 # served from cache


def test_fetch_body_no_match_gives_empty_text(B, repo, monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: Resp("<html>nothing here</html>"))
    assert B.fetch_body(5, "T") == "T\n---\n"


# ------------------------------------------------------------------ main
def make_src(repo, rows):
    con = sqlite3.connect(repo / "data/pib_index.sqlite")
    con.execute("CREATE TABLE pib_items(id INTEGER, kind TEXT, date TEXT, ministry TEXT, title TEXT, url TEXT)")
    con.executemany("INSERT INTO pib_items VALUES (?,?,?,?,?,?)", rows)
    con.commit()
    con.close()


SRC = [
    (1, "release", "2026-02-01", "MoD", "iDEX winners announced", "u1"),
    (2, "release", "2026-01-01", "DBT", "BIRAC supports startups", "u2"),
    (3, "release", "2026-03-01", "MoD", "Defence Innovation Organisation signs", "u3"),
    (4, "release", "2026-03-02", "X", "Unrelated release", "u4"),
    (5, "factsheet", "2026-03-03", "X", "iDEX factsheet", "u5"),
    (6, "release", "2026-04-01", "MoD", "Innovations for Defence Excellence round", "u6"),
]
BODIES = {1: "Zen Technologies Pvt Ltd and Alpha Pvt Ltd won", 2: "Zen Technologies Private Limited got grant", 3: "Beta Robotics Pvt Ltd signed", 6: "no company here"}


def page_for(prid):
    return f'<div id="PrDateTime">x</div><p>{BODIES[prid]}</p><div class="print-icons">'


def test_main_end_to_end(B, repo, monkeypatch, capsys):
    make_src(repo, SRC)
    seen = []

    def urlopen(req, timeout=None):
        prid = int(req.full_url.rsplit("=", 1)[1])
        seen.append(prid)
        if prid == 3:
            raise OSError("down")
        return Resp(page_for(prid))
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(sys, "argv", ["x"])
    B.main()
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "4 iDEX/BIRAC releases in scope"
    assert "  FAIL 3: down" in out
    assert seen == [2, 1, 3, 6]                                              # ordered by date; factsheet 5 and unrelated 4 never fetched
    with open(repo / "data/pib_idex_birac_body_startups_latest.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by = {r["company_name"]: r for r in rows}
    assert [r["company_name"] for r in rows] == sorted(by, key=str.lower)
    zen = by["Zen Technologies Private Limited"]                              # longest spelling wins as canonical
    assert zen["scheme"] == "BIRAC/iDEX" and zen["first_mentioned"] == "2026-01-01" and zen["n_source_releases"] == "2"
    assert zen["source_titles"] == "BIRAC supports startups || iDEX winners announced" and zen["source_urls"] == "u2 || u1"
    assert by["Alpha Pvt Ltd"]["scheme"] == "iDEX" and by["Alpha Pvt Ltd"]["n_source_releases"] == "1"
    assert "Beta Robotics Pvt Ltd" not in by                                  # its fetch failed
    assert out[-1].startswith("3 raw mentions -> 2 distinct companies -> ") and out[-1].endswith("pib_idex_birac_body_startups_latest.csv")


def test_main_no_fetch_uses_cache_only(B, repo, monkeypatch, capsys):
    make_src(repo, SRC)
    cache = repo / "data/pib_idex_birac_bodies"
    cache.mkdir()
    (cache / "1.txt").write_text("iDEX winners announced\n---\nCache Robotics Pvt Ltd won", encoding="utf-8")
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("network used"))
    monkeypatch.setattr(sys, "argv", ["x", "--no-fetch"])
    B.main()
    out = capsys.readouterr().out
    assert "1 raw mentions -> 1 distinct companies" in out
    with open(repo / "data/pib_idex_birac_body_startups_latest.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["company_name"] for r in rows] == ["Cache Robotics Pvt Ltd"] and rows[0]["scheme"] == "iDEX"
