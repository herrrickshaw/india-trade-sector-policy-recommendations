"""scripts/build_state_fdi_iem.py: state-label reconciliation and the FDI-vs-IEM intensity join."""
import json

import pytest


@pytest.fixture
def M(load):
    return load("build_state_fdi_iem")


@pytest.mark.parametrize("raw,expected", [
    ("JAMMU AND KASHMIR", "Jammu and Kashmir"),
    ("Jammu & Kashmir", "Jammu and Kashmir"),
    ("  tamil   nadu ", "Tamil Nadu"),
    ("Orissa", "Odisha"), ("PONDICHERRY", "Puducherry"), ("Uttaranchal", "Uttarakhand"),
    ("Telengana", "Telangana"), ("Lakshwadeep", "Lakshadweep"),
    ("Dadra and Nagar Haveli", "Dadra and Nagar Haveli and Daman and Diu"),
    ("DAMAN & DIU", "Dadra and Nagar Haveli and Daman and Diu"),
    ("Delhi.", "Delhi"),
    ("ANDAMAN AND NICOBAR ISLANDS", "Andaman and Nicobar Islands"),
    ("", ""), (None, ""),
])
def test_norm(M, raw, expected):
    assert M.norm(raw) == expected


def write_src(M, tmp_path, monkeypatch, data):
    src = tmp_path / "state_fdi_iem_full.json"
    src.write_text(json.dumps(data))
    monkeypatch.setattr(M, "SRC", str(src))
    return src


def built(repo):
    files = list((repo / "data").glob("state_fdi_vs_iem_*.json"))
    assert len(files) == 1
    return json.loads(files[0].read_text()), files[0]


def test_missing_source_exits(M, tmp_path, monkeypatch):
    monkeypatch.setattr(M, "SRC", str(tmp_path / "nope.json"))
    with pytest.raises(SystemExit) as e:
        M.main()
    assert "missing" in str(e.value) and "extraction has not landed yet" in str(e.value)


DATA = {
    "fdi_cumulative_annexure_c": {"period": "Oct 2019 - Mar 2026", "source_title": "Annex C", "url": "http://f", "caveat_verbatim": "cv", "ignored": 1, "rows": [
        {"state": "MAHARASHTRA", "usd_mn": 600},
        {"state": "Gujarat", "usd_mn": 300},
        {"state": "ASSAM", "usd_mn": 0.004},
        {"state": "Ladakh", "usd_mn": 50},
        {"state": "Grand Total", "usd_mn": 99999},
        {"state": "State not indicated", "usd_mn": 77},
        {"state": "", "usd_mn": 5},
        {"state": "Orissa", "usd_mn": None},
        {"state": "Daman & Diu", "usd_mn": 10}, {"state": "Dadra and Nagar Haveli", "usd_mn": 20},
    ]},
    "fdi_fy_table": {"rows": [{"state": "ShouldNotBeUsed", "usd_mn": 1}]},
    "iem_part_b": {"period": "p", "rows": [
        {"state": "Maharashtra", "year": 2020, "rs_cr": 100}, {"state": "Maharashtra", "year": "2021", "rs_cr": 100},
        {"state": "Maharashtra", "year": "2019", "rs_cr": 99999},                        # excluded year
        {"state": "Gujarat", "year": "Up to Dec 2025", "rs_cr": 100},
        {"state": "Gujarat", "year": 2018, "rs_cr": 5000},
        {"state": "Sikkim", "year": 2022, "rs_cr": 100},
        {"state": "Assam", "year": 2023, "rs_cr": 50},
        {"state": "Total", "year": 2023, "rs_cr": 123456},
        {"state": "Dadra and Nagar Haveli", "year": 2024, "rs_cr": 10}, {"state": "Daman and Diu", "year": 2024, "rs_cr": 10},
    ]},
    "iem_part_a": {"rows": [
        {"state": "Maharashtra", "year": 2020, "rs_cr": 400}, {"state": "Gujarat", "year": 2021, "rs_cr": 0},
        {"state": "Sikkim", "year": 2017, "rs_cr": 999},
    ]},
    "extraction_notes": ["n1"], "unavailable": ["u1"],
}


