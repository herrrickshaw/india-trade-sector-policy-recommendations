"""scripts/cci_index.py: retrying fetch, probe commands, DataTables pagination, row parsing, sqlite upsert, CLI (no network)."""
import html as htmllib
import io
import json
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request

import pytest


@pytest.fixture
def C(load, monkeypatch):
    m = load("cci_index")
    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    return m


class Resp:
    def __init__(self, body, status=200):
        self.b = body if isinstance(body, bytes) else body.encode()
        self.status = status

    def read(self):
        return self.b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def http_error(code, body=b"err"):
    return urllib.error.HTTPError("http://x", code, "msg", {}, io.BytesIO(body))


# ------------------------------------------------------------------ fetch
def patch_urlopen(monkeypatch, seq):
    calls = []
    it = iter(seq)

    def urlopen(req, timeout=None):
        calls.append((req.full_url, timeout))
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return calls


def test_fetch_success(C, monkeypatch):
    calls = patch_urlopen(monkeypatch, [Resp(b"hello", 200)])
    assert C.fetch("http://x/a") == (200, b"hello")
    assert calls == [("http://x/a", 20)]
    calls = patch_urlopen(monkeypatch, [Resp(b"hello", 200)])
    C.fetch("http://x/a", timeout=5)
    assert calls == [("http://x/a", 5)]


def test_fetch_retries_with_exponential_backoff(C, monkeypatch):
    sleeps = []
    monkeypatch.setattr(C.time, "sleep", lambda s: sleeps.append(s))
    calls = patch_urlopen(monkeypatch, [http_error(429), http_error(503), http_error(500), Resp(b"ok")])
    assert C.fetch("http://x") == (200, b"ok")
    assert sleeps == [2.0, 4.0, 8.0] and len(calls) == 4


def test_fetch_gives_up_on_fourth_retryable_error(C, monkeypatch):
    calls = patch_urlopen(monkeypatch, [http_error(502, b"b1"), http_error(502, b"b2"), http_error(502, b"b3"), http_error(502, b"last")])
    assert C.fetch("http://x") == (502, b"last") and len(calls) == 4


@pytest.mark.parametrize("code", [429, 500, 502, 503, 504])
def test_fetch_retryable_codes(C, monkeypatch, code):
    calls = patch_urlopen(monkeypatch, [http_error(code), Resp(b"ok")])
    assert C.fetch("http://x") == (200, b"ok") and len(calls) == 2


@pytest.mark.parametrize("code", [400, 403, 404, 405])
def test_fetch_non_retryable_codes_return_immediately(C, monkeypatch, code):
    calls = patch_urlopen(monkeypatch, [http_error(code, b"nope")])
    assert C.fetch("http://x") == (code, b"nope") and len(calls) == 1


def test_fetch_url_error_becomes_runtime_error(C, monkeypatch):
    patch_urlopen(monkeypatch, [urllib.error.URLError("dns down")])
    with pytest.raises(RuntimeError, match="network: dns down"):
        C.fetch("http://x")


# ------------------------------------------------------------------ pure parsing
@pytest.mark.parametrize("raw,expected", [
    ("2026-03-15", "2026-03-15"), ("15/03/2026", "2026-03-15"), ("  15/03/2026 ", "2026-03-15"), (" 2026-03-15 ", "2026-03-15"),
    ("2026/03/15", None), ("15-03-2026", None), ("5/3/2026", None), ("2026-3-15", None), ("", None), (None, None), ("garbage", None),
    ("2026-03-15 10:00", None),
])
def test_normalize_date(C, raw, expected):
    assert C.normalize_date(raw) == expected


def test_parse_pdf_field(C):
    raw = htmllib.escape(json.dumps([{"title": "Order", "file_name": "images/caseorders/en/o1.pdf"},
                                     {"title": "x"}, {"file_name": ""}, "str", {"file_name": "a/b.pdf"}]).replace("/", "\\/"))
    assert "&quot;" in raw
    assert C.parse_pdf_field(raw) == ["https://cci.gov.in/images/caseorders/en/o1.pdf", "https://cci.gov.in/a/b.pdf"]
    assert C.parse_pdf_field("") == [] and C.parse_pdf_field(None) == []
    assert C.parse_pdf_field("not json") == []
    assert C.parse_pdf_field(json.dumps({"file_name": "x"})) == []      # an object, not a list of entries: iterating keys yields strings
    assert C.parse_pdf_field(12345) == []


