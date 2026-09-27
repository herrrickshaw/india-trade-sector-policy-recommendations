#!/usr/bin/env python3
"""
pib_idex_birac_body_scan.py — names iDEX (defence-innovation) and DBT-BIRAC
(biotech) startups that PIB *release titles* never name.

Built 2026-09-27 as a follow-up to pib_company_scan.py's `other_startup_
support` pattern (title-only: 6 hits). That pattern only catches releases
that name ONE startup right in the title. Most iDEX and BIRAC coverage
doesn't -- individual spotlights are rare, but several releases attach a
full ROSTER of funded startups inside the release BODY: Parliament-question
replies ("Name of iDEX Winner" tables) and consortium-grant announcements
list dozens of companies that the title alone gives no hint of. Titles are
already indexed (data/pib_index.sqlite); this script is the one extra hop
needed to reach the body text those titles hide behind.

METHOD:
  1. Select every release whose title contains iDEX / BIRAC / "Defence
     Innovation Organisation" / "Innovations for Defence Excellence" from
     data/pib_index.sqlite (pib_company_scan.py's own title-only pattern
     covers TDB and everything else; this script is scoped to these two
     schemes because that's where CONFIRMED body says a title-only pattern
     would use are known to hide multi-company rosters not the general case).
  2. GET each release's page directly (PIB's detail pages serve fine over a
     plain GET with a browser UA -- unlike AllReleasem.aspx's day-listing,
     which needs the ASP.NET __VIEWSTATE token chain; see pib_index.py).
  3. Extract the body paragraph text, then apply the SUFFIX_RE company-name
     pattern (same regex as pib_company_scan.py's pattern_legal_suffix)
     LINE BY LINE, not on the whole blob. Roster tables render as one
     company per line once HTML is stripped -- scanning the whole blob at
     once lets the regex's greedy quantifier span from the first line's
     company name to the LAST "Ltd" anywhere in the whole table, merging
     30+ companies into one garbage "name". Confirmed the hard way on the
     first run of this script (159 raw matches, several hundred characters
     long) before switching to per-line scanning (144 clean matches).
  4. A small hand-curated blocklist drops false positives: BIRAC/DBT scheme
     acronyms (NBM, BIPP, SBIRI) and place names (Chennai, Vellore,
     Thanjavur) that regex accidentally spliced onto a legal suffix from
     unrelated text, plus large incumbents already covered elsewhere
     (Bharat Biotech, Cadila/Zydus, Biological E, Serum Institute,
     Aurobindo, Hindustan Aeronautics, Goa Shipyard, Bharat Electronics --
     these get BIRAC/iDEX press coverage but are not startups). Extend
     BLOCK_EXACT/BLOCK_SUBSTR as future runs surface more of either.
  5. Near-duplicate spellings across releases (missing space before "Pvt
     Ltd", "Ltd" vs "Limited") are merged for counting via a normalized key,
     but the longest/most-complete spelling is kept as the display name --
     variants are NOT silently discarded, same philosophy as
     pib_company_scan.py's CATEGORY dict ("visible in stats, not silently
     merged").

Usage:
    python3 scripts/pib_idex_birac_body_scan.py             # fetch + extract, write CSV
    python3 scripts/pib_idex_birac_body_scan.py --no-fetch   # reuse cached bodies, re-extract only

Cache: data/pib_idex_birac_bodies/<prid>.txt (title + body text; re-run is a
no-op per release once cached -- delete a file to force a re-fetch of it).
Output: data/pib_idex_birac_body_startups_latest.csv
"""
import argparse
import csv
import html
import re
import sqlite3
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DB = ROOT / "data/pib_index.sqlite"
BODY_CACHE = ROOT / "data/pib_idex_birac_bodies"
OUT_CSV = ROOT / "data/pib_idex_birac_body_startups_latest.csv"

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}
DETAIL = "https://www.pib.gov.in/PressReleasePage.aspx?PRID={prid}"
SLEEP = 1.0

TITLE_FILTER = """SELECT id, date, ministry, title, url FROM pib_items
    WHERE kind='release' AND (title LIKE '%iDEX%' OR title LIKE '%BIRAC%'
    OR title LIKE '%Defence Innovation Organisation%'
    OR title LIKE '%Innovations for Defence Excellence%')
    ORDER BY date"""

TAG_RE = re.compile(r"<[^>]+>")
BODY_RE = re.compile(
    r'id="PrDateTime".*?(<p[^>]*>.*?)(?:<div class="print-icons"|<div id="ReleaseIDBox"|id="Sfooter"|$)',
    re.S)

SUFFIX_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&.\'\-]*(?:\s+(?:[A-Z][A-Za-z0-9&.\'\-]*|and|of|&))*?\s+"
    r"(?:Pvt\.?\s*Ltd\.?|Private\s+Limited|Ltd\.?|Limited|LLP|Inc\b\.?|Corporation|Co\.))\b"
)
ROLE_PREFIX_RE = re.compile(
    r"^(?:CEO|Founder(?:\s*&\s*CEO)?|Co-?[Ff]ounder|Managing\s+Director|MD|Chairman|Director|"
    r"Dr\.?|Shri|Smt\.?|Mr\.?|Ms\.?)\s*(?:of\s+|,\s*)?", re.I)

