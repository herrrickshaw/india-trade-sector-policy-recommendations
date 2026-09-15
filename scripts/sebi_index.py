#!/usr/bin/env python3
"""
sebi_index.py — SEBI Draft Offer Document (DRHP/UDRHP/Addendum/Corrigendum)
filing index, in a SQLite database for ready reference.

Converted from SEBI_web_scraper.ipynb (a Selenium/Colab notebook, still in
herrrickshaw/global-market-research-platform) into a standalone, cron-able
script, per the same request that produced pib_index.py and cci_index.py.

WHY THE NOTEBOOK "NEVER STARTED": its driver setup called
ChromeDriverManager().install(), which queries a legacy chromedriver-
download endpoint with no matching entries for Chrome 115+ -- it hangs
rather than erroring. Fixed here by using Selenium's own built-in Selenium
Manager (webdriver.Chrome(options=...) with no explicit Service/driver-
manager call) -- built into Selenium 4.6+, auto-resolves the matching
driver for whatever Chrome is actually installed, no network round-trip to
that broken endpoint.

SOURCE: SEBI's own Draft Offer Documents listing --
  https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=3&ssid=15&smid=10
JS-rendered and paginated via a "Next" link -- there is no plain-HTTP/API
path (sebi.gov.in is blocked from the cloud sandbox that maintains this
repo's other scrapers, and the page needs a real browser regardless of
that). This script MUST run somewhere with real Chrome + real network --
a local machine, not a CI box or a blocked sandbox.

Requires (one-time):
    pip3 install selenium beautifulsoup4
No webdriver-manager needed -- see the fix note above.

WHAT COUNTS AS "COMPANY" AND "FILING TYPE": the site's own title strings
follow "<Company Name> - <Filing Type>" (e.g. "Zepto Limited - UDRHP1",
"Aastha Spintex Limited - Addendum to DRHP"). parse_title() below splits on
that convention; a title that doesn't match is stored with filing_type NULL
and the raw title as company, rather than guessed at.

SECTOR / SUB-SEGMENT CLASSIFICATION IS DELIBERATELY NOT HERE: the existing
SEBI_DRHP_Company_and_Industry_Analysis.xlsx's Sector/Sub-segment columns
were built by manual/LLM analysis, not a script (confirmed: no such script
exists anywhere in this account's ~100 repos, checked 2026-09-15). This
script only reproduces the raw "Default View" scrape plus title parsing --
classification stays a separate, human-in-the-loop step.

Usage:
    python3 scripts/sebi_index.py --scrape --page-limit 60   # newest first,
                                                                upsert
    python3 scripts/sebi_index.py --new-since 2026-06-11      # rows added
                                                                after a date
    python3 scripts/sebi_index.py --stats
    python3 scripts/sebi_index.py --query "SELECT * FROM sebi_filings WHERE company LIKE '%Punjab%'"

DB: data/sebi_index.sqlite (table sebi_filings, PK url)
"""
import argparse
import datetime as dt
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data/sebi_index.sqlite"
TARGET_URL = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=3&ssid=15&smid=10"
SLEEP = 2.0  # between page clicks -- politeness floor, matching this repo's other scrapers

FILING_TYPE_RE = re.compile(
    r"^(?P<company>.+?)\s*-\s*(?P<ftype>UDRHP\d*|Addendum to DRHP|Corrigendum to DRHP|DRHP)\s*$",
    re.IGNORECASE,
)
FTYPE_CANON = {
    "drhp": "DRHP",
    "addendum to drhp": "Addendum to DRHP",
    "corrigendum to drhp": "Corrigendum to DRHP",
}


