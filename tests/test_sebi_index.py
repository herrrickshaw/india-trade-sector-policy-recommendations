"""scripts/sebi_index.py: title/date parsing, sqlite store, and the Selenium listing scraper (selenium faked, bs4 real)."""
import sqlite3
import sys
import types

import pytest


@pytest.fixture
def S(load, monkeypatch):
    m = load("sebi_index")
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    return m


# ------------------------------------------------------------------ parsing
@pytest.mark.parametrize("raw,expected", [
    ("Jun 11, 2026", "2026-06-11"), ("  Jan 1, 2026  ", "2026-01-01"), ("Dec 31, 1999", "1999-12-31"),
    ("11 Jun 2026", None), ("2026-06-11", None), ("", None), (None, None), ("Foo 11, 2026", None),
])
def test_normalize_date(S, raw, expected):
    assert S.normalize_date(raw) == expected


@pytest.mark.parametrize("title,expected", [
    ("Acme Foods Ltd - DRHP", ("Acme Foods Ltd", "DRHP")),
    ("Acme Foods Ltd - drhp", ("Acme Foods Ltd", "DRHP")),
    ("Acme  - Addendum to DRHP", ("Acme", "Addendum to DRHP")),
    ("Acme - CORRIGENDUM TO DRHP", ("Acme", "Corrigendum to DRHP")),
    ("Acme - UDRHP", ("Acme", "UDRHP (Updated DRHP)")),
    ("Acme - UDRHP2", ("Acme", "UDRHP (Updated DRHP)")),
    ("Acme - udrhp3  ", ("Acme", "UDRHP (Updated DRHP)")),
    ("A - B - DRHP", ("A - B", "DRHP")),                                   # lazy company group keeps the first dash
    ("Acme Foods - Final Prospectus", ("Acme Foods - Final Prospectus", None)),
    ("  Spaced Title  ", ("Spaced Title", None)),
    ("Acme - DRHP trailing", ("Acme - DRHP trailing", None)),
])
def test_parse_title(S, title, expected):
    assert S.parse_title(title) == expected


