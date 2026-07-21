#!/usr/bin/env python3
"""State-by-state: does FDI go where industry is actually built?

Compares two Indian government series for every state:
  FDI equity inflow (DPIIT) -- foreign money credited to the state
  IEM Part B (DPIIT)        -- industrial investment actually IMPLEMENTED

and computes an INTENSITY RATIO = (state's share of FDI) / (state's share of
implemented industrial investment). Above 1.0 the state books more foreign money
than its factory-building share; below 1.0 it builds more than its FDI implies.

THE TIME LIMIT IS REAL AND NOT A CHOICE. DPIIT states "State wise data is
maintained w.e.f. October, 2019". Before that the published series is by RBI
REGIONAL OFFICE, which bundles states (Mumbai = Maharashtra + Dadra & Nagar
Haveli + Daman & Diu), so a pre-2019 state series does not exist and is not
constructed here. "Historically" therefore means Oct-2019 onward.

WHAT THE RATIO CAN AND CANNOT MEAN. FDI is attributed to the registered office
of the company receiving the remittance, not the project site -- so a high ratio
may mean financial-centre bookkeeping rather than absent industry. IEM Part B
excludes services and sub-threshold projects, so it under-measures states whose
growth is services-led. The ratio is a divergence detector, not a verdict.

    python3 scripts/build_state_fdi_iem.py
"""
import datetime, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = ("/private/tmp/claude-501/-Users-umashankar/"
           "0c3e9924-9f05-4396-80c8-81c306920b86/scratchpad")
SRC = os.path.join(SCRATCH, "state_fdi_iem_full.json")

# The two source universes do not line up and must be reconciled deliberately:
#   FDI Annexure-C merges Dadra & Nagar Haveli with Daman & Diu into ONE UT and
#   carries Ladakh; the IEM appendices keep the first two SEPARATE and have no
#   Ladakh row. Joining them blind would double-count or drop states.
ALIAS = {"orissa": "Odisha", "pondicherry": "Puducherry", "uttaranchal": "Uttarakhand",
         "telengana": "Telangana", "lakshwadeep": "Lakshadweep",
         "dadra and nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
         "daman and diu": "Dadra and Nagar Haveli and Daman and Diu"}
DROP = {"state not indicated", "region not indicated", "grand total", "total"}

# IEM years usable for a window-matched comparison with FDI (Oct-2019 -> Mar-2026).
# 2017/2018 predate the FDI state series. 2019 is EXCLUDED as defective in the
# source: AR 2022-23 prints Gujarat 2019 Part B at Rs 15,18,861 cr -- about six
# times all-India in any other year -- and AR 2021-22's 2019 column repeats the
# IEM COUNT in the investment cell for most states (verified at 200 dpi, so a
# source defect, not an extraction artifact).
IEM_YEARS_IN_WINDOW = {"2020", "2021", "2022", "2023", "2024", "Up to Dec 2025"}
IEM_YEARS_EXCLUDED = {"2017": "predates the FDI state series (starts Oct-2019)",
                      "2018": "predates the FDI state series (starts Oct-2019)",
                      "2019": "DEFECTIVE IN SOURCE -- see IEM_YEARS_IN_WINDOW comment"}


def norm(s):
    """Canonicalise a state label across two sources that disagree on case and
    on '&' vs 'and' -- FDI prints 'JAMMU AND KASHMIR', IEM prints
    'Jammu & Kashmir'. Without this they read as two different states."""
    k = re.sub(r"\s+", " ", (s or "").strip()).strip(".")
    k = re.sub(r"\s*&\s*", " and ", k)
    k = re.sub(r"\s+", " ", k).strip()
    low = k.lower()
    if low in ALIAS:
        return ALIAS[low]
    return " ".join(w.lower() if w.lower() == "and" else w.capitalize() for w in k.split())


