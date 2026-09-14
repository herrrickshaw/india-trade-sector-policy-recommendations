#!/usr/bin/env python3
"""
pib_company_scan.py — extracts company/startup/deal mentions from PIB
press-release TITLES (data/pib_index.sqlite), across several known
announcement phrasings, into one re-runnable SQLite table plus refreshable
CSVs for review.

Built 2026-09-14 by consolidating three ad-hoc extraction passes done by hand
in one chat session (company-mention regex, CCI M&A parsing, TDB startup-
funding parsing) into one maintainable, incrementally re-runnable tool. See
data/pib_company_mentions_2026-09-14.csv, data/pib_cci_ma_mentions_2026-09-14.csv
and data/pib_tdb_startup_deals_2026-09-14.csv for the one-shot outputs this
script's logic is drawn from -- this script supersedes running that logic by
hand each time.

WHY A SEPARATE DB, NOT MORE COLUMNS ON pib_items: pib_index.sqlite is a
faithful mirror of PIB's own release feed (one row per release, PK
(kind,id)) -- this script's output is *derived*, opinionated, and will be
wrong sometimes (regex on titles, not verified fact). Keeping it in its own
table makes that boundary obvious and means re-running this script's logic
(e.g. after fixing a pattern) never touches the source-of-truth PIB mirror.

PATTERNS IMPLEMENTED (each is one function; add a fifth by adding a fifth
function, not by rewriting this file):

  1. legal_suffix  -- title contains a strong company-legal-suffix phrase
                      (Ltd/Limited/Pvt Ltd/LLP/Inc/Corp/Co.). Filtered
                      against GENERIC_HEADS, a blocklist of generic
                      government-phrase false positives already caught once
                      ("Renewable Energy", "Working Group", "Small
                      Enterprises" -- none of these are companies, but they
                      matched a first, looser version of this regex). This
                      blocklist WILL need new entries over time; when
                      --stats reports a spike in single-pattern, single-
                      mention "companies," read them before trusting them.

  2. mou_partner   -- "signs MoU with X" / "partners with X". Catches almost
                      every startup/brand-only company (no legal suffix) that
                      pattern 1 structurally cannot -- Indian startups are
                      routinely named by brand only in press coverage
                      (PhonePe, Zepto, Rapido), never by their formal Pvt Ltd
                      name.

  3. tdb_support   -- "TDB-DST supports/extends support to/signs agreement
                      with/sanctions support for (M/s )X" -- Technology
                      Development Board deep-tech/biotech/cleantech startup
                      funding announcements. CONFIRMED (2026-09-14) unique to
                      TDB among the funding bodies checked at PIB-title scale
                      (BIRAC, SERB, DBT, NRDC, SIDBI all returned zero or one
                      hit for the equivalent "X supports" phrasing) -- if a
                      future check finds one of those adopting similar
                      phrasing, add it as its own pattern function, don't
                      fold it into this one silently.

  4. cci_ma        -- "CCI approves acquisition of X by Y" / "merger of X
                      with/into Y" / "amalgamation of X ... with Y". Scoped
                      to ministry = 'Competition Commission of India' only.
                      Highest-precision of the four (every match carries both
                      target and acquirer, not just one name).

CATEGORY LOOKUP: a curated name -> category dict (PSU/CPSE, Private/MNC,
Startup, Financial/Advisory, Foreign/Global) covers names already reviewed
by hand. A name pattern 1/2 finds that ISN'T in that dict gets category
'Unknown' -- these are exactly the rows worth reading on each --scan-since
run: a new 'Unknown' company is either a genuinely new name to categorize,
or a sign the regex caught something that isn't a company at all and
GENERIC_HEADS needs another entry. Patterns 3 and 4 don't need this lookup
(TDB grants are ~always to a startup; CCI parties are already split into
explicit target/acquirer roles).

Usage:
  python3 scripts/pib_company_scan.py --scan-all
  python3 scripts/pib_company_scan.py --scan-since 2026-08-26
  python3 scripts/pib_company_scan.py --export-csv
  python3 scripts/pib_company_scan.py --stats
  python3 scripts/pib_company_scan.py --new-since 2026-08-26   # only rows added by
                                                                 # the most recent scan
                                                                 # that started after
                                                                 # this date -- the
                                                                 # "what's new" view

DB: data/pib_company_mentions.sqlite (table mentions)
"""
import argparse
import datetime as dt
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DB = ROOT / "data/pib_index.sqlite"
OUT_DB = ROOT / "data/pib_company_mentions.sqlite"