def test_build_datatable_url(C):
    u = C.build_datatable_url("https://x.in/list", 200, 50)
    base, q = u.split("?", 1)
    assert base == "https://x.in/list"
    p = dict(urllib.parse.parse_qsl(q, keep_blank_values=True))
    assert p["start"] == "200" and p["length"] == "50" and p["draw"] == "1"
    assert p["order[0][dir]"] == "desc" and p["order[0][column]"] == "0"
    for i, col in enumerate(C.DATATABLE_COLUMNS):
        assert p[f"columns[{i}][data]"] == col and p[f"columns[{i}][searchable]"] == "true"
    assert f"columns[{len(C.DATATABLE_COLUMNS)}][data]" not in p
    assert p["fromdate"] == "" and p["todate"] == ""


# ------------------------------------------------------------------ probes
def test_cmd_probe_prints_all_four_views(C, monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(C, "fetch", lambda url, timeout=20: seen.append(url) or (200, b"<html>" + b"x" * 900 + b"</html>"))
    C.cmd_probe(77)
    out = capsys.readouterr().out
    assert seen == [C.DETAIL_URL.format(kind=k, order_id=77, sub=s) for k in ("order", "summary") for s in (0, 1)]
    assert out.count("=== ") == 4 and "=== order sub=0 -> HTTP 200 (913 bytes) ===" in out
    assert ("<html>" + "x" * 794) in out and ("x" * 795) not in out                  # only the first 800 chars are echoed


def test_cmd_probe_listing_counts_ids(C, monkeypatch, capsys):
    page = ("/combination/order/details/order/101/0/x /combination/order/details/summary/105/1/x "
            "/combination/order/details/order/101/0/x")
    monkeypatch.setattr(C, "fetch", lambda url, timeout=20: (200, page.encode()) if "section31" in url else (404, b"nothing"))
    C.cmd_probe_listing()
    out = capsys.readouterr().out
    assert "=== section31 -> HTTP 200 (%d bytes), 2 distinct order IDs found in raw HTML ===" % len(page) in out
    assert "id range seen on this page: 101-105" in out
    assert "=== green_channel -> HTTP 404 (7 bytes), 0 distinct order IDs found in raw HTML ===" in out
    assert out.count("id range seen") == 1


def test_cmd_probe_deep(C, monkeypatch, capsys):
    detail = ('<script src="/a.js"></script><script src="/a.js"></script><script src="/b.js"></script>'
              "var u = '/api/orders'; var j = \"data/x.json\"; Combination Registration No and acquisition of target")
    monkeypatch.setattr(C, "fetch", lambda url, timeout=20: (200, detail.encode()))
    C.cmd_probe_deep(5)
    out = capsys.readouterr().out
    assert out.count("=== DEEP order sub=0") == 1 and "=== DEEP summary sub=0" in out and "=== DEEP listing section31" in out
    assert "markers found in full body: ['Combination Registration No', 'acquisition of', 'target company']" not in out
    assert "markers found in full body: ['Combination Registration No', 'acquisition of']" in out
    assert "script src= URLs (2):\n  /a.js\n  /b.js" in out
    assert "api-like inline strings (2):" in out and "  /api/orders" in out and "  data/x.json" in out


def test_cmd_probe_deep_no_markers(C, monkeypatch, capsys):
    monkeypatch.setattr(C, "fetch", lambda url, timeout=20: (500, b"plain"))
    C.cmd_probe_deep(5)
    out = capsys.readouterr().out
    assert "markers found in full body: NONE" in out and "script src= URLs (0):" in out


def test_cmd_probe_ajax(C, monkeypatch, capsys):
    page = "x" * 200 + " $('#t').DataTable({ ajax: '/data.json' }) " + "y" * 300 + " /api/z"
    urls = []
    monkeypatch.setattr(C, "fetch", lambda url, timeout=20: urls.append(url) or (200, page.encode()))
    C.cmd_probe_ajax(9)
    out = capsys.readouterr().out
    assert urls == [C.LISTING_URLS["section31"], C.DETAIL_URL.format(kind="order", order_id=9, sub=0)]
    assert out.count("=== AJAX SCAN") == 2
    assert "occurrences of 'ajax': 1" in out and "occurrences of 'DataTable(': 1" in out
    assert "occurrences of '.json': 1" in out and "occurrences of '/api': 1" in out
    assert "--- last 4000 chars of body ---" in out


class Op:
    def __init__(self, router):
        self.router, self.reqs = router, []

    def open(self, req, timeout=None):
        self.reqs.append((req, timeout))
        r = self.router(req)
        if isinstance(r, Exception):
            raise r
        return r


def patch_opener(monkeypatch, router):
    op = Op(router)
    monkeypatch.setattr(urllib.request, "build_opener", lambda *a: op)
    return op


def test_cmd_probe_datatable_json(C, monkeypatch, capsys):
    def router(req):
        return Resp("<html/>") if "?" not in req.full_url else Resp(json.dumps({"draw": 1, "data": []}))
    op = patch_opener(monkeypatch, router)
    C.cmd_probe_datatable("green_channel")
    out = capsys.readouterr().out
    warm, get = op.reqs[0][0], op.reqs[1][0]
    assert warm.full_url == C.LISTING_URLS["green_channel"] and get.get_method() == "GET"
    assert get.get_header("X-requested-with") == "XMLHttpRequest" and get.get_header("Referer") == C.LISTING_URLS["green_channel"]
    assert get.get_header("Accept").startswith("application/json")
    assert "warm-up GET" in out and "HTTP 200" in out and "response IS valid JSON. keys: ['draw', 'data']" in out


def test_cmd_probe_datatable_http_error_and_non_json(C, monkeypatch, capsys):
    n = {"i": 0}

    def router(req):
        n["i"] += 1
        return Resp("<html/>") if n["i"] == 1 else http_error(405, b"Supported methods: GET")
    patch_opener(monkeypatch, router)
    C.cmd_probe_datatable("section31")
    out = capsys.readouterr().out
    assert "-> HTTP 405 (22 chars) ===" in out and "response is NOT valid JSON, raw excerpt:" in out and "Supported methods: GET" in out


# ------------------------------------------------------------------ iter_listing_rows
def paged_router(total, page_size_seen=None):
    def router(req):
        if "?" not in req.full_url:
            return Resp("warm")
        q = dict(urllib.parse.parse_qsl(req.full_url.split("?", 1)[1], keep_blank_values=True))
        start, length = int(q["start"]), int(q["length"])
        rows = [{"id": i} for i in range(start, min(start + length, total))]
        return Resp(json.dumps({"recordsTotal": total, "data": rows}))
    return router


def test_iter_listing_rows_paginates(C, monkeypatch):
    op = patch_opener(monkeypatch, paged_router(7))
    rows = list(C.iter_listing_rows("https://x.in/list", page_size=3))
    assert [r["id"] for r in rows] == list(range(7))
    starts = [int(dict(urllib.parse.parse_qsl(r.full_url.split("?", 1)[1]))["start"]) for r, _ in op.reqs[1:]]
    assert starts == [0, 3, 6]
    assert op.reqs[0][0].full_url == "https://x.in/list" and all(t == 20 for _, t in op.reqs)


def test_iter_listing_rows_exact_multiple_and_default_page_size(C, monkeypatch):
    op = patch_opener(monkeypatch, paged_router(200))
    assert len(list(C.iter_listing_rows("https://x.in/list"))) == 200
    assert len(op.reqs) == 3                                              # warm + 2 pages of 100; no extra empty page


def test_iter_listing_rows_stops_on_empty_page_and_sets_headers(C, monkeypatch):
    def router(req):
        if "?" not in req.full_url:
            return Resp("warm")
        return Resp(json.dumps({"recordsTotal": 50, "data": []}))
    op = patch_opener(monkeypatch, router)
    assert list(C.iter_listing_rows("https://x.in/list")) == []
    hdr = op.reqs[1][0]
    assert hdr.get_header("X-requested-with") == "XMLHttpRequest" and hdr.get_header("Referer") == "https://x.in/list"
    assert hdr.get_header("User-agent") == C.UA["User-Agent"]


def test_iter_listing_rows_http_error(C, monkeypatch):
    def router(req):
        return Resp("warm") if "?" not in req.full_url else http_error(500)
    patch_opener(monkeypatch, router)
    with pytest.raises(RuntimeError, match="HTTP 500 fetching https://x.in/list\\?"):
        list(C.iter_listing_rows("https://x.in/list"))


# ------------------------------------------------------------------ db / upsert
def row(oid, **kw):
    r = {"id": oid, "combination_no": f"C-2026/{oid}", "order_type": "Under Section 31", "order_status": "Approved",
         "decision_date": "15/03/2026", "party_name": "Acme Ltd",
         "order_file_content": htmllib.escape(json.dumps([{"file_name": "o/%d.pdf" % oid}])),
         "summary_file_content": htmllib.escape(json.dumps([{"file_name": "s/%d.pdf" % oid}, {"file_name": "s/%dB.pdf" % oid}]))}
    r.update(kw)
    return r


def fetch_all(con):
    cur = con.execute("SELECT * FROM cci_orders ORDER BY order_id")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def test_upsert_row_maps_fields(C, repo):
    con = C.db()
    C.upsert_row(con, "section31", row(5))
    (r,) = fetch_all(con)
    assert (r["order_id"], r["case_no"], r["order_kind"], r["order_type"], r["order_status"]) == (5, "C-2026/5", "section31", "Under Section 31", "Approved")
    assert r["order_date"] == "2026-03-15" and r["acquirer"] == "Acme Ltd" and r["target"] is None and r["deal_value_text"] is None
    assert r["order_pdf_url"] == "https://cci.gov.in/o/5.pdf"
    assert r["summary_pdf_url"] == "https://cci.gov.in/s/5.pdf;https://cci.gov.in/s/5B.pdf"
    assert json.loads(r["raw_json"])["id"] == 5 and r["fetched_at"][:2] == "20"


def test_upsert_row_date_fallback_chain(C, repo):
    con = C.db()
    C.upsert_row(con, "k", row(1, decision_date=None, date_of_order="2025-01-02", notification_date="01/01/2025"))
    C.upsert_row(con, "k", row(2, decision_date="garbage", date_of_order=None, notification_date="01/02/2025"))
    C.upsert_row(con, "k", row(3, decision_date=None, date_of_order=None, notification_date=None))
    C.upsert_row(con, "k", row(4, decision_date="03/04/2025", date_of_order="2025-01-02"))
    assert [r["order_date"] for r in fetch_all(con)] == ["2025-01-02", "2025-02-01", None, "2025-04-03"]


def test_upsert_row_skips_rows_without_id_and_updates_existing(C, repo):
    con = C.db()
    C.upsert_row(con, "k", {"party_name": "no id"})
    assert fetch_all(con) == []
    C.upsert_row(con, "section31", row(5))
    C.upsert_row(con, "green_channel", row(5, order_status="Deemed Approved", party_name="New Acq"))
    (r,) = fetch_all(con)
    assert (r["order_kind"], r["order_status"], r["acquirer"]) == ("green_channel", "Deemed Approved", "New Acq")


# ------------------------------------------------------------------ backfill / update
def test_cmd_backfill(C, repo, monkeypatch, capsys):
    data = {"section31": [row(i) for i in range(1, 104)], "section43a_44": [row(500)], "green_channel": []}
    monkeypatch.setattr(C, "iter_listing_rows", lambda url, page_size=100: iter(data[[k for k, v in C.LISTING_URLS.items() if v == url][0]]))
    C.cmd_backfill()
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "backfilling section31 ..." and "  section31: 100 rows so far" in out and "  section31: 103 rows total" in out
    assert "  section31: 200 rows so far" not in out
    assert "  section43a_44: 1 rows total" in out and "  green_channel: 0 rows total" in out
    assert out[-1] == "backfill done, 104 rows processed across 3 listing kinds"
    con = sqlite3.connect(repo / "data/cci_index.sqlite")
    assert con.execute("SELECT order_kind, COUNT(*) FROM cci_orders GROUP BY order_kind ORDER BY 1").fetchall() == [("section31", 103), ("section43a_44", 1)]


def test_cmd_update_stops_at_first_known_order(C, repo, monkeypatch, capsys):
    con = C.db()
    C.upsert_row(con, "section31", row(8))
    con.commit()
    con.close()
    data = {"section31": [row(10), row(9), row(8), row(7)], "section43a_44": [row(20)], "green_channel": []}
    monkeypatch.setattr(C, "iter_listing_rows", lambda url, page_size=100: iter(data[[k for k, v in C.LISTING_URLS.items() if v == url][0]]))
    C.cmd_update()
    out = capsys.readouterr().out
    assert out.startswith("1 orders already indexed")
    assert "section31: hit already-indexed order 8, stopping" in out and "  section31: 2 new rows" in out
    assert "  section43a_44: 1 new rows" in out and "  green_channel: 0 new rows" in out
    con = sqlite3.connect(repo / "data/cci_index.sqlite")
    assert [r[0] for r in con.execute("SELECT order_id FROM cci_orders ORDER BY order_id")] == [8, 9, 10, 20]      # 7 is past the stop point


def test_cmd_stats(C, repo, capsys):
    con = C.db()
    C.upsert_row(con, "section31", row(1))
    C.upsert_row(con, "section31", row(2, decision_date="01/01/2025"))
    C.upsert_row(con, "green_channel", row(3, decision_date=None, order_status="Deemed Approved"))
    con.commit()
    C.cmd_stats()
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "orders indexed: 3  dates 2025-01-01 -> 2026-03-15 (1 rows excluded from range: unparseable order_date)"
    assert "      2  section31" in out and "      1  green_channel" in out
    assert out.index("      2  Approved") < out.index("      1  Deemed Approved")


# ------------------------------------------------------------------ main
def run_main(C, monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["cci_index.py", *argv])
    C.main()


@pytest.mark.parametrize("argv,fn,args", [
    (["--probe", "12"], "cmd_probe", (12,)),
    (["--probe-listing"], "cmd_probe_listing", ()),
    (["--probe-deep", "13"], "cmd_probe_deep", (13,)),
    (["--probe-ajax", "14"], "cmd_probe_ajax", (14,)),
    (["--probe-datatable", "green_channel"], "cmd_probe_datatable", ("green_channel",)),
    (["--backfill"], "cmd_backfill", ()),
    (["--update"], "cmd_update", ()),
    (["--stats"], "cmd_stats", ()),
])
def test_main_dispatch(C, monkeypatch, argv, fn, args):
    calls = []
    for name in ("cmd_probe", "cmd_probe_listing", "cmd_probe_deep", "cmd_probe_ajax", "cmd_probe_datatable", "cmd_backfill", "cmd_update", "cmd_stats"):
        monkeypatch.setattr(C, name, (lambda n: lambda *a: calls.append((n, a)))(name))
    run_main(C, monkeypatch, *argv)
    assert calls == [(fn, args)]


def test_main_query_and_help(C, repo, monkeypatch, capsys):
    con = C.db()
    C.upsert_row(con, "section31", row(5))
    con.commit()
    run_main(C, monkeypatch, "--query", "SELECT order_id, acquirer FROM cci_orders")
    assert capsys.readouterr().out.strip() == "(5, 'Acme Ltd')"
    run_main(C, monkeypatch)
    assert "usage:" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        run_main(C, monkeypatch, "--probe-datatable", "bogus")
