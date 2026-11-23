"""scripts/pib_index.py: HTML parsing, the ASP.NET day-by-day indexer (fake opener), detail-page fill, sqlite store, CLI."""
import datetime as dt
import sqlite3
import sys
import urllib.parse

import pytest


@pytest.fixture
def P(load, monkeypatch):
    m = load("pib_index")
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    return m


class Resp:
    def __init__(self, b):
        self.b = b if isinstance(b, bytes) else b.encode()

    def read(self):
        return self.b


class Op:
    """Fake opener: router(req) -> str | Exception; records every request."""

    def __init__(self, router):
        self.router, self.reqs = router, []

    def open(self, req, timeout=None):
        self.reqs.append((req, timeout))
        r = self.router(req)
        if isinstance(r, Exception):
            raise r
        return Resp(r)


def day_page(ministries, shown="Monday, 5-January-2026"):
    body = ['<html><input id="__VIEWSTATE" value="VS1"><input id="__VIEWSTATEGENERATOR" value="GEN">'
            '<input id="__EVENTVALIDATION" value="EV"><span id="x" lblDate">%s<' % shown]
    for mn, items in ministries:
        body.append(f"<h3>{mn}</h3>")
        for prid, title in items:
            body.append(f"<li><a title='t' href='/PressReleseDetailm.aspx?PRID={prid}'>{title}</a></li>")
    return "".join(body)


# ------------------------------------------------------------------ pure helpers
def test_tok_and_missing(P):
    page = '<input id="__VIEWSTATE" value="abc=="><input id="y" value="">'
    assert P.tok("__VIEWSTATE", page) == "abc=="
    assert P.tok("y", page) == ""
    assert P.tok("nope", page) == ""


def test_parse_day_groups_by_ministry_and_unescapes(P):
    page = ("junk before<h3>Ministry of  Finance &amp; Co</h3><ul>"
            "<li><a title='a' href='/PressReleseDetailm.aspx?PRID=111'> Budget &amp; Tax </a></li>"
            "<li><a href='/PressReleseDetailm.aspx?PRID=112'>Second</a></li></ul>"
            "<h3>Cabinet</h3><li><a href='/PressReleseDetailm.aspx?PRID=113'>Third</a></li>"
            "<li><a href='/Other.aspx?PRID=999'>ignored</a></li>")
    assert list(P.parse_day(page)) == [("Ministry of Finance & Co", 111, "Budget & Tax"),
                                       ("Ministry of Finance & Co", 112, "Second"),
                                       ("Cabinet", 113, "Third")]
    assert list(P.parse_day("no headings at all")) == []


def test_months_table(P):
    assert P.MONTHS["JAN"] == 1 and P.MONTHS["DEC"] == 12 and len(P.MONTHS) == 12


def test_fetch_get_and_post(P):
    seen = []
    op = Op(lambda req: seen.append(req) or "café".encode("utf-8"))
    assert P.fetch(op, "http://x/a") == "café"
    req, timeout = op.reqs[0]
    assert timeout == 45 and req.data is None and req.get_header("User-agent") == P.UA["User-Agent"]
    assert req.get_header("Content-type") is None
    P.fetch(op, "http://x/a", {"k": "v w", "n": 1})
    req = op.reqs[1][0]
    assert req.data == b"k=v+w&n=1" and req.get_header("Content-type") == "application/x-www-form-urlencoded"
    assert req.get_header("Referer") == P.BASE
    bad = Op(lambda req: b"ok\xff")
    assert P.fetch(bad, "http://x") == "ok"                 # undecodable bytes are dropped


def test_opener_builds_cookie_opener(P):
    op = P.opener()
    assert any(h.__class__.__name__ == "HTTPCookieProcessor" for h in op.handlers)