def db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS sebi_filings(
        url TEXT PRIMARY KEY,
        filing_date TEXT,        -- normalized YYYY-MM-DD where parseable
        filing_date_raw TEXT,    -- as scraped, e.g. "Jun 11, 2026"
        company TEXT,
        filing_type TEXT,        -- DRHP | UDRHP (Updated DRHP) | Addendum to DRHP |
                                  -- Corrigendum to DRHP | NULL if title didn't parse
        title TEXT,              -- full raw title as scraped
        scraped_at TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_sebi_date ON sebi_filings(filing_date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_sebi_company ON sebi_filings(company)")
    return con


def normalize_date(raw):
    """SEBI's own listing prints dates like 'Jun 11, 2026'. Returns
    YYYY-MM-DD, or None rather than guessing on anything unexpected."""
    if not raw:
        return None
    try:
        return dt.datetime.strptime(raw.strip(), "%b %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_title(title):
    """Split "<Company> - <Filing Type>" per the site's own convention.
    Returns (company, filing_type); filing_type is None, company is the
    raw title, if it doesn't match -- nothing is dropped or guessed."""
    m = FILING_TYPE_RE.match(title)
    if not m:
        return title.strip(), None
    company = m.group("company").strip()
    ftype_raw = m.group("ftype").strip()
    if ftype_raw.lower().startswith("udrhp"):
        ftype = "UDRHP (Updated DRHP)"
    else:
        ftype = FTYPE_CANON.get(ftype_raw.lower(), ftype_raw)
    return company, ftype


def cmd_scrape(page_limit):
    """Selenium-drive SEBI's Draft Offer Documents listing, newest first,
    up to page_limit pages, and upsert every DRHP/UDRHP/Addendum/
    Corrigendum row found into sebi_filings."""
    try:
        from bs4 import BeautifulSoup
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except ImportError as e:
        sys.exit(f"missing dependency ({e}) -- run: pip3 install selenium beautifulsoup4")

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
    )
    # Deliberately no Service()/ChromeDriverManager() -- Selenium Manager
    # (built into Selenium 4.6+) auto-resolves the matching driver for
    # whatever Chrome is installed locally. See module docstring.
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(TARGET_URL)

    con = db()
    extracted = []
    page_num = 1
    print("Connected to SEBI database. Parsing public listings...")
    while page_num <= page_limit:
        print(f"  Page {page_num}...")
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//table | //div[contains(@class, 'card-table')]"))
            )
        except Exception:
            print("  Table timeout -- stopping.")
            break

        soup = BeautifulSoup(driver.page_source, "html.parser")
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue
            date_text = cells[0].get_text(strip=True)
            anchor = row.find("a")
            if not anchor:
                continue
            title = anchor.get_text(strip=True)
            href = anchor.get("href", "")
            if "DRHP" not in title.upper() and "DRAFT RED HERRING" not in title.upper():
                continue
            full_url = href if href.startswith("http") else f"https://www.sebi.gov.in{href}"
            extracted.append((date_text, title, full_url))

        pagination_xpath = "//a[contains(text(), 'Next') or contains(@class, 'next') or contains(@onclick, 'next')]"
        try:
            next_btn = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, pagination_xpath)))
            classes = next_btn.get_attribute("class") or ""
            if "disabled" in classes:
                print("  Next button disabled -- end of listing.")
                break
            driver.execute_script("arguments[0].click();", next_btn)
            page_num += 1
            time.sleep(SLEEP)
        except Exception:
            print("  No next-page button found -- end of listing.")
            break

    driver.quit()

    now = dt.datetime.now().isoformat(timespec="seconds")
    for date_text, title, url in extracted:
        company, ftype = parse_title(title)
        con.execute(
            """INSERT INTO sebi_filings
               (url, filing_date, filing_date_raw, company, filing_type, title, scraped_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(url) DO UPDATE SET
                   filing_date=excluded.filing_date, filing_date_raw=excluded.filing_date_raw,
                   company=excluded.company, filing_type=excluded.filing_type,
                   title=excluded.title, scraped_at=excluded.scraped_at""",
            (url, normalize_date(date_text), date_text, company, ftype, title, now),
        )
    con.commit()
    print(f"\nExtraction complete. {len(extracted)} DRHP-family filings scraped across {page_num} page(s).")


def cmd_new_since(since_date):
    con = db()
    rows = con.execute(
        "SELECT filing_date, company, filing_type, url FROM sebi_filings "
        "WHERE filing_date > ? ORDER BY filing_date DESC",
        (since_date,),
    ).fetchall()
    print(f"{len(rows)} filings after {since_date}:")
    for r in rows:
        print(f"  {r[0] or '?':10s}  {r[1][:55]:55s}  {r[2] or '(unparsed)'}")


def cmd_stats():
    con = db()
    n_total = con.execute("SELECT COUNT(*) FROM sebi_filings").fetchone()[0]
    n_valid, dmin, dmax = con.execute(
        "SELECT COUNT(*), MIN(filing_date), MAX(filing_date) FROM sebi_filings WHERE filing_date IS NOT NULL"
    ).fetchone()
    print(f"filings indexed: {n_total}  dates {dmin} -> {dmax} "
          f"({n_total - n_valid} rows excluded from range: unparseable filing_date)")
    n_companies = con.execute("SELECT COUNT(DISTINCT company) FROM sebi_filings").fetchone()[0]
    print(f"distinct companies: {n_companies}")
    for row in con.execute(
        "SELECT COALESCE(filing_type, '(unparsed title)'), COUNT(*) FROM sebi_filings "
        "GROUP BY filing_type ORDER BY COUNT(*) DESC"
    ):
        print(f"  {row[1]:5d}  {row[0]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scrape", action="store_true", help="run the Selenium scrape and upsert into sebi_filings")
    ap.add_argument("--page-limit", type=int, default=60, help="max pages to walk (default 60)")
    ap.add_argument("--new-since", metavar="YYYY-MM-DD", help="list filings with filing_date after this date")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--query", help="run a raw SQL SELECT against sebi_filings")
    args = ap.parse_args()

    if args.scrape:
        cmd_scrape(args.page_limit)
    elif args.new_since:
        cmd_new_since(args.new_since)
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
