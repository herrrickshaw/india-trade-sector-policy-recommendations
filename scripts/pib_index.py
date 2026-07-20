#!/usr/bin/env python3
"""
pib_index.py — date-wise index of PIB press releases (by ministry) and PIB
factsheets, in a SQLite database for ready reference.

Implements the "pib_prid_sweep" item from the quarterly refresh blueprint:
gates 1 and 5 (policy announcements, PLI disbursal) pull their quarterly
deltas from PIB, and this index makes that pull reproducible — one row per
release with (date, ministry, title, PRID, url), so "what did Ministry of
Steel announce in Q1" is a SQL query instead of a browsing session.

How it talks to PIB (all learned the hard way, kept here for the next run):
  * POST to https://www.pib.gov.in — the bare domain 301s and the redirect
    turns the POST into a GET, silently resetting every filter to today.
  * AllReleasem.aspx (mobile listing) is an ASP.NET form: chain each POST's
    __VIEWSTATE/__EVENTVALIDATION tokens from the previous response.
  * The day page groups releases under <h3>Ministry</h3> headers, so one
    request per day covers every ministry — no per-ministry loop needed.
  * AllFactSheet.aspx?reg=3&lang=1 lists recent factsheets (title + date).
  * Release detail pages carry "Posted On" + ministry for cited-PRID fills.

Usage:
  python3 scripts/pib_index.py --backfill 2026-01-01 2026-07-19
  python3 scripts/pib_index.py --update            # last indexed date -> today
  python3 scripts/pib_index.py --factsheets        # index the factsheet listing
  python3 scripts/pib_index.py --seed-cited        # harvest PRIDs cited in data/*.json
  python3 scripts/pib_index.py --stats
  python3 scripts/pib_index.py --query "SELECT date,ministry,title FROM pib_items WHERE ministry LIKE '%Steel%' ORDER BY date DESC LIMIT 20"

DB: data/pib_index.sqlite  (table pib_items, PK (kind,id))
"""
import argparse, datetime as dt, html, json, re, sqlite3, sys, time
import urllib.request, urllib.parse, http.cookiejar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data/pib_index.sqlite"  # override with --db (e.g. parallel per-year backfills)
BASE = "https://www.pib.gov.in/AllReleasem.aspx?MenuId=3&Lang=1&Reg=3"
FACTSHEETS = "https://www.pib.gov.in/AllFactSheet.aspx?reg=3&lang=1"
DETAIL = "https://www.pib.gov.in/PressReleasePage.aspx?PRID={prid}"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
SLEEP = 1.2  # politeness between requests

MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS pib_items(
        id INTEGER NOT NULL,
        kind TEXT NOT NULL DEFAULT 'release',
        date TEXT,
        ministry TEXT,
        title TEXT,
        url TEXT,
        cited_in_repo INTEGER DEFAULT 0,
        fetched_at TEXT,
        PRIMARY KEY (kind, id))""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_items_date ON pib_items(date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_items_min ON pib_items(ministry, date)")
    con.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
    return con


def opener():
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def fetch(op, url, data=None):
    hdrs = dict(UA)
    if data is not None:
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
        hdrs["Referer"] = BASE
        data = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=data, headers=hdrs)
    return op.open(req, timeout=45).read().decode("utf-8", "ignore")


def tok(name, page):
    m = re.search(r'id="%s" value="([^"]*)"' % name, page)
    return m.group(1) if m else ""


def parse_day(page):
    """Yield (ministry, prid, title) from a day-listing page."""
    # releases are grouped: <h3>Ministry</h3><li><a title='..' href='/PressReleseDetailm.aspx?PRID=N'>Title</a>
    for section in re.split(r"<h3>", page)[1:]:
        mn = re.match(r"([^<]+)</h3>", section)
        mn = re.sub(r"\s+", " ", html.unescape(mn.group(1))).strip() if mn else None
        for m in re.finditer(
                r"<a[^>]*href='/PressReleseDetailm\.aspx\?PRID=(\d+)'[^>]*>([^<]*)</a>", section):
            yield mn, int(m.group(1)), html.unescape(m.group(2)).strip()