# ------------------------------------------------------------------ db
def test_db_schema_and_upsert_keys(P, repo):
    con = P.db()
    cols = [r[1] for r in con.execute("PRAGMA table_info(pib_items)")]
    assert cols == ["id", "kind", "date", "ministry", "title", "url", "cited_in_repo", "fetched_at"]
    con.execute("INSERT INTO pib_items(id) VALUES (1)")
    assert con.execute("SELECT kind, cited_in_repo FROM pib_items").fetchone() == ("release", 0)
    con.execute("INSERT INTO pib_items(id, kind) VALUES (1, 'factsheet')")          # same id, other kind is allowed
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO pib_items(id) VALUES (1)")
    assert con.execute("SELECT value FROM meta").fetchall() == []
    assert (repo / "data/pib_index.sqlite").exists()


# ------------------------------------------------------------------ index_days
def patch_opener(P, monkeypatch, router):
    op = Op(router)
    monkeypatch.setattr(P, "opener", lambda: op)
    return op


def test_index_days_walks_each_day_and_records_meta(P, repo, monkeypatch, capsys):
    pages = {
        5: day_page([("Finance", [(1001, "Budget"), (1002, "Tax")])], "Monday, 5-January-2026"),
        6: day_page([("Cabinet", [(1003, "Approves")])], "Tuesday, 6-January-2026"),
    }

    def router(req):
        if req.data is None:
            return day_page([], "Sunday, 4-January-2026")                 # priming page
        form = dict(urllib.parse.parse_qsl(req.data.decode()))
        assert form["__VIEWSTATE"] == "VS1" and form["__EVENTVALIDATION"] == "EV" and form["__VIEWSTATEGENERATOR"] == "GEN"
        assert form["ctl00$ContentPlaceHolder1$ddlMonth"] == "1" and form["ctl00$ContentPlaceHolder1$ddlYear"] == "2026"
        assert form["ctl00$Bar1$ddlregion"] == "3" and form["ctl00$ContentPlaceHolder1$ddlMinistry"] == "0"
        return pages[int(form["ctl00$ContentPlaceHolder1$ddlday"])]
    op = patch_opener(P, monkeypatch, router)
    P.index_days(dt.date(2026, 1, 5), dt.date(2026, 1, 6))
    out = capsys.readouterr().out.splitlines()
    assert out == ["  2026-01-05    2 releases", "  2026-01-06    1 releases", "indexed 3 release rows 2026-01-05 → 2026-01-06"]
    assert len(op.reqs) == 3                                                   # prime + one POST per day
    con = sqlite3.connect(repo / "data/pib_index.sqlite")
    rows = con.execute("SELECT id, kind, date, ministry, title, url FROM pib_items ORDER BY id").fetchall()
    assert rows == [(1001, "release", "2026-01-05", "Finance", "Budget", "https://pib.gov.in/PressReleasePage.aspx?PRID=1001"),
                    (1002, "release", "2026-01-05", "Finance", "Tax", "https://pib.gov.in/PressReleasePage.aspx?PRID=1002"),
                    (1003, "release", "2026-01-06", "Cabinet", "Approves", "https://pib.gov.in/PressReleasePage.aspx?PRID=1003")]
    assert con.execute("SELECT value FROM meta WHERE key='last_indexed_date'").fetchone() == ("2026-01-06",)


def test_index_days_upserts_existing_rows(P, repo, monkeypatch, capsys):
    state = {"title": "Old"}

    def router(req):
        if req.data is None:
            return day_page([])
        return day_page([("Fin", [(7, state["title"])])], "Monday, 5-January-2026")
    patch_opener(P, monkeypatch, router)
    P.index_days(dt.date(2026, 1, 5), dt.date(2026, 1, 5))
    state["title"] = "New"
    P.index_days(dt.date(2026, 1, 5), dt.date(2026, 1, 5))
    con = sqlite3.connect(repo / "data/pib_index.sqlite")
    assert con.execute("SELECT COUNT(*), MAX(title) FROM pib_items").fetchone() == (1, "New")


