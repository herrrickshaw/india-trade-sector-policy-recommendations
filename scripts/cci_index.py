#!/usr/bin/env python3
"""
cci_index.py — date-wise index of Competition Commission of India (CCI)
combination (M&A) orders, in a SQLite database for ready reference.

WHY THIS EXISTS: pib_cci_ma_mentions_2026-09-14.csv (built from pib_index.sqlite)
only captured 297 of 684 CCI-tagged PIB releases, and PIB only republishes a
subset of CCI's own order-by-order output as short press notes -- title-only,
no deal value, no order status detail, no case number. CCI's own site
(cci.gov.in) is the authoritative source: every combination order, searchable
by status, with the underlying PDF (which usually states deal value, the
parties' full legal names, and the CCI's own competitive-assessment summary).

CONFIRMED LIVE (a 4-round --probe* diagnostic chain resolved this; see git
history on this file for the round-by-round evidence if any of this ever
stops matching reality):

  The three listing pages are a jQuery DataTables shell -- the visible HTML
  never contains order rows. Each page's DataTable is initialized with
  serverSide:true and an ajax config whose `url` is the SAME listing URL,
  with no `type` set (so jQuery defaults to GET, confirmed by a first
  attempt at POST getting HTTP 405 "Supported methods: GET, HEAD"). Hitting
  that URL with the standard DataTables paging/column query-string params
  returns JSON: {draw, recordsTotal, recordsFiltered, data: [...]}. Row
  fields seen live: id, combination_no, party_name, order_type,
  order_status, order_status_id, notification_date, decision_date,
  date_of_order, description, order_file_content, summary_file_content
  (both HTML-entity-escaped JSON strings listing PDF file_name/file_size --
  see parse_pdf_field()). section31 alone reported recordsTotal: 1460.
    https://www.cci.gov.in/combination/orders-section31       (main approvals)
    https://www.cci.gov.in/combination/orders-section43a_44   (penalty/enforcement,
                                                                 non-notification)
    https://www.cci.gov.in/combination/green-channel           (fast-track)

  KNOWN LIMITATION: party_name is the notifying party (usually the
  acquirer) -- the listing endpoint does NOT return a separate target-
  company field. target stays NULL until PDF parsing is added (see
  NOT YET DONE below); acquirer is populated from party_name.

  Individual order detail pages still exist and still work for sub=0 (sub=1
  is a hard HTTP 500 for both order/summary -- treat {sub} as always 0):
    https://cci.gov.in/combination/order/details/order/{id}/{sub}/orders-section31
    https://cci.gov.in/combination/order/details/summary/{id}/{sub}/orders-section31
  They are NOT currently used by --backfill/--update -- the listing ajax
  endpoint alone already gives every field this script's DB schema wants
  except target/deal_value_text.

  PDFs, once you have a file_name from order_file_content/summary_file_content:
    https://cci.gov.in/{file_name}

NOT YET DONE (deliberately out of scope for this pass -- add only if the
listing endpoint's fields prove insufficient for actual use):
  1. PDF text extraction (pdfplumber) for target-company name and deal
     value, neither of which the listing endpoint returns.
  2. Confirming whether page_size can go above the 100 used here (fewer,
     larger requests) -- untested; 100 is a conservative default, not a
     measured ceiling.
  3. Cross-check row counts against pib_cci_ma_mentions_2026-09-14.csv's 684
     CCI-tagged PIB releases once --backfill has actually run -- CCI's own
     count should be >= that, since PIB only republishes a subset.

Usage (mirrors pib_index.py's CLI):
  python3 scripts/cci_index.py --probe 1270              # round 1: raw detail-page HTML
  python3 scripts/cci_index.py --probe-listing            # round 1: raw listing-page HTML
  python3 scripts/cci_index.py --probe-deep 1270          # round 2: full-body markers + script src=
  python3 scripts/cci_index.py --probe-ajax 1270          # round 3: locate the DataTable ajax config
  python3 scripts/cci_index.py --probe-datatable section31  # round 4: hit the real ajax endpoint
  python3 scripts/cci_index.py --backfill                 # pull every order, all 3 listing kinds
  python3 scripts/cci_index.py --update                   # newest-first, stop at first known order_id
  python3 scripts/cci_index.py --stats
  python3 scripts/cci_index.py --query "SELECT order_date,case_no,acquirer FROM cci_orders WHERE acquirer LIKE '%Steel%'"

DB: data/cci_index.sqlite (table cci_orders, PK order_id)
"""
import argparse
import datetime as dt
import html
import http.cookiejar
import json
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data/cci_index.sqlite"

