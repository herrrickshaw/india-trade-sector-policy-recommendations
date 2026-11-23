"""scripts/pib_company_scan.py: title patterns, category lookup, sqlite scan/stats/export (all on a tmp sqlite)."""
import csv
import sqlite3
import sys

import pytest

from conftest import run_script


@pytest.fixture
def P(load):
    return load("pib_company_scan")


def names(hits):
    return [h["company_name"] for h in hits]


# ------------------------------------------------------------- pattern_legal_suffix
def test_legal_suffix_extracts_company_with_suffix(P):
    hits = P.pattern_legal_suffix("d", "m", "MoU signed with Tata Advanced Systems Limited for drones", "u")
    assert hits == [{"pattern": "legal_suffix", "role": "company", "company_name": "Tata Advanced Systems Limited"}]


def test_legal_suffix_requires_suffix_and_skips_generic_heads(P):
    assert P.pattern_legal_suffix("d", "m", "Minister inaugurates National Mission", "u") == []
    # generic heads are compared lower-cased and skipped
    assert P.pattern_legal_suffix("d", "m", "Visit to India Ltd today", "u") == []
    assert names(P.pattern_legal_suffix("d", "m", "Group of Renewable Energy Limited", "u")) == ["Group of Renewable Energy Limited"]


def test_legal_suffix_length_boundary(P):
    # name must be >= 6 chars: "Ab Ltd" has 6 (kept), "A Ltd" has 5 (dropped)
    assert names(P.pattern_legal_suffix("d", "m", "deal with Ab Ltd signed", "u")) == ["Ab Ltd"]
    assert P.pattern_legal_suffix("d", "m", "deal with A Ltd signed", "u") == []


def test_legal_suffix_multiple_companies(P):
    t = "Alpha Industries Limited and Beta Foods LLP sign pact; Gamma Steel Corporation joins"
    assert names(P.pattern_legal_suffix("d", "m", t, "u")) == ["Alpha Industries Limited and Beta Foods LLP", "Gamma Steel Corporation"]


# ------------------------------------------------------------- pattern_mou_partner
def test_mou_partner_signs_mou_with(P):
    hits = P.pattern_mou_partner("d", "m", "NITI Aayog signs MoU with Microsoft India to boost AI", "u")
    assert [(h["pattern"], h["role"], h["company_name"]) for h in hits] == [("mou_partner", "company", "Microsoft India")]


def test_mou_partner_partners_with(P):
    hits = P.pattern_mou_partner("d", "m", "DST partners with Google for research", "u")
    assert names(hits) == ["Google"]


def test_mou_partner_stopwords_and_short_names(P):
    assert P.pattern_mou_partner("d", "m", "Ministry signs MoU with India to expand", "u") == []       # stopword
    assert P.pattern_mou_partner("d", "m", "Ministry signs MoU with The for it", "u") == []            # stopword, case-insensitive
    assert names(P.pattern_mou_partner("d", "m", "Ministry signs MoU with IBM for it", "u")) == ["IBM"]   # len == 3 kept
    assert P.pattern_mou_partner("d", "m", "nothing relevant here", "u") == []


def test_mou_partner_strips_trailing_period(P):
    assert names(P.pattern_mou_partner("d", "m", "Govt signs MoU with Acme Robotics.", "u")) == ["Acme Robotics"]


# ------------------------------------------------------------- pattern_tdb_support
def test_tdb_requires_both_keywords(P):
    assert P.pattern_tdb_support("d", "m", "Support given to M/s Foo Pvt Ltd for project", "u") == []   # no TDB
    assert P.pattern_tdb_support("d", "m", "TDB mentions M/s Foo Pvt Ltd for project", "u") == []       # no support word


def test_tdb_ms_pattern(P):
    t = "TDB supports M/s Alpha Biotech Pvt Ltd for development of vaccine"
    hits = P.pattern_tdb_support("d", "m", t, "u")
    assert hits == [{"pattern": "tdb_support", "role": "startup", "company_name": "Alpha Biotech Pvt Ltd"}]