def test_index_days_reprimes_on_fetch_error(P, repo, monkeypatch, capsys):
    calls = {"post": 0}
    sleeps = []
    monkeypatch.setattr(P.time, "sleep", lambda s: sleeps.append(s))

    def router(req):
        if req.data is None:
            return day_page([])
        calls["post"] += 1
        if calls["post"] == 1:
            return OSError("reset")
        return day_page([("Fin", [(9, "T")])], "Monday, 5-January-2026")
    op = patch_opener(P, monkeypatch, router)
    P.index_days(dt.date(2026, 1, 5), dt.date(2026, 1, 5))
    cap = capsys.readouterr()
    assert "FETCH ERROR reset" in cap.err and "indexed 1 release rows" in cap.out
    assert 5 in sleeps                                                         # back-off before re-priming
    assert len(op.reqs) == 4                                                   # prime, failed POST, re-prime, retried POST


def test_index_days_reprimes_when_server_shows_other_date(P, repo, monkeypatch, capsys):
    shown = iter(["Friday, 2-January-2026", "Monday, 5-January-2026"])

    def router(req):
        if req.data is None:
            return day_page([])
        return day_page([("Fin", [(5, "T")])], next(shown))
    op = patch_opener(P, monkeypatch, router)
    P.index_days(dt.date(2026, 1, 5), dt.date(2026, 1, 5))
    out = capsys.readouterr().out
    assert out.count("  2026-01-05  ") == 1 and "indexed 1 release rows" in out
    assert len(op.reqs) == 4                                                   # prime, wrong-date POST, re-prime, good POST
    con = sqlite3.connect(repo / "data/pib_index.sqlite")
    assert con.execute("SELECT COUNT(*) FROM pib_items").fetchone() == (1,)    # the wrong-date page was NOT stored


def test_index_days_page_without_label_is_accepted(P, repo, monkeypatch, capsys):
    def router(req):
        return "<h3>Fin</h3><li><a href='/PressReleseDetailm.aspx?PRID=3'>T</a>"
    patch_opener(P, monkeypatch, router)
    P.index_days(dt.date(2026, 1, 5), dt.date(2026, 1, 5))
    assert "indexed 1 release rows" in capsys.readouterr().out


def test_index_days_empty_range(P, repo, monkeypatch, capsys):
    op = patch_opener(P, monkeypatch, lambda req: day_page([]))
    P.index_days(dt.date(2026, 1, 6), dt.date(2026, 1, 5))
    assert capsys.readouterr().out.strip() == "indexed 0 release rows 2026-01-06 → 2026-01-05"
    assert len(op.reqs) == 1


# ------------------------------------------------------------------ factsheets
FS_PAGE = ("<a href='/FactsheetDetails.aspx?Id=150699' class='x'>Ethanol &amp; Biofuels</a>"
           "<span class='publishdatesmall'>Posted on: 05 Mar 2026</span>"
           "<a href='/FactsheetDetails.aspx?Id=150700'>Bad Date</a><span class='publishdatesmall'>Posted on: someday</span>"
           "<a href='/Other.aspx?Id=1'>skip</a>")


def test_index_factsheets(P, repo, monkeypatch, capsys):
    patch_opener(P, monkeypatch, lambda req: FS_PAGE)
    P.index_factsheets()
    assert capsys.readouterr().out.strip() == "indexed 2 factsheets from the listing"
    con = sqlite3.connect(repo / "data/pib_index.sqlite")
    rows = con.execute("SELECT id, kind, date, ministry, title, url FROM pib_items ORDER BY id").fetchall()
    assert rows == [(150699, "factsheet", "2026-03-05", None, "Ethanol & Biofuels", "https://pib.gov.in/FactsheetDetails.aspx?Id=150699&reg=3&lang=1"),
                    (150700, "factsheet", None, None, "Bad Date", "https://pib.gov.in/FactsheetDetails.aspx?Id=150700&reg=3&lang=1")]
    P.index_factsheets()                                                       # upsert, no duplicates
    assert con.execute("SELECT COUNT(*) FROM pib_items").fetchone() == (2,)