BLOCK_EXACT = {
    "bharat biotech international limited", "bharat biotech international ltd",
    "cadila healthcare limited", "cadila healthcare ltd", "biological e limited",
    "biological e. limited", "hindustan aeronautics limited", "goa shipyard limited",
    "bharat electronics limited", "serum institute of india private limited",
    "aurobindo pharma limited", "spm india limited", "gennova biopharmaceuticals ltd.",
    "gennova biopharmaceuticals ltd", "virchow biotech pvt ltd.", "kinetix engineering solutions limited",
    "innovation pvt ltd", "technologies pvt ltd", "innovation communications systems pvt ltd",
    "about gennova", "bipp", "c. abdul hakeem college", "chennai",
    "christian medical college vellore association", "district", "incorporation pvt ltd",
    "india private limited", "nation.", "nbm", "medical science", "pib delhi", "programs",
    "sbiri", "thanjavur", "vellore", "winner",
    "sushil eknath ghule. siliconia technologies pvt ltd",
}
BLOCK_SUBSTR = ("minister inc", "partner inc", "veterinary inc", "medtech inc", "dex partner inc",
                "clean energy international inc", "total no. of inc", "simplification and handholding")


def clean_name(raw):
    name = raw.strip().strip(",.").strip()
    name = re.sub(r'^["“‘\']+', "", name).strip()
    if "," in name:
        segs = [s.strip() for s in name.split(",")]
        for s in reversed(segs):
            if re.search(r"(Pvt\.?\s*Ltd\.?|Private\s+Limited|Ltd\.?|Limited|LLP|Corporation|Co\.)$", s, re.I):
                name = s
                break
    if " of " in name:
        name = name.split(" of ")[-1].strip()
    prev = None
    while prev != name:
        prev = name
        name = ROLE_PREFIX_RE.sub("", name).strip()
    return name.strip(",.").strip()


def norm_key(name):
    n = re.sub(r"(?<=[a-z])(?=Pvt|Private|Technologies|Solutions|Systems|Ltd)", " ", name)
    n = re.sub(r"\s+", " ", n).strip().lower()
    n = re.sub(r"\bpvt\.?\s*ltd\.?\b", "pvt ltd", n)
    n = re.sub(r"\bprivate\s+limited\b", "pvt ltd", n)
    n = re.sub(r"\bltd\.?\b", "ltd", n)
    return n


def fetch_body(prid, title):
    path = BODY_CACHE / f"{prid}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    req = urllib.request.Request(DETAIL.format(prid=prid), headers=UA)
    page = urllib.request.urlopen(req, timeout=45).read().decode("utf-8", "ignore")
    m = BODY_RE.search(page)
    text = TAG_RE.sub(" ", m.group(1)) if m else ""
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    body = f"{title}\n---\n{text}"
    BODY_CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    time.sleep(SLEEP)
    return body


def extract_names(text, source):
    names = set()
    for line in text.split("\n"):
        for m in SUFFIX_RE.finditer(line):
            name = clean_name(m.group(1))
            key = name.lower()
            if len(name) < 6 or key in BLOCK_EXACT or any(b in key for b in BLOCK_SUBSTR):
                continue
            if not re.match(r"^[A-Z]", name):
                continue
            if " and " in name and name.count("Ltd") >= 2:
                for part in re.split(r"\s+and\s+", name):
                    names.add(part.strip())
            else:
                names.add(name)
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-fetch", action="store_true", help="reuse cached bodies only, skip HTTP")
    args = ap.parse_args()

    con = sqlite3.connect(SRC_DB)
    releases = con.execute(TITLE_FILTER).fetchall()
    print(f"{len(releases)} iDEX/BIRAC releases in scope")

    mentions = []  # (company_name, scheme, date, title, url)
    for prid, date, ministry, title, url in releases:
        if args.no_fetch:
            path = BODY_CACHE / f"{prid}.txt"
            if not path.exists():
                continue
            body = path.read_text(encoding="utf-8")
        else:
            try:
                body = fetch_body(prid, title)
            except Exception as e:
                print(f"  FAIL {prid}: {e}")
                continue
        scheme = "BIRAC" if "BIRAC" in title.upper() else "iDEX"
        for name in extract_names(body, (date, title, url)):
            mentions.append((name, scheme, date, title, url))

    groups = defaultdict(list)
    for name, scheme, date, title, url in mentions:
        groups[norm_key(name)].append((name, scheme, date, title, url))

    out_rows = []
    for key, items in groups.items():
        canonical = max({i[0] for i in items}, key=len)
        schemes = sorted({i[1] for i in items})
        sources = sorted({(i[2], i[3], i[4]) for i in items}, key=lambda x: x[0])
        out_rows.append({
            "company_name": canonical,
            "scheme": "/".join(schemes),
            "first_mentioned": sources[0][0],
            "n_source_releases": len(sources),
            "source_titles": " || ".join(s[1] for s in sources),
            "source_urls": " || ".join(s[2] for s in sources),
        })
    out_rows.sort(key=lambda r: r["company_name"].lower())

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["company_name", "scheme", "first_mentioned",
                                          "n_source_releases", "source_titles", "source_urls"])
        w.writeheader()
        w.writerows(out_rows)
    print(f"{len(mentions)} raw mentions -> {len(out_rows)} distinct companies -> {OUT_CSV}")


if __name__ == "__main__":
    main()