LISTING_URLS = {
    "section31": "https://www.cci.gov.in/combination/orders-section31",
    "section43a_44": "https://www.cci.gov.in/combination/orders-section43a_44",
    "green_channel": "https://www.cci.gov.in/combination/green-channel",
}
DETAIL_URL = "https://cci.gov.in/combination/order/details/{kind}/{order_id}/{sub}/orders-section31"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
SLEEP = 1.5  # start conservative; this site's rate-limit tolerance is unconfirmed


def db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS cci_orders(
        order_id INTEGER PRIMARY KEY,
        case_no TEXT,
        order_kind TEXT,          -- which listing page this came from: section31 | section43a_44 | green_channel
        order_type TEXT,          -- site's own type label, e.g. "Under Section 31" | "Green Channel Notices"
        order_status TEXT,        -- Approved | Deemed Approved (Section 6(5)) | ... (as returned, not normalized)
        order_date TEXT,          -- decision_date, falling back to date_of_order/notification_date
        target TEXT,              -- NOT populated by the listing endpoint -- party_name is the
                                   -- notifying party (usually the acquirer); target name needs
                                   -- the order/summary PDF, not yet parsed by this script
        acquirer TEXT,            -- party_name from the listing endpoint
        deal_value_text TEXT,     -- raw as stated; not in the listing endpoint, needs PDF parsing
        order_pdf_url TEXT,       -- ; -joined if more than one file
        summary_pdf_url TEXT,     -- ; -joined if more than one file
        raw_json TEXT,            -- the row's raw JSON from the listing endpoint, for debugging
        fetched_at TEXT)""")
    return con


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    delay = 2.0
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(delay)
                delay *= 2
                continue
            return e.code, e.read()
        except urllib.error.URLError as e:
            raise RuntimeError(f"network: {e.reason}")


def cmd_probe(order_id):
    """Fetch both detail sub-views for one order_id, print status + a raw excerpt.
    Run this FIRST, before trusting anything else in this file -- it exists to
    show the actual HTML shape so list_page()/detail_page() can be written
    against reality instead of a guess."""
    for kind in ("order", "summary"):
        for sub in (0, 1):
            url = DETAIL_URL.format(kind=kind, order_id=order_id, sub=sub)
            status, body = fetch(url)
            text = body.decode("utf-8", errors="replace")
            print(f"\n=== {kind} sub={sub} -> HTTP {status} ({len(body)} bytes) ===")
            print(url)
            print(text[:800])
            time.sleep(SLEEP)


def cmd_probe_listing():
    """Fetch all three listing pages plain (no filter params), print status +
    a raw excerpt of each, and a naive count of any numeric order-detail IDs
    findable in the response (a rough signal of whether the page is server-
    rendered with real rows, or a shell needing JS/an API call)."""
    id_pattern = re.compile(r"/combination/order/details/(?:order|summary)/(\d+)/")
    for name, url in LISTING_URLS.items():
        status, body = fetch(url)
        text = body.decode("utf-8", errors="replace")
        ids = sorted(set(int(m) for m in id_pattern.findall(text)))
        print(f"\n=== {name} -> HTTP {status} ({len(body)} bytes), "
              f"{len(ids)} distinct order IDs found in raw HTML ===")
        print(url)
        if ids:
            print(f"id range seen on this page: {min(ids)}-{max(ids)}")
        print(text[:800])
        time.sleep(SLEEP)


def cmd_probe_deep(order_id):
    """Round 2 probe, run after --probe and --probe-listing showed 0 order IDs
    in the listing pages' raw HTML. Two things:
      1. Fetch order/summary sub=0 for order_id (the only sub value that did
         not 500) and search the FULL body -- not just the first 800 chars --
         for text markers that would prove the detail page carries real
         parsed fields server-side (deal terms, case number, party names).
      2. Fetch the section31 listing page and pull out every <script src=...>
         and <link ... as="fetch"/preload> URL, plus any inline string that
         looks like an API path (contains "/api/" or ends in .json), since
         the actual order rows almost certainly come from one of those."""
    markers = [
        "Combination Registration No", "Regulation 5", "Section 6(2)",
        "acquisition of", "target company", "acquirer", "order date",
        "notice given", "Order No", "combination-order",
    ]
    for kind in ("order", "summary"):
        url = DETAIL_URL.format(kind=kind, order_id=order_id, sub=0)
        status, body = fetch(url)
        text = body.decode("utf-8", errors="replace")
        print(f"\n=== DEEP {kind} sub=0 -> HTTP {status} ({len(body)} bytes) ===")
        print(url)
        hits = [m for m in markers if m.lower() in text.lower()]
        print(f"markers found in full body: {hits if hits else 'NONE'}")
        script_srcs = sorted(set(re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text)))
        print(f"script src= URLs ({len(script_srcs)}):")
        for s in script_srcs:
            print(f"  {s}")
        api_like = sorted(set(re.findall(r'["\']([^"\']*(?:/api/|\.json)[^"\']*)["\']', text)))
        print(f"api-like inline strings ({len(api_like)}):")
        for s in api_like:
            print(f"  {s}")
        print("--- body chars 800:2400 (past the head boilerplate) ---")
        print(text[800:2400])
        time.sleep(SLEEP)

    url = LISTING_URLS["section31"]
    status, body = fetch(url)
    text = body.decode("utf-8", errors="replace")
    print(f"\n=== DEEP listing section31 -> HTTP {status} ({len(body)} bytes) ===")
    script_srcs = sorted(set(re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', text)))
    print(f"script src= URLs ({len(script_srcs)}):")
    for s in script_srcs:
        print(f"  {s}")
    api_like = sorted(set(re.findall(r'["\']([^"\']*(?:/api/|\.json)[^"\']*)["\']', text)))
    print(f"api-like inline strings ({len(api_like)}):")
    for s in api_like:
        print(f"  {s}")
    print("--- body chars 800:2400 (past the head boilerplate) ---")
    print(text[800:2400])


def cmd_probe_ajax(order_id):
    """Round 3 probe. --probe-deep showed the pages load DataTables
    (frontdatatables.min.js, datatables.script.min.js, datatables.min.css)
    -- DataTables almost always fetches its rows via a separate AJAX call
    configured in an inline <script> near the end of the page body, which
    the earlier 800:2400-char window never reached. This dumps every
    occurrence of "ajax"/"DataTable(" with surrounding context, plus the
    last 4000 chars of the body (where init scripts usually sit), for the
    listing page and for order_id's own detail page."""
    def scan(name, url):
        status, body = fetch(url)
        text = body.decode("utf-8", errors="replace")
        print(f"\n=== AJAX SCAN {name} -> HTTP {status} ({len(body)} bytes) ===")
        print(url)
        for kw in ("ajax", "DataTable(", ".json", "/api"):
            spots = [m.start() for m in re.finditer(re.escape(kw), text, re.IGNORECASE)]
            print(f"occurrences of {kw!r}: {len(spots)}")
            for pos in spots[:5]:
                lo, hi = max(0, pos - 150), min(len(text), pos + 250)
                print(f"  ...{text[lo:hi]!r}...")
        print("--- last 4000 chars of body ---")
        print(text[-4000:])
        time.sleep(SLEEP)

    scan("listing section31", LISTING_URLS["section31"])
    scan("detail order sub=0", DETAIL_URL.format(kind="order", order_id=order_id, sub=0))