def test_main_builds_join(M, repo, tmp_path, monkeypatch, capsys):
    write_src(M, tmp_path, monkeypatch, DATA)
    M.main()
    out, path = built(repo)
    states = {r["state"]: r for r in out["states"]}
    assert [r["state"] for r in out["states"]] == sorted(states)                       # alphabetical
    assert set(states) == {"Maharashtra", "Gujarat", "Assam", "Ladakh", "Odisha", "Sikkim", "Dadra and Nagar Haveli and Daman and Diu"}
    assert out["analysis"] == "state_fdi_vs_implemented_industry" and path.name == f"state_fdi_vs_iem_{out['built']}.json"
    # FDI totals: 600+300+0.004+50+0+30 = 980.004 (Grand Total / not indicated / blank are dropped)
    assert out["totals"] == {"fdi_usd_mn": 980.0, "iem_implemented_rs_cr": 470.0, "states_with_both": 4, "states_total": 7}
    mh = states["Maharashtra"]
    assert mh["fdi_usd_mn"] == 600.0 and mh["fdi_share_pct"] == 61.22 and mh["iem_implemented_rs_cr"] == 200.0
    assert mh["iem_share_pct"] == 42.55 and mh["intensity_ratio"] == round((600 / 980.004) / (200 / 470), 4)
    assert mh["iem_filed_rs_cr"] == 400.0 and mh["conversion_pct"] == 50.0 and mh["present_in"] == "both"
    gj = states["Gujarat"]
    assert gj["iem_implemented_rs_cr"] == 100.0 and gj["iem_filed_rs_cr"] == 0.0 and gj["conversion_pct"] is None   # zero filed: no division
    assert states["Sikkim"]["present_in"] == "iem_only" and states["Sikkim"]["fdi_usd_mn"] is None and states["Sikkim"]["intensity_ratio"] is None
    assert states["Sikkim"]["iem_filed_rs_cr"] is None                                  # 2017 Part A is outside the window
    assert states["Ladakh"]["present_in"] == "fdi_only" and states["Ladakh"]["iem_share_pct"] is None
    assert states["Odisha"]["fdi_usd_mn"] == 0.0 and states["Odisha"]["present_in"] == "fdi_only"
    assert states["Assam"]["fdi_share_pct"] == 0.0 and states["Assam"]["intensity_ratio"] is not None   # tiny share is not dropped as falsy
    dd = states["Dadra and Nagar Haveli and Daman and Diu"]
    assert dd["fdi_usd_mn"] == 30.0 and dd["iem_implemented_rs_cr"] == 20.0                # separate rows merged
    assert out["window"]["fdi"] == "Oct 2019 - Mar 2026" and out["window"]["iem_years"] == ["2020", "2021", "2022", "2023", "2024", "Up to Dec 2025"]
    assert set(out["window"]["iem_years_excluded"]) == {"2017", "2018", "2019"}
    assert (out["join_reconciliation"]["fdi_rows"], out["join_reconciliation"]["iem_rows"]) == (6, 5)
    assert out["sources"]["fdi_cumulative_annexure_c"] == {"source_title": "Annex C", "url": "http://f", "period": "Oct 2019 - Mar 2026", "caveat_verbatim": "cv"}
    assert out["sources"]["fdi_fy_table"] == {} and out["extraction_notes"] == ["n1"] and out["unavailable"] == ["u1"]
    printed = capsys.readouterr().out
    assert "states: 7 total, 4 with both series" in printed and "FDI basis: Oct 2019 - Mar 2026" in printed
    lines = printed.splitlines()
    first = next(i for i, l in enumerate(lines) if l.startswith("Assam") or l.startswith("Maharashtra") or l.startswith("Gujarat"))
    assert lines[first].startswith("Assam")                                              # highest intensity ratio first
    assert "single-series states (kept, not dropped):" in printed and "  Ladakh" in printed and "iem_only" in printed
    assert printed.rstrip().endswith(str(path))


def test_main_falls_back_to_fy_rows(M, repo, tmp_path, monkeypatch, capsys):
    data = {"fdi_cumulative_annexure_c": {"rows": []},
            "fdi_fy_table": {"rows": [{"state": "Goa", "usd_mn": 10}, {"state": "GOA", "usd_mn": 5}, {"state": "Total", "usd_mn": 1}]},
            "iem_part_b": {"rows": [{"state": "Goa", "year": 2022, "rs_cr": 30}]}}
    write_src(M, tmp_path, monkeypatch, data)
    M.main()
    out, _ = built(repo)
    assert out["window"]["fdi"] == "summed financial-year rows"
    (goa,) = out["states"]
    assert goa["fdi_usd_mn"] == 15.0 and goa["fdi_share_pct"] == 100.0 and goa["iem_share_pct"] == 100.0 and goa["intensity_ratio"] == 1.0
    assert goa["iem_filed_rs_cr"] is None and goa["conversion_pct"] is None


def test_main_default_period_when_annexure_has_no_period(M, repo, tmp_path, monkeypatch, capsys):
    data = {"fdi_cumulative_annexure_c": {"rows": [{"state": "Goa", "usd_mn": 10}]}, "iem_part_b": {"rows": []}}
    write_src(M, tmp_path, monkeypatch, data)
    M.main()
    out, _ = built(repo)
    assert out["window"]["fdi"] == "cumulative" and out["states"][0]["present_in"] == "fdi_only"
    assert out["states"][0]["iem_share_pct"] is None and out["totals"]["iem_implemented_rs_cr"] == 0
    assert "single-series" in capsys.readouterr().out


def test_main_empty_source_does_not_crash(M, repo, tmp_path, monkeypatch, capsys):
    write_src(M, tmp_path, monkeypatch, {})
    M.main()
    out, _ = built(repo)
    assert out["states"] == [] and out["totals"] == {"fdi_usd_mn": 0, "iem_implemented_rs_cr": 0, "states_with_both": 0, "states_total": 0}
    assert out["window"]["iem_years"] == [] and "states: 0 total, 0 with both series" in capsys.readouterr().out
