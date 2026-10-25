import pytest

import pib_company_scan as pcs

CCI = "Competition Commission of India"


def names(rows):
    return [r["company_name"] for r in rows]


def test_legal_suffix_extracts_company():
    t = "Bharat Heavy Electricals Limited signs pact with ministry"
    assert names(pcs.pattern_legal_suffix(None, None, t, None)) == ["Bharat Heavy Electricals Limited"]


def test_legal_suffix_skips_generic_heads():
    assert pcs.pattern_legal_suffix(None, None, "Digital India Corporation launches portal", None) == []


@pytest.mark.parametrize("title,expected", [
    ("Tata Steel Ltd. commissions plant", ["Tata Steel Ltd"]),
    ("Reliance Industries Pvt Ltd invests", ["Reliance Industries Pvt Ltd"]),
    ("Larsen & Toubro Limited bags order", ["Larsen & Toubro Limited"]),
])
def test_legal_suffix_variants(title, expected):
    assert names(pcs.pattern_legal_suffix(None, None, title, None)) == expected


def test_legal_suffix_matches_dotted_co():
    """'Co.' is the only suffix alternative with a mandatory dot; the trailing
    \\b then needs a word character after the dot, so 'Mitsui & Co.' followed
    by a space or end-of-title never matched."""
    rows = pcs.pattern_legal_suffix(None, None, "Mitsui & Co. to set up unit", None)
    assert names(rows) == ["Mitsui & Co"]


def test_legal_suffix_ignores_bare_generic_suffix_phrase():
    assert pcs.pattern_legal_suffix(None, None, "says India Ltd now", None) == []


def test_mou_partner():
    t = "NITI Aayog signs MoU with Microsoft India to boost AI skilling"
    assert names(pcs.pattern_mou_partner(None, None, t, None)) == ["Microsoft India"]


def test_mou_partner_stopword_dropped():
    assert pcs.pattern_mou_partner(None, None, "Ministry partners with India for growth", None) == []


@pytest.mark.parametrize("title,expected", [
    ("TDB supports M/s SynthBio Pvt Ltd for indigenous enzyme production", "SynthBio Pvt Ltd"),
    ("TDB-DST supports Quantum Synth for commercialising sensors", "Quantum Synth"),
    ("TDB signs agreement with industry for development by M/s Alpha Robotics.", "Alpha Robotics"),
])
def test_tdb_support(title, expected):
    assert names(pcs.pattern_tdb_support(None, None, title, None)) == [expected]


def test_tdb_requires_support_wording():
    assert pcs.pattern_tdb_support(None, None, "TDB annual day held", None) == []


def test_birac_startups_split_on_and():
    t = "DBT-BIRAC supported start-ups AlphaGen and BetaCure have received awards"
    rows = pcs.pattern_other_startup_support(None, None, t, None)
    assert names(rows) == ["AlphaGen", "BetaCure"]
    assert {r["deal_type"] for r in rows} == {"DBT-BIRAC"}


def test_dli_chip_startup():
    t = "Chip Design Startup - SynthSilicon Raises Series A funding"
    assert names(pcs.pattern_other_startup_support(None, None, t, None)) == ["SynthSilicon"]


def test_cci_acquisition_strips_stake_prefix():
    t = "CCI approves acquisition of 26% equity shareholding of Target Co Ltd by Buyer Holdings, such that..."
    rows = pcs.pattern_cci_ma(None, CCI, t, None)
    assert [(r["role"], r["company_name"]) for r in rows] == [
        ("target", "Target Co Ltd"), ("acquirer", "Buyer Holdings")]


def test_cci_merger_and_other_ministry_ignored():
    t = "CCI approves merger of Alpha Ltd with and into Beta Ltd."
    rows = pcs.pattern_cci_ma(None, CCI, t, None)
    assert [(r["role"], r["company_name"], r["deal_type"]) for r in rows] == [
        ("target", "Alpha Ltd", "merger"), ("acquirer", "Beta Ltd", "merger")]
    assert pcs.pattern_cci_ma(None, "Ministry of Finance", t, None) == []


def test_categorize_exact_match_only():
    assert pcs.categorize("NTPC") == "PSU/CPSE"
    assert pcs.categorize("NTPC Ltd") == "Unknown"