DATATABLE_COLUMNS = [
    "DT_RowIndex", "combination_no", "party_name", "form_type",
    "notification_date", "order_status", "decision_date",
    "summary_files", "order_files",
]


def cmd_probe_datatable(name):
    """Round 4 probe. --probe-ajax found the exact DataTables serverSide
    config: url: the SAME listing URL, with the standard DataTables
    paging/column params plus custom filter fields (form_type, order_status,
    searchString, search_type, fromdate, todate), expecting JSON back
    ({draw, recordsTotal, recordsFiltered, data: [...]}). The ajax config
    never set `type: 'POST'`, so jQuery DataTables defaults to GET -- a
    first attempt at POST got HTTP 405 ("Supported methods: GET, HEAD"),
    confirming this. Sends the params as a GET query string instead."""
    url = LISTING_URLS[name]
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    warm_req = urllib.request.Request(url, headers=UA)
    with opener.open(warm_req, timeout=20) as r:
        warm_status = r.status
    print(f"=== warm-up GET {url} -> HTTP {warm_status}, cookies received: "
          f"{[c.name for c in jar]} ===")

    params = {
        "draw": "1", "start": "0", "length": "10",
        "search[value]": "", "search[regex]": "false",
        "order[0][column]": "0", "order[0][dir]": "desc",
        "form_type": "", "order_status": "", "searchString": "",
        "search_type": "", "fromdate": "", "todate": "",
    }
    for i, col in enumerate(DATATABLE_COLUMNS):
        params[f"columns[{i}][data]"] = col
        params[f"columns[{i}][name]"] = col
        params[f"columns[{i}][searchable]"] = "true"
        params[f"columns[{i}][orderable]"] = "true"
        params[f"columns[{i}][search][value]"] = ""
        params[f"columns[{i}][search][regex]"] = "false"
    query = urllib.parse.urlencode(params)
    get_url = f"{url}?{query}"

    get_headers = dict(UA)
    get_headers["X-Requested-With"] = "XMLHttpRequest"
    get_headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
    get_headers["Referer"] = url

    get_req = urllib.request.Request(get_url, headers=get_headers, method="GET")
    try:
        with opener.open(get_req, timeout=20) as r:
            status = r.status
            body = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read().decode("utf-8", errors="replace")

    print(f"\n=== GET {get_url[:120]}... -> HTTP {status} ({len(body)} chars) ===")
    try:
        parsed = json.loads(body)
        print("response IS valid JSON. keys:", list(parsed.keys()))
        print(json.dumps(parsed, indent=2)[:3000])
    except json.JSONDecodeError:
        print("response is NOT valid JSON, raw excerpt:")
        print(body[:2000])