def test_tdb_by_and_active_patterns_and_quote_stripping(P):
    assert names(P.pattern_tdb_support("d", "m", "“TDB agreement signed by M/s Beta Labs Pvt. Ltd.”", "u")) == ["Beta Labs Pvt. Ltd."]
    got = P.pattern_tdb_support("d", "m", "TDB-DST supports Gamma Energy for commercialisation", "u")
    assert names(got) == ["Gamma Energy"]


def test_tdb_rejects_generic_prefixes_and_short(P):
    assert P.pattern_tdb_support("d", "m", "TDB supports Indigenous Systems for work", "u") == []
    assert P.pattern_tdb_support("d", "m", "TDB supports Development Bank for work", "u") == []
    assert P.pattern_tdb_support("d", "m", "TDB supports Financial Corp for work", "u") == []
    assert P.pattern_tdb_support("d", "m", "TDB supports Commercial Banks for work", "u") == []
    assert P.pattern_tdb_support("d", "m", "TDB supports Abc for work", "u") == []      # len == 3 is not > 3
    assert names(P.pattern_tdb_support("d", "m", "TDB supports Abcd for work", "u")) == ["Abcd"]   # len 4 is


def test_tdb_no_name_match(P):
    assert P.pattern_tdb_support("d", "m", "TDB support scheme extended", "u") == []


# ------------------------------------------------------------- pattern_other_startup_support
def test_split_and_names(P):
    assert P._split_and_names("Alpha, Beta and Gamma Labs.") == ["Alpha", "Beta", "Gamma Labs"]
    assert P._split_and_names(" Xy , Abc ") == ["Abc"]                     # names of <= 2 chars dropped


def test_birac_multi_startup(P):
    t = "DBT-BIRAC supported start-ups Alpha Bio and Beta Gen and Gamma Cell have launched products"
    hits = P.pattern_other_startup_support("d", "m", t, "u")
    assert [h["company_name"] for h in hits] == ["Alpha Bio", "Beta Gen", "Gamma Cell"]
    # a comma ends the capture (only the first name is taken)
    t = "DBT-BIRAC supports startups Alpha Bio, Beta Gen have launched"
    assert [h["company_name"] for h in P.pattern_other_startup_support("d", "m", t, "u")] == ["Alpha Bio"]
    assert all(h["deal_type"] == "DBT-BIRAC" and h["category"] == "Startup" and h["role"] == "startup" for h in hits)


def test_dli_chip_design(P):
    t = "Chip Design Startups - Mindgrove Technologies Raises Rs 50 crore"
    hits = P.pattern_other_startup_support("d", "m", t, "u")
    assert [(h["company_name"], h["deal_type"]) for h in hits] == [("Mindgrove Technologies", "MeitY DLI Scheme")]
    assert P.pattern_other_startup_support("d", "m", "Chip Design Startup: Ab Raises seed", "u") == []   # name len 2 not > 3


def test_idex_collab_needs_idex_and_contract(P):
    t = "iDEX contract: MoD to collaborate with Zen Technologies Ltd for simulators"
    hits = P.pattern_other_startup_support("d", "m", t, "u")
    assert [(h["company_name"], h["deal_type"]) for h in hits] == [("Zen Technologies Ltd", "iDEX-DIO")]
    assert P.pattern_other_startup_support("d", "m", "MoD to collaborate with Zen Technologies Ltd for simulators", "u") == []
    assert P.pattern_other_startup_support("d", "m", "iDEX: MoD to collaborate with Zen Ltd for simulators", "u") == []   # no 'contract'
    assert P.pattern_other_startup_support("d", "m", "unrelated", "u") == []


# ------------------------------------------------------------- pattern_cci_ma
CCI = "Competition Commission of India"


def test_cci_requires_ministry(P):
    assert P.pattern_cci_ma("d", "Other", "CCI approves acquisition of Foo Ltd by Bar Ltd", "u") == []


def test_cci_acquisition(P):
    t = "CCI approves acquisition of 26% of the equity share capital of Foo Ltd by Bar Holdings Ltd, and others"
    hits = P.pattern_cci_ma("d", CCI, t, "u")
    assert [(h["role"], h["company_name"], h["deal_type"]) for h in hits] == [
        ("target", "Foo Ltd", "acquisition"), ("acquirer", "Bar Holdings Ltd", "acquisition")]