COMPANY_TAIL = r"[A-Z][A-Za-z0-9&.,\'\-\s]{2,80}?(?:Pvt\.?\s*Ltd\.?|Private\s+Limited|Ltd\.?|Limited|LLP|Inc\.?|Corp\.?|Corporation|Co\.)?"

# ---------------------------------------------------------------- pattern 1

GENERIC_HEADS = {
    "renewable energy", "heavy industries", "food processing industries", "eight core industries",
    "national defence", "food corporation", "medium enterprises", "network planning group",
    "combined defence", "clean energy", "india energy", "union steel", "atomic energy",
    "technical textiles", "emerging technologies", "green energy", "solar energy",
    "traditional systems", "union textiles", "national energy", "village industries",
    "joint working group", "india", "civil defence", "public enterprises", "specialty steel",
    "india pharma", "nuclear energy", "central public sector enterprises", "indian defence",
    "sco defence", "digital solutions", "unincorporated sector enterprises", "small enterprises",
    "asean defence", "india semiconductor", "international energy", "tourism working group",
    "indian steel", "working group", "climate sustainability working group", "national technical textiles",
    "micro food processing enterprises", "education working group", "secondary steel",
    "mission steering group", "empowered group", "global energy", "joint defence",
    "expert group", "development corporation", "india-australia defence", "sustainable energy",
    "modern technologies", "digital india corporation", "state insurance corporation",
    "culture working group", "investment working group", "new technologies", "bilateral working group",
    "private limited", "pvt. ltd", "pte. ltd", "india ltd", "india inc", "municipal corporation",
}

# Deliberately its own regex, NOT reusing COMPANY_TAIL: that constant's suffix
# group is optional (needed for patterns 2/3, where a name legitimately has no
# legal suffix), so reusing it here matched bare capitalized words ("Minister",
# "National") against nothing but noise on the first real run of this script
# (523,485 rows from 124,730 releases -- a dead giveaway something was matching
# unconditionally). This one requires the suffix.
SUFFIX_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&.\'\-]*(?:\s+(?:[A-Z][A-Za-z0-9&.\'\-]*|and|of|&))*\s+"
    r"(?:Pvt\.?\s*Ltd\.?|Private\s+Limited|Ltd\.?|Limited|LLP|Inc\.?|Corp\.?|Corporation|Co\.))\b"
)


def pattern_legal_suffix(date, ministry, title, url):
    out = []
    for m in SUFFIX_RE.finditer(title):
        name = m.group(1).strip()
        if name.lower() in GENERIC_HEADS or len(name) < 6:
            continue
        out.append({"pattern": "legal_suffix", "role": "company", "company_name": name})
    return out


# ---------------------------------------------------------------- pattern 2

MOU_PATTERNS = [
    re.compile(r"(?:signs?|sign(?:ed|ing)?)\s+(?:an?\s+)?MoU\s+with\s+(?P<name>[A-Z][A-Za-z0-9&.,\'\-\s]{2,60}?)(?:\s+to\b|\s+for\b|\s+in\b|,|\.|$)"),
    re.compile(r"partners?\s+with\s+(?P<name>[A-Z][A-Za-z0-9&.,\'\-\s]{2,60}?)(?:\s+to\b|\s+for\b|,|\.|$)"),
]
MOU_STOPWORDS = {"the", "india", "startups", "startup"}