def build_datatable_url(url, start, length):
    params = {
        "draw": "1", "start": str(start), "length": str(length),
        "search[value]": "", "search[regex]": "false",
        "order[0][column]": "0", "order[0][dir]": "desc",
        "form_type": "", "order_status": "", "searchString": "",
        "search_type": "", "fromdate": "", "todate": "",
    }
    for i, col in enumerate(DATATABLE_COLUMNS):
        params[f"columns[{i}][data]"] = col
        params[f"columns[{i}][name]"] = col
        params[f"columns[{i}][searchable]"] = "true"
        params[f"columns[{i}][orderable]"] = "true"
        params[f"columns[{i}][search][value]"] = ""
        params[f"columns[{i}][search][regex]"] = "false"
    return f"{url}?{urllib.parse.urlencode(params)}"


def iter_listing_rows(url, page_size=100):
    """Paginate a CCI listing page's DataTables ajax endpoint (confirmed
    live via --probe-datatable: a GET, not a POST, back to the listing
    URL itself with DataTables paging params in the query string),
    yielding every row dict across all pages. The site's default order
    is newest-first by internal id -- confirmed on one page of live data,
    not proven across the whole table, so --update's early-stop (below)
    is a reasonable bet, not a guarantee."""
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    warm_req = urllib.request.Request(url, headers=UA)
    with opener.open(warm_req, timeout=20) as r:
        r.read()

    headers = dict(UA)
    headers["X-Requested-With"] = "XMLHttpRequest"
    headers["Accept"] = "application/json, text/javascript, */*; q=0.01"
    headers["Referer"] = url

    start = 0
    total = None
    while total is None or start < total:
        page_url = build_datatable_url(url, start, page_size)
        req = urllib.request.Request(page_url, headers=headers, method="GET")
        try:
            with opener.open(req, timeout=20) as r:
                body = r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code} fetching {page_url}")
        payload = json.loads(body)
        total = payload.get("recordsTotal", 0)
        rows = payload.get("data", [])
        if not rows:
            break
        for row in rows:
            yield row
        start += len(rows)
        time.sleep(SLEEP)