def index_days(start, end):
    con = db()
    op = opener()
    page = fetch(op, BASE)  # prime session + tokens
    total_new = 0
    day = start
    while day <= end:
        data = {
            "script_HiddenField": "", "__EVENTTARGET": "ctl00$ContentPlaceHolder1$ddlday",
            "__EVENTARGUMENT": "", "__LASTFOCUS": "",
            "__VIEWSTATE": tok("__VIEWSTATE", page),
            "__VIEWSTATEGENERATOR": tok("__VIEWSTATEGENERATOR", page),
            "__VIEWSTATEENCRYPTED": "",
            "__EVENTVALIDATION": tok("__EVENTVALIDATION", page),
            "ctl00$Bar1$ddlregion": "3", "ctl00$Bar1$ddlLang": "1",
            "ctl00$ContentPlaceHolder1$ddlday": str(day.day),
            "ctl00$ContentPlaceHolder1$ddlMonth": str(day.month),
            "ctl00$ContentPlaceHolder1$ddlYear": str(day.year),
            "ctl00$ContentPlaceHolder1$ddlMinistry": "0",
        }
        try:
            page = fetch(op, BASE, data)
        except Exception as e:
            print(f"  {day} FETCH ERROR {e} — re-priming session", file=sys.stderr)
            time.sleep(5)
            op = opener()
            page = fetch(op, BASE)
            continue  # retry same day with fresh tokens
        shown = re.search(r'lblDate">([^<]*)<', page)
        if shown and day.strftime("%d-%B-%Y").lstrip("0") not in shown.group(1).replace(" ", " "):
            # server ignored us (token drift) — re-prime and retry once
            op = opener()
            page = fetch(op, BASE)
            continue
        rows = [(prid, "release", day.isoformat(), mn, title,
                 f"https://pib.gov.in/PressReleasePage.aspx?PRID={prid}",
                 dt.datetime.now().isoformat(timespec="seconds"))
                for mn, prid, title in parse_day(page)]
        cur = con.executemany(
            """INSERT INTO pib_items(id,kind,date,ministry,title,url,fetched_at)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(kind,id) DO UPDATE SET
                 date=excluded.date, ministry=excluded.ministry,
                 title=excluded.title, fetched_at=excluded.fetched_at""", rows)
        con.commit()
        total_new += len(rows)
        print(f"  {day}  {len(rows):>3} releases")
        con.execute("INSERT INTO meta(key,value) VALUES('last_indexed_date',?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (day.isoformat(),))
        con.commit()
        day += dt.timedelta(days=1)
        time.sleep(SLEEP)
    print(f"indexed {total_new} release rows {start} → {end}")


def index_factsheets():
    con = db()
    op = opener()
    page = fetch(op, FACTSHEETS)
    n = 0
    for m in re.finditer(
            r"<a href='/FactsheetDetails\.aspx\?Id=(\d+)'[^>]*>([^<]*)</a>"
            r"<span class='publishdatesmall'>Posted on:\s*([^<]+)", page):
        fid, title, posted = int(m.group(1)), html.unescape(m.group(2)).strip(), m.group(3).strip()
        try:
            date = dt.datetime.strptime(posted, "%d %b %Y").date().isoformat()
        except ValueError:
            date = None
        con.execute(
            """INSERT INTO pib_items(id,kind,date,ministry,title,url,fetched_at)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(kind,id) DO UPDATE SET
                 date=excluded.date, title=excluded.title, fetched_at=excluded.fetched_at""",
            (fid, "factsheet", date, None, title,
             f"https://pib.gov.in/FactsheetDetails.aspx?Id={fid}&reg=3&lang=1",
             dt.datetime.now().isoformat(timespec="seconds")))
        n += 1
    con.commit()
    print(f"indexed {n} factsheets from the listing")


def fill_from_detail(op, prid):
    """Fetch a release detail page -> (date, ministry, title) best-effort."""
    page = fetch(op, DETAIL.format(prid=prid))
    date = ministry = title = None
    # date lives in <div id="PrDateTime">…: 05 JUN 2022 2:11PM by PIB Delhi
    m = re.search(r'id="PrDateTime"[^>]*>.*?(\d{1,2})\s+([A-Z]{3})\s+(\d{4})', page, re.S) or \
        re.search(r"Posted On:\s*(\d{1,2})\s+([A-Z]{3})\s+(\d{4})", page)
    if m:
        date = dt.date(int(m.group(3)), MONTHS.get(m.group(2), 1), int(m.group(1))).isoformat()
    m = re.search(r'id="MinistryName"[^>]*>\s*([^<]+?)\s*</div>', page, re.S)
    if m:
        ministry = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
    m = re.search(r'<meta property="og:title" content="([^"]{5,})"', page) or \
        re.search(r'<h2[^>]*class="[^"]*[Tt]itle[^"]*"[^>]*>\s*([^<]{5,})', page) or \
        re.search(r"<h2[^>]*>\s*([^<]{5,}?)\s*</h2>", page)
    if m:
        title = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
    return date, ministry, title


def seed_cited():
    """Harvest every PRID / factsheet id cited in data/*.json, mark it, and
    fill date/ministry/title from detail pages where the index lacks them."""
    con = db()
    cited_rel, cited_fs = set(), set()
    for f in sorted((ROOT / "data").glob("*.json")):
        text = f.read_text(errors="ignore")
        cited_rel.update(int(x) for x in re.findall(r"PRID[\s:=]*(\d{6,7})", text))
        cited_fs.update(int(x) for x in re.findall(r"[Ff]actsheet\s*(\d{6})", text))
    print(f"cited in data/*.json: {len(cited_rel)} PRIDs, {len(cited_fs)} factsheets")
    op = opener()
    for kind, ids in (("release", cited_rel), ("factsheet", cited_fs)):
        for i in sorted(ids):
            url = (f"https://pib.gov.in/PressReleasePage.aspx?PRID={i}" if kind == "release"
                   else f"https://pib.gov.in/FactsheetDetails.aspx?Id={i}&reg=3&lang=1")
            con.execute(
                """INSERT INTO pib_items(id,kind,url,cited_in_repo,fetched_at)
                   VALUES(?,?,?,1,?)
                   ON CONFLICT(kind,id) DO UPDATE SET cited_in_repo=1""",
                (i, kind, url, dt.datetime.now().isoformat(timespec="seconds")))
            if kind == "release":
                row = con.execute("SELECT date FROM pib_items WHERE kind='release' AND id=?",
                                  (i,)).fetchone()
                if row and not row[0]:
                    try:
                        date, ministry, title = fill_from_detail(op, i)
                        con.execute("UPDATE pib_items SET date=?,ministry=?,title=? "
                                    "WHERE kind='release' AND id=?", (date, ministry, title, i))
                        print(f"  PRID {i}: {date} · {ministry} · {(title or '')[:60]}")
                        time.sleep(SLEEP)
                    except Exception as e:
                        print(f"  PRID {i}: detail fetch failed ({e})", file=sys.stderr)
        con.commit()
    print("seed-cited done")


def stats():
    con = db()
    for row in con.execute(
            "SELECT kind, COUNT(*), MIN(date), MAX(date), SUM(cited_in_repo) "
            "FROM pib_items GROUP BY kind"):
        print(f"{row[0]:<10} rows={row[1]:<6} dates {row[2]} → {row[3]}  cited={row[4]}")
    print("\ntop ministries:")
    for row in con.execute(
            "SELECT ministry, COUNT(*) c FROM pib_items WHERE ministry IS NOT NULL "
            "GROUP BY ministry ORDER BY c DESC LIMIT 12"):
        print(f"  {row[1]:>4}  {row[0]}")


def main():
    global DB_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", help="alternate sqlite path (parallel backfills merge later)")
    ap.add_argument("--backfill", nargs=2, metavar=("FROM", "TO"))
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--factsheets", action="store_true")
    ap.add_argument("--seed-cited", action="store_true")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--query")
    a = ap.parse_args()
    if a.db:
        DB_PATH = Path(a.db)
    if a.backfill:
        index_days(dt.date.fromisoformat(a.backfill[0]), dt.date.fromisoformat(a.backfill[1]))
    if a.update:
        con = db()
        row = con.execute("SELECT value FROM meta WHERE key='last_indexed_date'").fetchone()
        start = (dt.date.fromisoformat(row[0]) + dt.timedelta(days=1)) if row else \
            dt.date.today() - dt.timedelta(days=7)
        index_days(start, dt.date.today())
    if a.factsheets:
        index_factsheets()
    if a.seed_cited:
        seed_cited()
    if a.stats:
        stats()
    if a.query:
        for row in db().execute(a.query):
            print(" | ".join("" if v is None else str(v) for v in row))
    if not any([a.backfill, a.update, a.factsheets, a.seed_cited, a.stats, a.query]):
        ap.print_help()


if __name__ == "__main__":
    main()