def pattern_mou_partner(date, ministry, title, url):
    out = []
    for pat in MOU_PATTERNS:
        for m in pat.finditer(title):
            name = m.group("name").strip().rstrip(".")
            if len(name) < 3 or name.lower() in MOU_STOPWORDS:
                continue
            out.append({"pattern": "mou_partner", "role": "company", "company_name": name})
    return out


# ---------------------------------------------------------------- pattern 3

TDB_MS_PAT = re.compile(r"M/s\.?\s+(?P<name>" + COMPANY_TAIL + r")(?:,\s*[A-Z][a-zA-Z\s]{2,25}?)?\s*(?:for\b|under\b|to\b|with\b|,|\.|$)", re.I)
TDB_BY_PAT = re.compile(r"\bby\s+M/s\.?\s+(?P<name>" + COMPANY_TAIL + r")(?:,|\.|$)", re.I)
TDB_ACTIVE_PAT = re.compile(r"TDB(?:-DST)?\s+supports?\s+(?P<name>" + COMPANY_TAIL + r")\s+(?:for|under)\b", re.I)
TDB_REJECT_PREFIXES = ("indigenous", "development", "commercial", "financial")


def pattern_tdb_support(date, ministry, title, url):
    t = title.strip("\"“” ")
    if not re.search(r"TDB", t, re.I):
        return []
    if not re.search(r"support|agreement|sanctions|extends", t, re.I):
        return []
    for pat in (TDB_MS_PAT, TDB_BY_PAT, TDB_ACTIVE_PAT):
        m = pat.search(t)
        if m:
            name = m.group("name").strip().rstrip(",").strip()
            if len(name) > 3 and not name.lower().startswith(TDB_REJECT_PREFIXES):
                return [{"pattern": "tdb_support", "role": "startup", "company_name": name}]
    return []


# ---------------------------------------------------------------- pattern 4

CCI_ACQ_PAT = re.compile(
    r"acquisition of\s+(?P<middle>.+?)\s+by\s+(?P<acquirer>[A-Z][A-Za-z0-9&.,\'\-\s]{2,80}?)"
    r"(?:\s+from\b|\s+through\b|,\s+such that|,\s+and\b|,|\.|$)"
)
CCI_MERGE_PAT = re.compile(
    r"merger of\s+(?P<target>[A-Z][A-Za-z0-9&.,\'\-\s]{2,70}?)\s+with(?:\s+and)?\s+into\s+"
    r"(?P<acquirer>[A-Z][A-Za-z0-9&.,\'\-\s]{2,70}?)(?:,|\.|\s+such|$)"
)
CCI_AMALG_PAT = re.compile(
    r"amalgamation of\s+(?P<target>[A-Z][A-Za-z0-9&.,\'\-\s]{2,70}?)\s*,?\s+(?:holding company of\s+[A-Za-z0-9&.,\'\-\s]+?,\s+)?with\s+"
    r"(?P<acquirer>[A-Z][A-Za-z0-9&.,\'\-\s]{2,70}?)(?:,|\.|\s+such|$)"
)
CCI_STRIP1 = re.compile(r"^(?:up to\s+)?[\d.]+%\s+(?:of\s+the\s+)?(?:equity\s+)?(?:share(?:holding|\s+capital)?|stake|voting interest)s?\s+(?:of|in)\s+", re.I)
CCI_STRIP2 = re.compile(r"^(?:certain|additional|proposed)\s+(?:equity\s+)?(?:share(?:holding|\s+capital)?|stake)s?\s+(?:of|in)\s+", re.I)


def _cci_clean(s):
    s = s.strip()
    for _ in range(3):
        s2 = CCI_STRIP1.sub("", s)
        s2 = CCI_STRIP2.sub("", s2)
        if s2 == s:
            break
        s = s2
    return s.strip()