def test_cci_merger_and_amalgamation(P):
    t = "CCI approves merger of Alpha Steel Ltd with and into Beta Steel Ltd, such that"
    hits = P.pattern_cci_ma("d", CCI, t, "u")
    assert [(h["role"], h["company_name"], h["deal_type"]) for h in hits] == [
        ("target", "Alpha Steel Ltd", "merger"), ("acquirer", "Beta Steel Ltd", "merger")]
    t = "CCI approves amalgamation of Alpha Co Ltd, with Beta Co Ltd, such"
    hits = P.pattern_cci_ma("d", CCI, t, "u")
    assert [(h["role"], h["deal_type"]) for h in hits] == [("target", "amalgamation"), ("acquirer", "amalgamation")]
    assert P.pattern_cci_ma("d", CCI, "CCI approves something else", "u") == []


def test_cci_clean_strips_stake_phrases(P):
    assert P._cci_clean("  up to 49% of the equity share capital in Foo Ltd ") == "Foo Ltd"
    assert P._cci_clean("certain equity shares of Foo Ltd") == "Foo Ltd"
    assert P._cci_clean("proposed stake in Foo Ltd") == "Foo Ltd"
    assert P._cci_clean("Foo Ltd") == "Foo Ltd"
    assert P._cci_clean("10% stake in additional equity share capital of Foo Ltd") == "Foo Ltd"   # nested strips, loop


# ------------------------------------------------------------- categorize
def test_categorize(P):
    assert P.categorize("NTPC") == "PSU/CPSE"
    assert P.categorize("Swiggy") == "Startup"
    assert P.categorize("Amazon") == "Private/MNC"
    assert P.categorize("ntpc") == "Unknown"                    # case-sensitive by design
    assert P.categorize("Nobody Pvt Ltd") == "Unknown"


# ------------------------------------------------------------- sqlite scan / stats / export
def make_src(repo, rows):
    p = repo / "data/pib_index.sqlite"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE pib_items(id INTEGER, kind TEXT, date TEXT, ministry TEXT, title TEXT, url TEXT)")
    con.executemany("INSERT INTO pib_items VALUES (?,?,?,?,?,?)", rows)
    con.commit()
    con.close()


ROWS = [
    (1, "release", "2026-01-10", "MeitY", "Govt signs MoU with Microsoft India to boost AI", "u1"),
    (2, "release", "2026-02-10", "DST", "TDB supports M/s Alpha Biotech Pvt Ltd for development of vaccine", "u2"),
    (3, "release", "2026-03-10", CCI, "CCI approves acquisition of Foo Ltd by Bar Holdings Ltd", "u3"),
    (4, "release", "2026-03-11", "X", None, "u4"),                         # no title: skipped
    (5, "factsheet", "2026-03-12", "X", "Deal with Tata Advanced Systems Limited", "u5"),   # not a release
    (6, "release", "2026-04-01", "MoD", "Deal with Reliance Retail Ventures Limited", "u6"),
    (7, "release", "2026-04-02", "DBT", "DBT-BIRAC supported start-ups Alpha Bio and Beta Gen have launched", "u7"),
]


def test_scan_all_and_since(P, repo, capsys):
    make_src(repo, ROWS)
    P.scan()
    out = capsys.readouterr().out
    assert out.strip() == "scanned 6 releases, wrote 10 mention rows"
    con = sqlite3.connect(repo / "data/pib_company_mentions.sqlite")
    rows = con.execute("SELECT pib_id, pattern, role, company_name, category, deal_type, date, ministry FROM mentions ORDER BY pib_id, pattern, role, company_name").fetchall()
    assert (1, "mou_partner", "company", "Microsoft India", "Unknown", "", "2026-01-10", "MeitY") in rows
    assert (2, "tdb_support", "startup", "Alpha Biotech Pvt Ltd", "Unknown", "", "2026-02-10", "DST") in rows
    assert (3, "cci_ma", "target", "Foo Ltd", "Unknown", "acquisition", "2026-03-10", CCI) in rows
    assert (7, "other_startup_support", "startup", "Alpha Bio", "Startup", "DBT-BIRAC", "2026-04-02", "DBT") in rows
    assert not [r for r in rows if r[0] in (4, 5)]
    assert any(r[0] == 6 and r[3] == "Reliance Retail Ventures Limited" for r in rows)
    n_all = len(rows)
    # --since is exclusive (date > since)
    P.scan(since="2026-03-11")
    out = capsys.readouterr().out
    assert "scanned 2 releases since 2026-03-11" in out
    # re-running is idempotent (INSERT OR REPLACE on the primary key)
    P.scan()
    assert con.execute("SELECT COUNT(*) FROM mentions").fetchone()[0] == n_all