def parse_pdf_field(raw):
    """order_file_content / summary_file_content come back as an
    HTML-entity-escaped JSON string, e.g.
    '[{&quot;title&quot;:&quot;Order&quot;,&quot;file_name&quot;:&quot;images\\/caseorders\\/en\\/order123.pdf&quot;,...}]'
    -- html.unescape() turns &quot; back into ", after which it's plain
    JSON (the \\/ is a legal JSON-escaped slash, json.loads handles it)."""
    if not raw:
        return []
    try:
        entries = json.loads(html.unescape(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    urls = []
    for e in entries:
        fname = e.get("file_name") if isinstance(e, dict) else None
        if fname:
            urls.append(f"https://cci.gov.in/{fname}")
    return urls


def upsert_row(con, kind, row):
    order_id = row.get("id")
    if order_id is None:
        return
    order_date = row.get("decision_date") or row.get("date_of_order") or row.get("notification_date")
    order_pdfs = parse_pdf_field(row.get("order_file_content"))
    summary_pdfs = parse_pdf_field(row.get("summary_file_content"))
    con.execute("""INSERT INTO cci_orders
        (order_id, case_no, order_kind, order_type, order_status, order_date,
         target, acquirer, deal_value_text, order_pdf_url, summary_pdf_url,
         raw_json, fetched_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(order_id) DO UPDATE SET
            case_no=excluded.case_no, order_kind=excluded.order_kind,
            order_type=excluded.order_type, order_status=excluded.order_status,
            order_date=excluded.order_date, acquirer=excluded.acquirer,
            order_pdf_url=excluded.order_pdf_url, summary_pdf_url=excluded.summary_pdf_url,
            raw_json=excluded.raw_json, fetched_at=excluded.fetched_at
        """, (order_id, row.get("combination_no"), kind, row.get("order_type"),
              row.get("order_status"), order_date, None, row.get("party_name"),
              None, ";".join(order_pdfs), ";".join(summary_pdfs),
              json.dumps(row, ensure_ascii=False),
              dt.datetime.now().isoformat(timespec="seconds")))


def cmd_backfill():
    con = db()
    grand_total = 0
    for kind, url in LISTING_URLS.items():
        print(f"backfilling {kind} ...")
        n = 0
        for row in iter_listing_rows(url):
            upsert_row(con, kind, row)
            n += 1
            if n % 100 == 0:
                con.commit()
                print(f"  {kind}: {n} rows so far")
        con.commit()
        print(f"  {kind}: {n} rows total")
        grand_total += n
    print(f"backfill done, {grand_total} rows processed across 3 listing kinds")


def cmd_update():
    con = db()
    existing_ids = set(r[0] for r in con.execute("SELECT order_id FROM cci_orders"))
    print(f"{len(existing_ids)} orders already indexed")
    for kind, url in LISTING_URLS.items():
        print(f"checking {kind} for new orders ...")
        new_count = 0
        for row in iter_listing_rows(url):
            oid = row.get("id")
            if oid in existing_ids:
                print(f"  {kind}: hit already-indexed order {oid}, stopping "
                      f"(assumes newest-first ordering -- rerun --backfill if this "
                      f"misses anything)")
                break
            upsert_row(con, kind, row)
            new_count += 1
        con.commit()
        print(f"  {kind}: {new_count} new rows")


def cmd_stats():
    """order_date is stored as CCI's own DD/MM/YYYY text, so a plain SQL
    MIN/MAX would sort lexicographically (comparing the day digit first)
    and print a meaningless range -- convert to YYYY-MM-DD first, and
    exclude empty/malformed values (printing how many were excluded).
    This does NOT filter out CCI's own 01/01/1970 placeholder (seen on
    one "Notice Not Valid" row) -- that's a real, if odd, value in their
    data, and now correctly sorts as the true minimum instead of just
    accidentally matching the old lexicographic bug's answer."""
    con = db()
    iso = ("substr(order_date,7,4) || '-' || substr(order_date,4,2) || "
           "'-' || substr(order_date,1,2)")
    valid = "order_date IS NOT NULL AND length(order_date) = 10"
    n_total = con.execute("SELECT COUNT(*) FROM cci_orders").fetchone()[0]
    cur = con.execute(f"SELECT COUNT(*), MIN({iso}), MAX({iso}) "
                       f"FROM cci_orders WHERE {valid}")
    n_valid, dmin, dmax = cur.fetchone()
    print(f"orders indexed: {n_total}  dates {dmin} -> {dmax} "
          f"({n_total - n_valid} rows excluded from range: empty/malformed order_date)")
    for row in con.execute("SELECT order_kind, COUNT(*) FROM cci_orders GROUP BY order_kind"):
        print(f"  {row[1]:5d}  {row[0]}")
    for row in con.execute("SELECT order_status, COUNT(*) FROM cci_orders "
                            "GROUP BY order_status ORDER BY COUNT(*) DESC"):
        print(f"  {row[1]:5d}  {row[0]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe", type=int, metavar="ORDER_ID",
                     help="fetch one order's detail pages raw, print HTML shape -- run this first")
    ap.add_argument("--probe-listing", action="store_true",
                     help="fetch all three listing pages raw, print HTML shape -- run this first too")
    ap.add_argument("--probe-deep", type=int, metavar="ORDER_ID",
                     help="round 2: search full detail-page body for real-data markers, "
                          "extract script src= and api-like URLs from detail + listing pages")
    ap.add_argument("--probe-ajax", type=int, metavar="ORDER_ID",
                     help="round 3: dump ajax/DataTable(/.json/api occurrences with context, "
                          "plus the last 4000 chars of body, for the listing + detail page")
    ap.add_argument("--probe-datatable", choices=list(LISTING_URLS),
                     help="round 4: GET the listing page for cookies/csrf, then attempt the "
                          "real DataTables serverSide POST and print what comes back")
    ap.add_argument("--backfill", action="store_true",
                     help="pull every order from all 3 listing kinds via the DataTables ajax "
                          "endpoint (confirmed live) and upsert into cci_orders")
    ap.add_argument("--update", action="store_true",
                     help="pull newest-first per listing kind, stop at the first "
                          "already-indexed order_id")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--query", help="run a raw SQL SELECT against cci_orders")
    args = ap.parse_args()

    if args.probe:
        cmd_probe(args.probe)
    elif args.probe_listing:
        cmd_probe_listing()
    elif args.probe_deep:
        cmd_probe_deep(args.probe_deep)
    elif args.probe_ajax:
        cmd_probe_ajax(args.probe_ajax)
    elif args.probe_datatable:
        cmd_probe_datatable(args.probe_datatable)
    elif args.backfill:
        cmd_backfill()
    elif args.update:
        cmd_update()
    elif args.stats:
        cmd_stats()
    elif args.query:
        con = db()
        for row in con.execute(args.query):
            print(row)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