# ------------------------------------------------------------------ fill_from_detail
def test_fill_from_detail_full_page(P, monkeypatch):
    page = ('<div id="PrDateTime" class="x">  <b>05 JUN 2022</b> 2:11PM by PIB Delhi</div>'
            '<div id="MinistryName">\n  Ministry of   Commerce &amp; Industry </div>'
            '<meta property="og:title" content="Big &amp; Bold  Title">')
    monkeypatch.setattr(P, "fetch", lambda op, url, data=None: page if url == P.DETAIL.format(prid=42) else pytest.fail(url))
    assert P.fill_from_detail(None, 42) == ("2022-06-05", "Ministry of Commerce & Industry", "Big & Bold Title")


def test_fill_from_detail_fallbacks(P, monkeypatch):
    monkeypatch.setattr(P, "fetch", lambda op, url, data=None: "Posted On: 7 MAR 2021 <h2 class='pageTitle'> Fallback Title </h2>")
    assert P.fill_from_detail(None, 1) == ("2021-03-07", None, "Fallback Title")
    monkeypatch.setattr(P, "fetch", lambda op, url, data=None: "<h2>  Plain H2 title </h2>")
    assert P.fill_from_detail(None, 1) == (None, None, "Plain H2 title")
    monkeypatch.setattr(P, "fetch", lambda op, url, data=None: "nothing")
    assert P.fill_from_detail(None, 1) == (None, None, None)
    monkeypatch.setattr(P, "fetch", lambda op, url, data=None: '<meta property="og:title" content="abc">')   # < 5 chars rejected
    assert P.fill_from_detail(None, 1)[2] is None
    monkeypatch.setattr(P, "fetch", lambda op, url, data=None: '<div id="PrDateTime">1 XXX 2020</div>')       # unknown month -> January
    assert P.fill_from_detail(None, 1)[0] == "2020-01-01"


# ------------------------------------------------------------------ seed_cited
def test_seed_cited(P, repo, monkeypatch, capsys):
    (repo / "data/a.json").write_text('{"x": "PRID 2119954 and PRID: 2245096", "f": "Factsheet 150699"}')
    (repo / "data/b.json").write_text('{"x": "PRID=2119954", "short": "PRID 12345", "fs": "factsheet150700"}')
    con = P.db()
    con.execute("INSERT INTO pib_items(id, kind, date) VALUES (2119954, 'release', '2024-01-01')")     # date known: no fetch
    con.execute("INSERT INTO pib_items(id, kind, date) VALUES (2245096, 'release', NULL)")             # date missing: fetch
    con.commit()
    con.close()
    fetched = []

    def fill(op, prid):
        fetched.append(prid)
        return "2025-05-05", "Ministry", "Title " + str(prid)
    monkeypatch.setattr(P, "fill_from_detail", fill)
    monkeypatch.setattr(P, "opener", lambda: None)
    P.seed_cited()
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "cited in data/*.json: 2 PRIDs, 2 factsheets"           # 5-digit PRID ignored
    assert "  PRID 2245096: 2025-05-05 · Ministry · Title 2245096" in out and out[-1] == "seed-cited done"
    assert fetched == [2245096]
    con = sqlite3.connect(repo / "data/pib_index.sqlite")
    rows = {(r[0], r[1]): r[2:] for r in con.execute("SELECT id, kind, date, ministry, cited_in_repo, url FROM pib_items")}
    assert rows[(2119954, "release")][2] == 1 and rows[(2119954, "release")][0] == "2024-01-01"
    assert rows[(2245096, "release")][:3] == ("2025-05-05", "Ministry", 1)
    assert rows[(150699, "factsheet")][2] == 1 and rows[(150699, "factsheet")][3] == "https://pib.gov.in/FactsheetDetails.aspx?Id=150699&reg=3&lang=1"
    assert rows[(150700, "factsheet")][2] == 1
    assert (12345, "release") not in rows