def test_scan_category_hit_uses_hint_category_over_lookup(P, repo):
    make_src(repo, [(1, "release", "2026-01-01", "DBT", "DBT-BIRAC supported start-ups NTPC Labs, Beta Gen have launched", "u")])
    P.scan()
    con = sqlite3.connect(repo / "data/pib_company_mentions.sqlite")
    assert {r[0] for r in con.execute("SELECT category FROM mentions")} == {"Startup"}


def test_stats_output(P, repo, capsys):
    make_src(repo, ROWS)
    P.scan()
    capsys.readouterr()
    P.cmd_stats()
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "--- by pattern ---"
    by_pattern = {l.split()[1]: int(l.split()[0]) for l in out[1:out.index("--- by category (legal_suffix + mou_partner only) ---")]}
    assert by_pattern == {"legal_suffix": 4, "other_startup_support": 2, "cci_ma": 2, "tdb_support": 1, "mou_partner": 1}
    assert out[1].split()[1] == "legal_suffix"                         # ordered by count, descending
    assert out[out.index("--- by category (legal_suffix + mou_partner only) ---") + 1].split() == ["5", "Unknown"]
    assert out[-1] == "distinct 'Unknown'-category names needing review: 5"


def test_new_since(P, repo, capsys):
    make_src(repo, ROWS)
    P.scan()
    capsys.readouterr()
    P.cmd_new_since("2026-03-10")
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "mention rows extracted_at >= a scan that covered releases since 2026-03-10:"
    dates = [eval(l)[0] for l in out[1:]]
    assert dates == sorted(dates, reverse=True) and all(d > "2026-03-10" for d in dates) and dates


def test_export_csv(P, repo, capsys):
    make_src(repo, ROWS)
    P.scan()
    capsys.readouterr()
    P.cmd_export_csv()
    out = capsys.readouterr().out
    assert "wrote 1 rows -> data/pib_tdb_startup_deals_latest.csv" in out
    with open(repo / "data/pib_tdb_startup_deals_latest.csv", newline="") as f:
        r = list(csv.reader(f))
    assert r[0] == ["date", "company_name", "title", "url"] and r[1][:2] == ["2026-02-10", "Alpha Biotech Pvt Ltd"]
    with open(repo / "data/pib_cci_ma_mentions_latest.csv", newline="") as f:
        r = list(csv.reader(f))
    assert r[0] == ["date", "deal_type", "role", "company_name", "title", "url"] and len(r) == 3
    with open(repo / "data/pib_other_startup_recognitions_latest.csv", newline="") as f:
        r = list(csv.reader(f))
    assert r[0][:3] == ["date", "scheme", "company_name"] and len(r) == 3
    with open(repo / "data/pib_company_mentions_latest.csv", newline="") as f:
        r = list(csv.reader(f))
    assert r[0] == ["company_name", "category", "mentions", "MIN(date)", "MAX(date)", "title", "url"]


@pytest.mark.parametrize("argv,expect", [
    (["--scan-all"], "scanned 6 releases, wrote"),
    (["--scan-since", "2026-03-31"], "scanned 2 releases since 2026-03-31"),
    (["--stats"], "--- by pattern ---"),
    (["--new-since", "2026-01-01"], "mention rows extracted_at"),
    (["--export-csv"], "wrote 1 rows -> data/pib_tdb_startup_deals_latest.csv"),
    ([], "usage:"),
])
def test_main_dispatch(P, repo, monkeypatch, capsys, argv, expect):
    make_src(repo, ROWS)
    P.scan()
    capsys.readouterr()
    monkeypatch.setattr(sys, "argv", ["pib_company_scan.py", *argv])
    P.main()
    assert expect in capsys.readouterr().out
