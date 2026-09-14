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

CONFIRMED SO FAR (WebSearch only -- cci.gov.in is network-egress-blocked from
the sandbox that wrote this script; every URL pattern below needs a live
--probe run on a machine with real access before trusting the parser logic):

  Listing pages (three separate order categories, each independently
  filterable by order status -- Approved, Notice Not Valid, Deemed approved
  (Reg 5A), No AAEC, Approved with modification, Transaction called off,
  Notice withdrawn, Deemed Approved (Sec 6(5)), Exempt, Under Review/RFI
  issued):
    https://www.cci.gov.in/combination/orders-section31       (main approvals)
    https://www.cci.gov.in/combination/orders-section43a_44   (penalty/enforcement,
                                                                 non-notification)
    https://www.cci.gov.in/combination/green-channel           (fast-track)

  Individual order detail pages -- sequential-looking numeric IDs (896, 1270,
  1731 all seen via WebSearch), two sub-views per order:
    https://cci.gov.in/combination/order/details/order/{id}/{sub}/orders-section31
    https://cci.gov.in/combination/order/details/summary/{id}/{sub}/orders-section31
  The {sub} segment's meaning is UNKNOWN (seen as both 0 and 1) -- probe this.

  Underlying PDFs, served from a flat, non-guessable timestamp-named path
  (cannot be enumerated directly, only discovered via the detail pages):
    https://cci.gov.in/images/caseorders/en/order{unix_ts}.pdf
    https://cci.gov.in/images/summaryorders/en/summary{unix_ts}.pdf

  Site appears to be a classic server-rendered PHP app (one snippet surfaced
  a /public/index.php/combination/... path, which reads as CodeIgniter or
  similar), NOT a Next.js/React SPA -- meaning (unlike sansad.in this repo
  fought with earlier) there is probably no separate JSON API to reverse-
  engineer; the listing and detail pages should just be plain HTML to parse
  with requests + BeautifulSoup. Confirm this on the first --probe run before
  writing any parsing logic that assumes otherwise.

UNKNOWNS TO RESOLVE ON THE FIRST LIVE RUN (in order of how much they change
the approach):
  1. Does the listing page return full HTML server-side, or does it need a
     query param / POST for pagination and status-filtering? (--probe fetches
     it plain and dumps what comes back; read the response for a total count,
     a page-size, and whether rows for *all* statuses are present without
     filtering, or only "Approved" by default.)
  2. Do individual order-detail pages carry the parsed fields (target,
     acquirer, deal value, order date, status) directly in HTML, or only a
     case number and PDF links? If the former, that alone may be enough --
     skip PDF parsing entirely for the common case and only fall back to it
     for anything the HTML doesn't state.
  3. Do the PDFs have a real text layer or are they scanned images? (CCI
     orders are almost certainly born-digital, but confirm before assuming
     pdfplumber's text extraction "just works" -- the OCR fallback pattern
     already used elsewhere in this ecosystem for eGazette PDFs is the
     backstop if not.)
  4. What is the actual ID range / total order count? (896-1731 already seen
     spans public accretion over 2022-2026; the true minimum and current
     maximum need a probe, not a guess -- do NOT hardcode a range from this
     docstring.)
  5. Rate limiting / robots.txt -- check both before any bulk pull; PIB's own
     scraper (pib_index.py) uses a 1.2s SLEEP between requests as a floor,
     start there and back off if the site complains.

RECOMMENDED BUILD ORDER (do not skip step 0):
  0. `--probe {id}` on 2-3 known IDs (896, 1270, 1731) plus the plain listing
     URL, printing raw response length/status/first 2KB, so the actual HTML
     shape is visible before writing a real parser against a guess.
  1. Once the listing page's shape is known, write `list_page()` to walk it
     (paginated or not) and collect every order ID + its order-status label.
  2. Write `detail_page()` per ID to pull whatever structured fields the
     detail HTML actually offers (this may fully replace the need for PDF
     parsing -- do not build the PDF-parsing path until step 1-2 prove the
     HTML alone is insufficient).
  3. Only if needed: PDF text extraction (pdfplumber) for deal value / party
     legal names not present in the HTML.
  4. Cross-check row counts against pib_cci_ma_mentions_2026-09-14.csv's 684
     CCI-tagged PIB releases -- CCI's own count should be >= that, since PIB
     only republishes a subset; a lower count means something in steps 1-2
     is under-collecting, not that CCI approved fewer combinations than PIB
     reported.

Usage (mirrors pib_index.py's CLI):
  python3 scripts/cci_index.py --probe 1270              # inspect one order's HTML, raw
  python3 scripts/cci_index.py --probe-listing            # inspect the listing page, raw
  python3 scripts/cci_index.py --backfill 800 1800        # once the shape is known
  python3 scripts/cci_index.py --update                   # new orders since last run
  python3 scripts/cci_index.py --stats
  python3 scripts/cci_index.py --query "SELECT date,target,acquirer FROM cci_orders WHERE target LIKE '%Steel%'"

DB: data/cci_index.sqlite (table cci_orders, PK order_id)
"""
import argparse
import datetime as dt
import re
import sqlite3
import sys
import time
import urllib.error
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
        order_kind TEXT,          -- section31 | section43a_44 | green_channel
        order_status TEXT,        -- Approved | Deemed approved | ... (verify exact labels)
        order_date TEXT,
        target TEXT,
        acquirer TEXT,
        deal_value_text TEXT,     -- raw as stated; do not attempt to normalize currency here
        order_pdf_url TEXT,
        summary_pdf_url TEXT,
        raw_html_excerpt TEXT,    -- first 500 chars of detail HTML, for debugging parse misses
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


def cmd_stats():
    con = db()
    cur = con.execute("SELECT COUNT(*), MIN(order_date), MAX(order_date) FROM cci_orders")
    n, dmin, dmax = cur.fetchone()
    print(f"orders indexed: {n}  dates {dmin} -> {dmax}")
    for row in con.execute("SELECT order_kind, COUNT(*) FROM cci_orders GROUP BY order_kind"):
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
    ap.add_argument("--backfill", nargs=2, type=int, metavar=("FROM_ID", "TO_ID"),
                     help="NOT YET IMPLEMENTED -- write list_page()/detail_page() after probing")
    ap.add_argument("--update", action="store_true", help="NOT YET IMPLEMENTED")
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
    elif args.stats:
        cmd_stats()
    elif args.query:
        con = db()
        for row in con.execute(args.query):
            print(row)
    elif args.backfill or args.update:
        print("Not implemented yet -- run --probe and --probe-listing first, "
              "then write list_page()/detail_page() against what they show.", file=sys.stderr)
        sys.exit(1)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
