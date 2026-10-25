import pytest

import sebi_index as sebi


@pytest.mark.parametrize("raw,iso", [("Jun 11, 2026", "2026-06-11"), ("11-06-2026", None), ("", None)])
def test_normalize_date(raw, iso):
    assert sebi.normalize_date(raw) == iso


@pytest.mark.parametrize("title,company,ftype", [
    ("Synth Labs Limited - DRHP", "Synth Labs Limited", "DRHP"),
    ("Synth Labs Limited - UDRHP1", "Synth Labs Limited", "UDRHP (Updated DRHP)"),
    ("Synth-Tech Ltd - Addendum to DRHP", "Synth-Tech Ltd", "Addendum to DRHP"),
    ("Synth Ltd - corrigendum to drhp", "Synth Ltd", "Corrigendum to DRHP"),
    ("Synth Ltd Red Herring Prospectus", "Synth Ltd Red Herring Prospectus", None),
])
def test_parse_title(title, company, ftype):
    assert sebi.parse_title(title) == (company, ftype)