def pattern_cci_ma(date, ministry, title, url):
    if ministry != "Competition Commission of India":
        return []
    m = CCI_ACQ_PAT.search(title)
    if m:
        target = _cci_clean(m.group("middle"))
        acquirer = m.group("acquirer").strip()
        return [
            {"pattern": "cci_ma", "role": "target", "company_name": target, "deal_type": "acquisition"},
            {"pattern": "cci_ma", "role": "acquirer", "company_name": acquirer, "deal_type": "acquisition"},
        ]
    m = CCI_MERGE_PAT.search(title)
    if m:
        return [
            {"pattern": "cci_ma", "role": "target", "company_name": m.group("target").strip(), "deal_type": "merger"},
            {"pattern": "cci_ma", "role": "acquirer", "company_name": m.group("acquirer").strip(), "deal_type": "merger"},
        ]
    m = CCI_AMALG_PAT.search(title)
    if m:
        return [
            {"pattern": "cci_ma", "role": "target", "company_name": m.group("target").strip(), "deal_type": "amalgamation"},
            {"pattern": "cci_ma", "role": "acquirer", "company_name": m.group("acquirer").strip(), "deal_type": "amalgamation"},
        ]
    return []


PATTERNS = [pattern_legal_suffix, pattern_mou_partner, pattern_tdb_support, pattern_cci_ma]

# --------------------------------------------------------- category lookup
# Curated by hand 2026-09-14; extend as --stats surfaces new 'Unknown' names
# worth categorizing. Keys are matched case-sensitively against the exact
# extracted name -- if a name varies slightly across releases (e.g. "Ltd"
# vs "Limited"), it will show up twice with different categories until
# someone adds the variant here. That's a feature, not a bug: it's visible
# in --stats rather than silently merged.
CATEGORY = {
    "Coal India": "PSU/CPSE", "NTPC": "PSU/CPSE", "REC Limited": "PSU/CPSE", "NHPC": "PSU/CPSE",
    "NLC India": "PSU/CPSE", "NMDC": "PSU/CPSE", "Steel Authority of India": "PSU/CPSE",
    "Bharat Electronics": "PSU/CPSE", "Bharat Dynamics": "PSU/CPSE", "RITES": "PSU/CPSE",
    "Cochin Shipyard": "PSU/CPSE", "Mazagon Dock Shipbuilders": "PSU/CPSE",
    "Power Grid Corporation": "PSU/CPSE", "Power Finance Corporation": "PSU/CPSE",
    "Rail Vikas Nigam": "PSU/CPSE", "RailTel": "PSU/CPSE", "Hindustan Copper": "PSU/CPSE",
    "GAIL": "PSU/CPSE", "Hindustan Zinc": "PSU/CPSE",
    "Reliance Retail Ventures": "Private/MNC", "Adani Green Energy": "Private/MNC",
    "Adani Power": "Private/MNC", "Vodafone Idea": "Private/MNC", "Larsen & Toubro": "Private/MNC",
    "Maruti Suzuki India": "Private/MNC", "Mahindra & Mahindra": "Private/MNC",
    "Hero MotoCorp": "Private/MNC", "Amazon": "Private/MNC", "Netflix": "Private/MNC",
    "Meta": "Private/MNC", "IBM": "Private/MNC", "HDFC Bank": "Private/MNC",
    "Kotak Mahindra Bank": "Private/MNC", "ICICI Bank": "Private/MNC",
    "PhonePe": "Startup", "Zepto": "Startup", "Swiggy": "Startup", "Rapido": "Startup",
    "Ather Energy": "Startup", "Apna": "Startup", "CarDekho Group": "Startup",
}


def categorize(name):
    return CATEGORY.get(name, "Unknown")


# ------------------------------------------------------------------- store

def out_db():
    con = sqlite3.connect(OUT_DB)
    con.execute("""CREATE TABLE IF NOT EXISTS mentions(
        pib_id INTEGER, pattern TEXT, role TEXT, company_name TEXT, category TEXT,
        deal_type TEXT, date TEXT, ministry TEXT, title TEXT, url TEXT, extracted_at TEXT,
        PRIMARY KEY (pib_id, pattern, role, company_name))""")
    return con