def test_seed_cited_new_release_is_not_fetched_and_failures_reported(P, repo, monkeypatch, capsys):
    (repo / "data/a.json").write_text('{"x": "PRID 3000001"}')
    con = P.db()
    con.execute("INSERT INTO pib_items(id, kind, date) VALUES (3000001, 'release', NULL)")
    con.commit()
    con.close()

    def boom(op, prid):
        raise RuntimeError("down")
    monkeypatch.setattr(P, "fill_from_detail", boom)
    monkeypatch.setattr(P, "opener", lambda: None)
    P.seed_cited()
    cap = capsys.readouterr()
    assert "PRID 3000001: detail fetch failed (down)" in cap.err and "seed-cited done" in cap.out


# ------------------------------------------------------------------ stats / main
def test_stats(P, repo, capsys):
    con = P.db()
    con.executemany("INSERT INTO pib_items(id, kind, date, ministry, cited_in_repo) VALUES (?,?,?,?,?)", [
        (1, "release", "2026-01-01", "Fin", 1), (2, "release", "2026-02-01", "Fin", 0),
        (3, "release", "2026-03-01", "Cab", 1), (4, "factsheet", "2025-01-01", None, 0)])
    con.commit()
    P.stats()
    out = capsys.readouterr().out.splitlines()
    assert out[0].split() == ["factsheet", "rows=1", "dates", "2025-01-01", "→", "2025-01-01", "cited=0"]
    assert out[1].split() == ["release", "rows=3", "dates", "2026-01-01", "→", "2026-03-01", "cited=2"]
    assert out[3] == "top ministries:"
    assert out[4].split(None, 1) == ["2", "Fin"] and out[5].split(None, 1) == ["1", "Cab"] and len(out) == 6    # NULL ministry excluded


def run_main(P, monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["pib_index.py", *argv])
    P.main()


def test_main_dispatch(P, repo, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(P, "index_days", lambda a, b: calls.append(("days", a, b)))
    monkeypatch.setattr(P, "index_factsheets", lambda: calls.append("fs"))
    monkeypatch.setattr(P, "seed_cited", lambda: calls.append("seed"))
    monkeypatch.setattr(P, "stats", lambda: calls.append("stats"))
    run_main(P, monkeypatch, "--backfill", "2026-01-01", "2026-01-31", "--factsheets", "--seed-cited", "--stats")
    assert calls == [("days", dt.date(2026, 1, 1), dt.date(2026, 1, 31)), "fs", "seed", "stats"]
    calls.clear()
    run_main(P, monkeypatch)
    assert calls == [] and "usage:" in capsys.readouterr().out


def test_main_update_resumes_from_meta(P, repo, monkeypatch):
    calls = []
    monkeypatch.setattr(P, "index_days", lambda a, b: calls.append((a, b)))
    run_main(P, monkeypatch, "--update")
    today = dt.date.today()
    assert calls[-1][1] == today and calls[-1][0] in (today - dt.timedelta(days=7), dt.date.today() - dt.timedelta(days=7))
    con = P.db()
    con.execute("INSERT INTO meta VALUES ('last_indexed_date', '2026-01-10')")
    con.commit()
    run_main(P, monkeypatch, "--update")
    assert calls[-1] == (dt.date(2026, 1, 11), dt.date.today())


def test_main_db_override_and_query(P, repo, monkeypatch, capsys):
    alt = repo / "alt.sqlite"
    run_main(P, monkeypatch, "--db", str(alt), "--query", "SELECT 1, NULL, 'x'")
    assert capsys.readouterr().out.strip() == "1 |  | x"
    assert alt.exists() and str(P.DB_PATH) == str(alt)