# ------------------------------------------------------------------ db + reports
def seed(S, rows):
    con = S.db()
    con.executemany("INSERT INTO sebi_filings(url, filing_date, filing_date_raw, company, filing_type, title, scraped_at) "
                    "VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()
    return con


def test_db_schema(S, repo):
    con = S.db()
    cols = [r[1] for r in con.execute("PRAGMA table_info(sebi_filings)")]
    assert cols == ["url", "filing_date", "filing_date_raw", "company", "filing_type", "title", "scraped_at"]
    idx = {r[1] for r in con.execute("PRAGMA index_list(sebi_filings)")}
    assert {"idx_sebi_date", "idx_sebi_company"} <= idx
    assert (repo / "data/sebi_index.sqlite").exists()


ROWS = [
    ("u1", "2026-06-11", "Jun 11, 2026", "Alpha Foods Ltd", "DRHP", "Alpha Foods Ltd - DRHP", "t"),
    ("u2", "2026-06-12", "Jun 12, 2026", "Beta Steel", "UDRHP (Updated DRHP)", "Beta Steel - UDRHP", "t"),
    ("u3", "2026-06-12", "Jun 12, 2026", "Alpha Foods Ltd", "Addendum to DRHP", "Alpha Foods Ltd - Addendum to DRHP", "t"),
    ("u4", None, "bad", "Gamma", None, "Gamma", "t"),
]


def test_new_since_is_exclusive_and_ordered(S, repo, capsys):
    seed(S, ROWS)
    S.cmd_new_since("2026-06-11")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "2 filings after 2026-06-11:"
    assert len(out) == 3 and all(l.startswith("  2026-06-12") for l in out[1:])
    S.cmd_new_since("2026-06-12")
    assert capsys.readouterr().out.strip() == "0 filings after 2026-06-12:"
    S.cmd_new_since("2000-01-01")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "3 filings after 2000-01-01:" and out[-1].startswith("  2026-06-11") and out[-1].rstrip().endswith("DRHP")


def test_new_since_formats_unparsed_type(S, repo, capsys):
    seed(S, [("u9", "2026-07-01", "Jul 1, 2026", "X" * 80, None, "t", "t")])
    S.cmd_new_since("2026-01-01")
    line = capsys.readouterr().out.splitlines()[1]
    assert line == "  2026-07-01  " + "X" * 55 + "  (unparsed)"                # company truncated to 55 chars, padded date


def test_stats(S, repo, capsys):
    seed(S, ROWS)
    S.cmd_stats()
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "filings indexed: 4  dates 2026-06-11 -> 2026-06-12 (1 rows excluded from range: unparseable filing_date)"
    assert out[1] == "distinct companies: 3"
    counts = {l.split(None, 1)[1]: int(l.split()[0]) for l in out[2:]}
    assert counts == {"DRHP": 1, "UDRHP (Updated DRHP)": 1, "Addendum to DRHP": 1, "(unparsed title)": 1}


def test_stats_empty(S, repo, capsys):
    S.cmd_stats()
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "filings indexed: 0  dates None -> None (0 rows excluded from range: unparseable filing_date)"
    assert out[1] == "distinct companies: 0"


# ------------------------------------------------------------------ selenium scrape
def listing_page(rows):
    body = "".join(rows)
    return f"<html><body><table><tr><th>Date</th><th>Title</th></tr>{body}</table></body></html>"


def row(date, title, href):
    return f"<tr><td>{date}</td><td><a href='{href}'>{title}</a></td></tr>"


class Driver:
    def __init__(self, pages, disabled_last=False, no_next_last=False, table_timeout_on=None):
        self.pages, self.idx = pages, 0
        self.disabled_last, self.no_next_last, self.table_timeout_on = disabled_last, no_next_last, table_timeout_on
        self.got, self.quit_called, self.clicks = None, False, 0

    @property
    def page_source(self):
        return self.pages[self.idx]

    def get(self, url):
        self.got = url

    def execute_script(self, script, el):
        assert script == "arguments[0].click();"
        self.clicks += 1
        self.idx += 1

    def quit(self):
        self.quit_called = True


class Btn:
    def __init__(self, drv):
        self.drv = drv

    def get_attribute(self, name):
        assert name == "class"
        last = self.drv.idx >= len(self.drv.pages) - 1
        return "next disabled" if (last and self.drv.disabled_last) else "next"


@pytest.fixture
def selenium(monkeypatch):
    state = types.SimpleNamespace(driver=None, opts=None)

    class Options:
        def __init__(self):
            self.args = []
            state.opts = self

        def add_argument(self, a):
            self.args.append(a)

    class EC:
        @staticmethod
        def presence_of_element_located(loc):
            return ("presence", loc)

        @staticmethod
        def element_to_be_clickable(loc):
            return ("clickable", loc)

    class By:
        XPATH = "xpath"

    class WebDriverWait:
        def __init__(self, drv, timeout):
            self.drv, self.timeout = drv, timeout

        def until(self, cond):
            kind, loc = cond
            d = self.drv
            if kind == "presence":
                if d.table_timeout_on is not None and d.idx == d.table_timeout_on:
                    raise TimeoutError("no table")
                assert self.timeout == 15
                return object()
            assert self.timeout == 10
            if d.idx >= len(d.pages) - 1 and d.no_next_last:
                raise TimeoutError("no next")
            return Btn(d)

    def make_driver(options=None):
        assert options is state.opts
        return state.driver

    mods = {
        "selenium": types.ModuleType("selenium"),
        "selenium.webdriver": types.SimpleNamespace(Chrome=make_driver),
        "selenium.webdriver.chrome": types.ModuleType("selenium.webdriver.chrome"),
        "selenium.webdriver.chrome.options": types.SimpleNamespace(Options=Options),
        "selenium.webdriver.common": types.ModuleType("selenium.webdriver.common"),
        "selenium.webdriver.common.by": types.SimpleNamespace(By=By),
        "selenium.webdriver.support": types.ModuleType("selenium.webdriver.support"),
        "selenium.webdriver.support.ui": types.SimpleNamespace(WebDriverWait=WebDriverWait),
        "selenium.webdriver.support.expected_conditions": EC,
    }
    mods["selenium"].webdriver = mods["selenium.webdriver"]
    mods["selenium.webdriver.support"].expected_conditions = EC
    for k, v in mods.items():
        monkeypatch.setitem(sys.modules, k, v)
    return state


def test_scrape_missing_dependency_exits(S, monkeypatch):
    monkeypatch.setitem(sys.modules, "selenium", None)
    with pytest.raises(SystemExit) as e:
        S.cmd_scrape(1)
    assert "missing dependency" in str(e.value) and "pip3 install selenium beautifulsoup4" in str(e.value)


def test_scrape_walks_pages_and_filters_rows(S, repo, selenium, capsys):
    p1 = listing_page([
        row("Jun 12, 2026", "Beta Steel - UDRHP", "/sebiweb/filing/b.html"),
        row("Jun 11, 2026", "Alpha Foods Ltd - DRHP", "https://www.sebi.gov.in/sebiweb/filing/a.html"),
        row("Jun 10, 2026", "Circular on something", "/c.html"),
        "<tr><td>Jun 9, 2026</td><td>no anchor DRHP</td></tr>",
        row("Jun 8, 2026", "Draft Red Herring Prospectus of Delta", "/d.html"),
    ])
    p2 = listing_page([row("Jun 7, 2026", "Eps Co - Corrigendum to DRHP", "/e.html"),
                       "<tr><td>Jun 6, 2026</td><td><a>Zeta DRHP</a></td></tr>"])
    selenium.driver = Driver([p1, p2], disabled_last=True)
    S.cmd_scrape(10)
    out = capsys.readouterr().out
    assert "Connected to SEBI database. Parsing public listings..." in out
    assert "  Page 1..." in out and "  Page 2..." in out and "Next button disabled -- end of listing." in out
    assert "5 DRHP-family filings scraped across 2 page(s)." in out
    d = selenium.driver
    assert d.got == S.TARGET_URL and d.quit_called and d.clicks == 1
    assert "--headless=new" in selenium.opts.args and "--window-size=1920,1080" in selenium.opts.args
    assert any(a.startswith("user-agent=Mozilla/5.0") for a in selenium.opts.args)
    con = sqlite3.connect(repo / "data/sebi_index.sqlite")
    rows = {r[0]: r[1:] for r in con.execute("SELECT url, filing_date, filing_date_raw, company, filing_type, title FROM sebi_filings")}
    assert rows["https://www.sebi.gov.in/sebiweb/filing/b.html"] == ("2026-06-12", "Jun 12, 2026", "Beta Steel", "UDRHP (Updated DRHP)", "Beta Steel - UDRHP")
    assert rows["https://www.sebi.gov.in/sebiweb/filing/a.html"][:1] == ("2026-06-11",)          # absolute href kept as is
    assert rows["https://www.sebi.gov.in/d.html"] == ("2026-06-08", "Jun 8, 2026", "Draft Red Herring Prospectus of Delta", None, "Draft Red Herring Prospectus of Delta")
    assert rows["https://www.sebi.gov.in"] == ("2026-06-06", "Jun 6, 2026", "Zeta DRHP", None, "Zeta DRHP")   # anchor without href -> site root
    assert "https://www.sebi.gov.in/c.html" not in rows and len(rows) == 5


def test_scrape_upserts_by_url(S, repo, selenium, capsys):
    selenium.driver = Driver([listing_page([row("Jun 12, 2026", "Beta - DRHP", "/b.html")])], disabled_last=True)
    S.cmd_scrape(5)
    selenium.driver = Driver([listing_page([row("Jun 13, 2026", "Beta Renamed - DRHP", "/b.html")])], disabled_last=True)
    S.cmd_scrape(5)
    con = sqlite3.connect(repo / "data/sebi_index.sqlite")
    assert con.execute("SELECT COUNT(*), MAX(company), MAX(filing_date) FROM sebi_filings").fetchone() == (1, "Beta Renamed", "2026-06-13")


def test_scrape_stops_without_next_button(S, repo, selenium, capsys):
    selenium.driver = Driver([listing_page([row("Jun 12, 2026", "Beta - DRHP", "/b.html")])], no_next_last=True)
    S.cmd_scrape(5)
    out = capsys.readouterr().out
    assert "No next-page button found -- end of listing." in out and "1 DRHP-family filings scraped across 1 page(s)." in out
    assert selenium.driver.quit_called


def test_scrape_table_timeout_stops_and_still_quits(S, repo, selenium, capsys):
    selenium.driver = Driver([listing_page([row("Jun 12, 2026", "Beta - DRHP", "/b.html")]), listing_page([])], table_timeout_on=1)
    S.cmd_scrape(5)
    out = capsys.readouterr().out
    assert "Table timeout -- stopping." in out and "1 DRHP-family filings scraped across 2 page(s)." in out
    assert selenium.driver.quit_called


def test_scrape_page_limit_zero_scrapes_nothing(S, repo, selenium, capsys):
    selenium.driver = Driver([listing_page([row("Jun 12, 2026", "Beta - DRHP", "/b.html")])])
    S.cmd_scrape(0)
    assert "0 DRHP-family filings scraped across 1 page(s)." in capsys.readouterr().out
    assert selenium.driver.clicks == 0


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="sebi_index.py:205 reports `page_num` after the loop, which is one past the last page scraped when the limit is hit")
def test_scrape_page_limit_message_counts_pages_scraped(S, repo, selenium, capsys):
    pages = [listing_page([row("Jun 1%d, 2026" % i, f"Co{i} - DRHP", f"/c{i}.html")]) for i in range(3)]
    selenium.driver = Driver(pages)
    S.cmd_scrape(2)
    out = capsys.readouterr().out
    assert selenium.driver.clicks == 2
    assert "2 DRHP-family filings scraped across 2 page(s)." in out


# ------------------------------------------------------------------ main
def run_main(S, monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["sebi_index.py", *argv])
    S.main()


def test_main_dispatch(S, repo, monkeypatch, capsys):
    seed(S, ROWS)
    scraped = []
    monkeypatch.setattr(S, "cmd_scrape", lambda n: scraped.append(n))
    run_main(S, monkeypatch, "--scrape")
    run_main(S, monkeypatch, "--scrape", "--page-limit", "3")
    assert scraped == [60, 3]
    run_main(S, monkeypatch, "--new-since", "2026-06-11")
    assert "2 filings after 2026-06-11:" in capsys.readouterr().out
    run_main(S, monkeypatch, "--stats")
    assert "filings indexed: 4" in capsys.readouterr().out
    run_main(S, monkeypatch, "--query", "SELECT company FROM sebi_filings WHERE url='u2'")
    assert capsys.readouterr().out.strip() == "('Beta Steel',)"
    run_main(S, monkeypatch)
    assert "usage:" in capsys.readouterr().out