def scan(since=None):
    src = sqlite3.connect(SRC_DB)
    cur = src.cursor()
    if since:
        cur.execute("SELECT id, date, ministry, title, url FROM pib_items WHERE kind='release' AND date > ?", (since,))
    else:
        cur.execute("SELECT id, date, ministry, title, url FROM pib_items WHERE kind='release'")
    rows = cur.fetchall()

    out = out_db()
    now = dt.datetime.now().isoformat(timespec="seconds")
    n_written = 0
    for pib_id, date, ministry, title, url in rows:
        if not title:
            continue
        for pat_fn in PATTERNS:
            for hit in pat_fn(date, ministry, title, url):
                category = hit.get("category") or categorize(hit["company_name"])
                out.execute(
                    "INSERT OR REPLACE INTO mentions VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (pib_id, hit["pattern"], hit["role"], hit["company_name"], category,
                     hit.get("deal_type", ""), date, ministry, title, url, now),
                )
                n_written += 1
    out.commit()
    print(f"scanned {len(rows)} releases{' since ' + since if since else ''}, wrote {n_written} mention rows")


def cmd_stats():
    con = out_db()
    print("--- by pattern ---")
    for row in con.execute("SELECT pattern, COUNT(*) FROM mentions GROUP BY pattern ORDER BY 2 DESC"):
        print(f"  {row[1]:5d}  {row[0]}")
    print("--- by category (legal_suffix + mou_partner only) ---")
    for row in con.execute("SELECT category, COUNT(*) FROM mentions WHERE pattern IN ('legal_suffix','mou_partner') GROUP BY category ORDER BY 2 DESC"):
        print(f"  {row[1]:5d}  {row[0]}")
    n_unknown = con.execute("SELECT COUNT(DISTINCT company_name) FROM mentions WHERE category='Unknown'").fetchone()[0]
    print(f"distinct 'Unknown'-category names needing review: {n_unknown}")


def cmd_new_since(since):
    con = out_db()
    print(f"mention rows extracted_at >= a scan that covered releases since {since}:")
    for row in con.execute(
        "SELECT date, pattern, role, company_name, category, title FROM mentions "
        "WHERE date > ? ORDER BY date DESC", (since,)
    ):
        print(row)


def cmd_export_csv():
    import csv
    con = out_db()
    exports = {
        "legal_suffix": ("data/pib_company_mentions_latest.csv",
                          "SELECT company_name, category, COUNT(*) mentions, MIN(date), MAX(date), title, url "
                          "FROM mentions WHERE pattern='legal_suffix' GROUP BY company_name ORDER BY category, mentions DESC"),
        "mou_partner": ("data/pib_mou_partner_mentions_latest.csv",
                         "SELECT date, company_name, category, title, url FROM mentions WHERE pattern='mou_partner' ORDER BY date DESC"),
        "tdb_support": ("data/pib_tdb_startup_deals_latest.csv",
                         "SELECT date, company_name, title, url FROM mentions WHERE pattern='tdb_support' ORDER BY date DESC"),
        "cci_ma": ("data/pib_cci_ma_mentions_latest.csv",
                    "SELECT date, deal_type, role, company_name, title, url FROM mentions WHERE pattern='cci_ma' ORDER BY date DESC"),
    }
    for name, (path, query) in exports.items():
        cur = con.execute(query)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        with open(ROOT / path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"wrote {len(rows)} rows -> {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scan-all", action="store_true")
    ap.add_argument("--scan-since", metavar="YYYY-MM-DD")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--new-since", metavar="YYYY-MM-DD")
    ap.add_argument("--export-csv", action="store_true")
    args = ap.parse_args()

    if args.scan_all:
        scan()
    elif args.scan_since:
        scan(since=args.scan_since)
    elif args.stats:
        cmd_stats()
    elif args.new_since:
        cmd_new_since(args.new_since)
    elif args.export_csv:
        cmd_export_csv()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