def main():
    if not os.path.exists(SRC):
        sys.exit(f"missing {SRC} -- extraction has not landed yet")
    d = json.load(open(SRC))

    # ---- FDI: prefer the cumulative Annexure-C (same window as IEM), else sum FY rows
    fdi = {}
    ann = (d.get("fdi_cumulative_annexure_c") or {}).get("rows") or []
    for r in ann:
        st = norm(r.get("state"))
        if st.lower() in DROP or not st:
            continue
        fdi[st] = fdi.get(st, 0) + float(r.get("usd_mn") or 0)
    fdi_basis = (d.get("fdi_cumulative_annexure_c") or {}).get("period") or "cumulative"
    if not fdi:
        for r in (d.get("fdi_fy_table") or {}).get("rows") or []:
            st = norm(r.get("state"))
            if st.lower() in DROP or not st:
                continue
            fdi[st] = fdi.get(st, 0) + float(r.get("usd_mn") or 0)
        fdi_basis = "summed financial-year rows"

    # ---- IEM Part B / Part A, summed over the window-matched years only
    def sum_iem(key):
        acc, used = {}, set()
        for r in (d.get(key) or {}).get("rows") or []:
            st, yr = norm(r.get("state")), str(r.get("year"))
            if st.lower() in DROP or not st or yr not in IEM_YEARS_IN_WINDOW:
                continue
            acc[st] = acc.get(st, 0) + float(r.get("rs_cr") or 0)
            used.add(yr)
        return acc, used
    iem, iem_years = sum_iem("iem_part_b")
    iem_a, _ = sum_iem("iem_part_a")

    tot_f, tot_i = sum(fdi.values()), sum(iem.values())
    states = sorted(set(fdi) | set(iem))
    rows = []
    for st in states:
        f, i = fdi.get(st), iem.get(st)
        fs = (f / tot_f * 100) if (f is not None and tot_f) else None
        isf = (i / tot_i * 100) if (i is not None and tot_i) else None
        # NB: test for None, not truthiness -- a state with a genuinely tiny share
        # (Assam: 0.004% of FDI) rounds to 0.00 and would be silently dropped.
        ratio = (fs / isf) if (fs is not None and isf) else None
        rows.append({
            "state": st,
            "fdi_usd_mn": round(f, 2) if f is not None else None,
            "fdi_share_pct": round(fs, 2) if fs is not None else None,
            "iem_implemented_rs_cr": round(i, 2) if i is not None else None,
            "iem_share_pct": round(isf, 2) if isf is not None else None,
            "intensity_ratio": round(ratio, 4) if ratio is not None else None,
            "iem_filed_rs_cr": round(iem_a[st], 2) if st in iem_a else None,
            "conversion_pct": (round(i / iem_a[st] * 100, 1)
                               if st in iem_a and iem_a[st] and i is not None else None),
            "present_in": ("both" if f is not None and i is not None
                           else "fdi_only" if f is not None else "iem_only"),
        })
    both = [r for r in rows if r["intensity_ratio"] is not None]
    both.sort(key=lambda r: -r["intensity_ratio"])

    out = {
        "analysis": "state_fdi_vs_implemented_industry",
        "built": datetime.date.today().isoformat(),
        "window": {"fdi": fdi_basis, "iem_years": sorted(iem_years),
                   "iem_years_excluded": IEM_YEARS_EXCLUDED,
                   "year_basis_mismatch": ("IEM years are CALENDAR years; FDI is a cumulative window "
                                           "running Oct-2019 to Mar-2026. The two are close but not "
                                           "coterminous and are not directly alignable."),
                   "iem_latest_is_part_year": ("'Up to Dec 2025' is a PART-YEAR column, not a full "
                                               "year, and DPIIT revises prior years between reports.")},
        "time_limit_note": (
            "DPIIT maintains state-wise FDI only from October 2019; the earlier published series is by "
            "RBI regional office and bundles states, so no pre-2019 state series exists and none is "
            "constructed here."),
        "interpretation_note": (
            "Ratio = share of FDI / share of implemented industrial investment. It detects divergence, "
            "not virtue. FDI is credited to the registered office of the receiving company, not the "
            "project site, so a high ratio can mean financial-centre bookkeeping rather than absent "
            "industry; IEM Part B excludes services and sub-threshold projects, so it under-measures "
            "services-led states."),
        "join_reconciliation": {
            "fdi_rows": len(fdi), "iem_rows": len(iem),
            "merged": "IEM's separate Dadra & Nagar Haveli and Daman & Diu rows are summed to match "
                      "FDI Annexure-C's single merged UT",
            "fdi_only_expected": ["Ladakh (no IEM row exists)"],
            "iem_only_expected": ["Andaman & Nicobar", "Lakshadweep", "Sikkim (no FDI row printed)"]},
        "totals": {"fdi_usd_mn": round(tot_f, 2), "iem_implemented_rs_cr": round(tot_i, 2),
                   "states_with_both": len(both), "states_total": len(rows)},
        "states": rows,
        "sources": {k: {kk: vv for kk, vv in (d.get(k) or {}).items() if kk in
                        ("source_title", "url", "period", "caveat_verbatim")}
                    for k in ("fdi_fy_table", "fdi_cumulative_annexure_c", "iem_part_b", "iem_part_a")},
        "extraction_notes": d.get("extraction_notes", []),
        "unavailable": d.get("unavailable", []),
    }
    p = os.path.join(ROOT, f"data/state_fdi_vs_iem_{out['built']}.json")
    json.dump(out, open(p, "w"), indent=1)

    print(f"states: {len(rows)} total, {len(both)} with both series")
    print(f"FDI basis: {fdi_basis} | IEM years: {out['window']['iem_years']}\n")
    print(f"{'state':<26}{'FDI $mn':>11}{'FDI%':>7}{'IEM Rs cr':>13}{'IEM%':>7}{'ratio':>8}{'conv%':>7}")
    for r in both:
        print(f"{r['state'][:25]:<26}{r['fdi_usd_mn']:>11,.0f}{r['fdi_share_pct']:>6.1f}%"
              f"{r['iem_implemented_rs_cr']:>13,.0f}{r['iem_share_pct']:>6.1f}%"
              f"{r['intensity_ratio']:>7.2f}x"
              + (f"{r['conversion_pct']:>6.0f}%" if r['conversion_pct'] is not None else "     -"))
    only = [r for r in rows if r["present_in"] != "both"]
    if only:
        print("\nsingle-series states (kept, not dropped):")
        for r in only:
            print(f"  {r['state'][:28]:<30}{r['present_in']}")
    print(f"\n-> {p}")


if __name__ == "__main__":
    main()
