#!/usr/bin/env python3
"""
build_quarterly_series.py — the retrospective set: one compact Trade-Watch-
style document per fiscal year, FY2014-15 → FY2026-27 (YTD), each showing
that year's quarters of policy launches (from the classified Cabinet register
2017-2026 + traced 2014-16 launches), the year's verified trade/sector
anchors (PRID-cited waypoints from the matured-cohort traces), and the
policy↔trade↔forex linkage line.

Sources: the PIB register (data/pib_index.sqlite, 122k releases), the
classified launch datasets (154 launches 2017-2026 + traced 2014-16 cohort),
and session-verified trade/FDI/forex anchors. Figures without a stated source
do not appear — years the register cannot reach carry fewer anchors, stated
plainly.

Usage:  /opt/homebrew/bin/python3 scripts/build_quarterly_series.py
Output: reports/published/series/India_Trade_Watch_FY<yy>.pdf  (13 files)
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "reports/published/series"
SITE = "herrrickshaw.github.io/india-trade-sector-policy-recommendations"

CSS = """
@page { size: A4; margin: 16mm 15mm 15mm 15mm;
  @top-left { content: string(fy); font: 7pt Helvetica; letter-spacing:.06em; text-transform:uppercase; color:#82867a; }
  @top-right { content: "India Trade Watch — Retrospective Series"; font: 7pt Helvetica; letter-spacing:.06em; text-transform:uppercase; color:#82867a; }
  @bottom-right { content: counter(page) " / " counter(pages); font: 8pt Helvetica; color:#82867a; }
  @bottom-left { content: \"""" + SITE + """\"; font: 6.5pt Helvetica; color:#a8ab9f; } }
body { font: 9.5pt/1.5 Helvetica, Arial, sans-serif; color:#14180f; margin:0; }
h1 { string-set: fy content(); font: 600 17pt Georgia, serif; border-bottom:2.5pt solid #0e1c2e; padding-bottom:2mm; margin:0 0 1mm; }
.era { font: italic 10.5pt Georgia, serif; color:#4f5348; margin:0 0 4mm; }
h2 { font: 700 10pt Helvetica; margin:4.5mm 0 1.5mm; break-after: avoid; }
table { width:100%; border-collapse:collapse; font-size:8.3pt; margin:1mm 0 3mm; }
th { text-align:left; font: 700 6.8pt Helvetica; text-transform:uppercase; letter-spacing:.05em; color:#6b7280; border-bottom:1.2pt solid #14180f; padding:1.5mm 2mm 1.5mm 0; }
td { padding:1.6mm 2mm 1.6mm 0; border-bottom:.4pt solid #d8d2c0; vertical-align:top; line-height:1.45; }
tr { break-inside: avoid; }
td.q { font: 700 8pt "Courier New", monospace; white-space:nowrap; width:14mm; }
td.n { font-variant-numeric: tabular-nums; white-space:nowrap; }
.roster { border-left:2.5pt solid #1f6f5c; background:#eef3ef; padding:2.5mm 4mm; margin:2mm 0; font-size:8.6pt; line-height:1.55; break-inside:avoid; }
.roster b { color:#0e1c2e; }
.src { font: 6.5pt "Courier New", monospace; color:#82867a; margin:0 0 2mm; }
.anch td:first-child { font-weight:700; }
"""

# ---- The series data. Every anchor carries its source; launches carry PRIDs
#      (2017+ from the classified register; 2014-16 from traced launch records).
YEARS = [
 {"fy":"FY2014-15","era":"The starting line — and the first pricing instrument",
  "q":[("Q2","Make in India launched (25 Sep 2014) — umbrella facilitation, no fiscal instrument of its own (traced: PRID 2058603)"),
       ("Q3","Administered ethanol pricing notified for OMC procurement — the EBP loop's first instrument (traced: PRID 1536696 states 'since 2014')"),
       ("Q4","UJALA LED programme launched (5 Jan 2015) — zero-subsidy bulk procurement (PRID 2090639) · Sagarmala approved (Mar 2015) — port-led development (PRID 2251071)")],
  "anchors":[("Mobile handset factories","2 units","PRID 2099656 (baseline stated)"),("Solar installed","2.82 GW","PRID 2100603 (baseline)"),("Operational airports","74","PRID 2285671 (baseline)"),("LED retail price","~Rs 450–500","PRID 2090639 (baseline)"),("Ethanol blending","1.53% (ESY 2013-14)","PRID 1736751")],
  "roster":"<b>Linkage:</b> the year's instruments are all demand-side (procurement price, bulk buying, port-led investment) — the design family the matured cohort later proves out. Trade/forex anchors here are baselines against which every later document measures."},
 {"fy":"FY2015-16","era":"Credit and startups enter",
  "q":[("Q1","MUDRA launched (8 Apr 2015) — collateral-free micro loans (PRID 2249942) · FAME-I (Apr 2015) — EV demand incentives (PRID 1592217)"),
       ("Q4","Startup India Action Plan (16 Jan 2016) — recognition + Rs 10,000cr Fund of Funds (PRID 1480666)")],
  "anchors":[("MUDRA year-1 sanctions","Rs 1,37,449cr (FY16)","PRID 1496027"),("Recognised startups","<500 (2016 baseline)","PRID 2227597")],
  "roster":"<b>Linkage:</b> credit guarantees and fund-of-funds begin the finance leg; no direct trade instrument this year — the forex channel is indirect via micro-enterprise formalisation."},
 {"fy":"FY2016-17","era":"Routes auctioned, capex extended",
  "q":[("Q3","UDAN/RCS launched (Oct 2016) — VGF route auctions with fare caps (PRID 1488754)"),
       ("Q4","M-SIPS amended & extended (18 Jan 2017, PRID 1480674) — Rs 10,000cr capex commitment window · Solar Park scheme doubled 20→40 GW, Rs 8,100cr CFA (PRID 1514292)")],
  "anchors":[("First UDAN flight","Shimla–Delhi, 27 Apr 2017","PRID 1488754"),("MUDRA FY17 sanctions","Rs 1,80,528cr","PRID 1496027")],
  "roster":"<b>Linkage:</b> two auction/procurement designs (routes, solar parks) plus the electronics capex window that builds the pre-PLI mobile base — the imports-to-exports swing starts here."},
 {"fy":"FY2017-18","era":"The register begins; sector policies stack up",
  "q":[("Q1","National Steel Policy + DMI&SP procurement preference (May 2017, PRIDs 1489109/1489103) · SAMPADA/PMKSY Rs 6,000cr (PRID 1489119) · PP-MII order (PRID 1490691) · i3 Biopharma Mission (PRID 1490032)"),
       ("Q2","GST Budgetary Support for hill/NE units — Rs 27,413cr to 2027 (PRID 1499900)"),
       ("Q3","BharatNet Phase-II launched (Nov 2017, PRID 1509114) · Leather/footwear package Rs 2,600cr (PRID 1512800) · MDR subsidy on small digital payments (PRID 1512812) · SCBTS textiles skilling Rs 1,300cr (PRID 1513467)"),
       ("Q4","FDI liberalisation (single-brand retail/aviation, PRID 1516115) · Champion Services fund Rs 5,000cr (PRID 1522078) · NEIDS 2017 Rs 3,000cr (PRID 1525687) · Silk scheme Rs 2,161.68cr (PRID 1525692) · PMRPY full-EPF wage subsidy (PRID 1526912)")],
  "anchors":[("FDI inflow FY18","$61.96bn","PRID 1539042"),("BharatNet Phase-I","1 lakh GPs done (Dec 2017)","PRID 1515906"),("UJALA bulbs","25.01cr distributed","PRID 1496506"),("Ethanol procured","~140cr litres (ESY 17-18 est.)","PRID 1536696")],
  "roster":"<b>Linkage:</b> PMRPY's wage subsidy is the first employment-linked payout — the design ELI scales in 2025. GST support keeps hill-state manufacturing whole through the tax transition; FDI at $62bn part-funds the goods deficit."},
 {"fy":"FY2018-19","era":"Biofuels widen; exports get finance; the pre-PLI year",
  "q":[("Q1","National Policy on Biofuels 2018 (PRID 1532264) — feedstock widening + 2G VGF signal · Bamboo Mission Rs 1,290cr · Micro-Irrigation Fund Rs 5,000cr · Sugar package Rs ~7,000cr incl. ethanol-capacity soft loans (PRID 1534489) · ECGC +Rs 2,000cr, NEIA +Rs 2,000cr (PRIDs 1536689/1536687)"),
       ("Q2","PM-AASHA price support Rs 15,053cr (PRID 1545775) · Enhanced-recovery oil/gas incentives (PRID 1545777) · Sugar export assistance Rs 5,538cr (PRID 1547295) · NDCP-2018 telecom policy (PRID 1547309)"),
       ("Q3","SATAT launched (1 Oct 2018) — 5,000-plant CBG target on voluntary LOIs (PRID 1548031) · Agriculture Export Policy (PRID 1554960)"),
       ("Q4","KUSUM Rs 34,422cr (PRID 1565274) · Rooftop Solar Ph-II Rs 11,814cr (PRID 1565282) · NPE-2019 — the parent of PLI (PRID 1565285) · JI-VAN 2G-ethanol VGF Rs 1,969.5cr (PRID 1566711) · FAME-II Rs 10,000cr (PRID 1566757) · RoSCTL (PRID 1567804) · AMIF · CPSU solar VGF Rs 8,580cr")],
  "anchors":[("Mobile handset factories","127 units (Feb 2019) — M-SIPS/PMP era","PRID 1563771"),("MUDRA cumulative","15.56cr loans, Rs 7.23L cr","PRID 1562143"),("Samsung Noida","world-scale plant inaugurated (Jul 2018)","PRID 1538166")],
  "roster":"<b>Linkage:</b> the ethanol supply side gets its capacity subvention (sugar package) exactly as feedstocks widen — the loop that closes in 2022/2026. NPE-2019 seeds the PLI architecture a year before its launch. Export credit capacity (ECGC/NEIA) is recapitalised as merchandise exports plateau."},
 {"fy":"FY2019-20","era":"PLI arrives (March 2020)",
  "q":[("Q3","SWAMIH stalled-housing fund Rs 10,000cr (PRID 1590679) · PCGS NBFC guarantee (PRID 1595952)"),
       ("Q4","RoDTEP approved (13 Mar 2020, PRID 1606281) · <b>21 Mar 2020: PLI-LSEM Rs 40,995cr + SPECS 25% capex + EMC 2.0 + PLI Bulk Drugs + parks + PLI MedDev + parks</b> (PRIDs 1607487/1607491/1607489/1607483/1607485)")],
  "anchors":[("UDAN passengers","~35 lakh cumulative (Dec 2019)","PRID 1597205"),("UJALA 5-year outcome","36.13cr bulbs; price Rs 310→38; 46.92bn kWh/yr","PRID 1598481"),("FAME-I closing","2.85 lakh vehicles subsidised","PRID 1592217")],
  "roster":"<b>Linkage:</b> the production-linked era begins in the last fortnight of the year, aimed squarely at the two import heads (electronics, APIs) that COVID exposed. UJALA's closed loop (10× price crash) is already the procurement-design proof."},
 {"fy":"FY2020-21","era":"Crisis instruments + the 10-sector PLI",
  "q":[("Q1","ECLGS Rs 3L cr guarantee (PRID 1625306) · NBFC liquidity SPV Rs 30,000cr · PMMSY Rs 20,050cr · PM-FME Rs 10,000cr (May 2020) · MSME FoF + sub-debt Rs 70,000cr · AHIDF Rs 15,000cr · Shishu-MUDRA subvention · <b>Commercial coal auctions launched</b> (18 Jun 2020, PRID 1632309)"),
       ("Q2","Agriculture Infrastructure Fund Rs 1L cr (PRID 1637221) · ARHC rental housing"),
       ("Q3","<b>PLI extended to 10 sectors, Rs 1,45,980cr</b> (11 Nov 2020, PRID 1671912) · revamped PPP-VGF Rs 8,100cr · ABRY wage subsidy Rs 22,810cr · PM-WANI · ethanol-distillation subvention widened (PRID 1684626) · CBIC industrial nodes Rs 7,725cr"),
       ("Q4","PLI Telecom Rs 12,195cr (17 Feb 2021, PRID 1698685) · PLI IT-HW Rs 7,350cr + PLI Pharma Rs 15,000cr (24 Feb 2021) · PLI Food Rs 10,900cr (31 Mar 2021)")],
  "anchors":[("FDI inflow FY21","$81.72bn — record","PRID 1721268"),("Coal tranche-1","19/38 mines; Rs 6,656cr/yr state revenue","PRID 1671487"),("Ethanol blending","7.93% (ESY 20-21); 302.30cr litres","PRIDs 1736751/1782735")],
  "roster":"<b>Linkage:</b> the guarantee stack (ECLGS/AIF/AHIDF) defends the credit channel while the PLI fan-out chases the import bill; record FDI funds the gap. The ethanol subvention widening is the supply-side push that makes 10% blending reachable a year later."},
 {"fy":"FY2021-22","era":"The PLI big bang completes — and the quiet mission money",
  "q":[("Q1","PLI Solar T1 Rs 4,500cr + PLI White Goods Rs 6,238cr (7 Apr 2021) · PLI ACC Rs 18,100cr (12 May 2021)"),
       ("Q2","BharatNet PPP redesign Rs 29,432cr VGF · RDSS Rs 3.04L cr · PLI Specialty Steel Rs 6,322cr (22 Jul 2021) · NMEO-Oil Palm Rs 11,040cr · PLI Textiles Rs 10,683cr (8 Sep 2021) · PLI Auto Rs 25,938cr + Drones Rs 120cr + telecom reforms + NARCL guarantee (15 Sep 2021)"),
       ("Q3","PM MITRA parks Rs 4,445cr · AMRUT 2.0 Rs 2.77L cr · SBM-U 2.0 Rs 1.42L cr · <b>Semicon India Rs 76,000cr</b> (15 Dec 2021, PRID 1781723)"),
       ("Q4","(consolidation quarter)")],
  "anchors":[("Trade deficit FY22","−$191bn (five-year series base)","TRADESTAT series"),("Production-linked share of the year's new commitments","11.2% — missions carried 6×","five-year evolution dataset")],
  "roster":"<b>Linkage:</b> 11 PLI schemes launch — yet the rupees concentrate in RDSS/AMRUT/SBM missions. The deficit series that motivates everything starts its climb from −$191bn."},
 {"fy":"FY2022-23","era":"Rescue & consolidation; ethanol hits 10%",
  "q":[("Q1","Biofuels-2018 amended — E20 advanced to 2025-26 (18 May 2022, PRID 1826265) · <b>10% blending achieved 5 months early</b> (5 Jun 2022, PRID 1831289: Rs 41,500cr forex impact)"),
       ("Q2","BSNL revival Rs 1.64L cr (27 Jul 2022) · ECLGS corpus +Rs 50,000cr · agri interest subvention Rs 34,856cr (Aug 2022) · Solar PLI T2 Rs 19,500cr + Semicon uniform 50% support (21 Sep 2022)"),
       ("Q3","PM-DevINE Rs 6,600cr · OMC LPG grant Rs 22,000cr (Oct 2022) · HURL Barauni + RFCL Ramagundam urea plants commissioned (PRIDs 1869233/1875464)"),
       ("Q4","Green Hydrogen Mission Rs 19,744cr (4 Jan 2023, PRID 1888545) · RuPay/BHIM incentive Rs 2,600cr")],
  "anchors":[("Trade deficit FY23","−$265bn","TRADESTAT series"),("FAME-II vehicles","7.46 lakh EVs supported (Dec 2022)","PRID 1883045"),("SATAT reality","3,694 LOIs → 38 plants","PRID 1881749")],
  "roster":"<b>Linkage:</b> the ethanol loop closes its first milestone as the deficit jumps $74bn — the year that proves substitution works and shows how much more of it is needed. NIP-2012's plants finally commission, eight years after the policy."},
 {"fy":"FY2023-24","era":"Missions & VGF; zero new PLI ahead",
  "q":[("Q1","IT-Hardware PLI 2.0 Rs 17,000cr (17 May 2023) · CITIIS 2.0"),
       ("Q2","PM Vishwakarma Rs 13,000cr + PM-eBus Sewa Rs 57,613cr (16 Aug 2023) · BESS VGF Rs 3,760cr (6 Sep 2023)"),
       ("Q3","SATAT pivot: mandatory CBG blending obligation announced (25 Nov 2023, PRID 1979705) · SHG drone scheme Rs 1,261cr · EDFC construction completed (PRID 1985782)"),
       ("Q4","<b>Coal gasification incentive Rs 8,500cr</b> (24 Jan 2024, PRID 1999219) · PM-MKSSY Rs 6,000cr · <b>PM-Surya Ghar Rs 75,021cr + three semiconductor units Rs 1.26L cr investment</b> (29 Feb 2024) · IndiaAI Rs 10,300cr + UNNATI Rs 10,037cr (7 Mar 2024) · SPMEPCI EV-import policy (15 Mar 2024)")],
  "anchors":[("Trade deficit FY24","−$241bn (the one improvement year)","TRADESTAT series"),("Solar installed","~70.1 GW (Aug 2023)","PRID 1947140"),("Ethanol blending","14.6% (ESY 23-24)","Factsheet 150699"),("MUDRA 8-year","40.82cr loans, Rs 23.2L cr","PRID 1914739")],
  "roster":"<b>Linkage:</b> the deficit's only improvement year coincides with the capex pivot — and SATAT's voluntary model is formally abandoned for a mandate, the cohort's clearest design lesson happening in real time."},
 {"fy":"FY2024-25","era":"The capex year completes; funds & packages begin",
  "q":[("Q1","Offshore wind VGF Rs 7,453cr (19 Jun 2024)"),
       ("Q2","Clean Plant Programme · BioE3 policy (Aug 2024) · 12 industrial smart cities Rs 28,602cr (28 Aug 2024) · Kaynes semicon unit · Digital Agriculture Mission · <b>PM E-DRIVE Rs 10,900cr</b> + eBus PSM Rs 3,435cr (11 Sep 2024)"),
       ("Q3","NMEO-Oilseeds Rs 10,103cr (3 Oct 2024) · Space VC fund Rs 1,000cr · Natural Farming Mission (Nov 2024)"),
       ("Q4","<b>National Critical Mineral Mission Rs 34,300cr + ethanol procurement mechanism</b> (29 Jan 2025) · <b>ECMS Rs 22,919cr</b> (28 Mar 2025, PRID 2116172)")],
  "anchors":[("Trade deficit FY25","−$284bn — widening resumes","TRADESTAT series"),("Solar installed","100.33 GW (Feb 2025) — 2022 target hit 3 years late","PRID 2100603"),("Ethanol blending","19.24% (ESY 24-25)","Factsheet 150699"),("FDI FY25","$81.04bn — plateau","PRID 2131716"),("FAME-II close","13.41 lakh EVs, Rs 5,790cr","PRID 2001991")],
  "roster":"<b>Linkage:</b> the critical-minerals chain assembles as China's export controls bite; ECMS opens the components lane the electronics trade data demanded; the deficit resumes widening — the pressure that produces 2026's wave."},
 {"fy":"FY2025-26","era":"Funds, mega-packages, employment-linked payouts",
  "q":[("Q1","<b>ELI Rs 99,446cr + RDI fund Rs 1L cr</b> (1 Jul 2025) · PM Dhan-Dhaanya Krishi (16 Jul 2025)"),
       ("Q2","NCDC grant Rs 2,000cr (31 Jul 2025) · Critical-mineral recycling Rs 1,500cr (3 Sep 2025) · <b>Shipbuilding package Rs 69,725cr</b> (24 Sep 2025) · Pulses Mission Rs 11,440cr (1 Oct 2025)"),
       ("Q3","<b>Export Promotion Mission Rs 25,060cr + exporter credit guarantee Rs 20,000cr</b> (12 Nov 2025) · REPM rare-earth magnets Rs 7,280cr (26 Nov 2025) · REPM-MHI notification (15 Dec 2025)"),
       ("Q4","SIDBI equity Rs 5,000cr (21 Jan 2026) · <b>Urban Challenge Fund Rs 1L cr + Startup FoF 2.0 Rs 10,000cr</b> (14 Feb 2026) · FDI PN3 Beneficial-Owner amendment (10 Mar 2026) · Pulses detail + BHAVYA Rs 33,660cr + cotton MSP support + Small Hydro (17-18 Mar 2026) · Modified UDAN Rs 28,840cr (25 Mar 2026) · <b>LSEM tenure ends 31 Mar 2026</b>")],
  "anchors":[("Trade deficit FY26","−$333.2bn, widened 17.5%","TRADESTAT (session-verified)"),("Exports / imports","$441.7bn / $776.0bn","TRADESTAT"),("Rupee","−11.9% over 12 months to Jul 2026","session-verified"),("Ethanol","20% blending, ~5 years early","Factsheet 150699"),("MUDRA 10-year","52.37cr loans, Rs 33.65L cr","PRID 2119954"),("UDAN","663 routes, 95 aerodromes, 162.47L passengers","PRID 2245096")],
  "roster":"<b>Linkage:</b> the worst deficit year of the series meets the largest non-PLI instrument wave — funds, packages and employment-linked payouts replacing production-linked design; E20 lands as the standing proof that the loop can close."},
 {"fy":"FY2026-27 (Q1–Q2 YTD)","era":"De-risking inputs; successions arrive",
  "q":[("Q1","ECLGS 5.0 + Cotton Mission Rs 5,659cr + Vadinar ship repair + 2 semicon units (5 May 2026) · <b>Coal gasification 2026 Rs 37,500cr</b> (13 May 2026) · ATF fund Rs 10,000cr + NCRPB fleet scheme (3 Jun 2026) · NIIF +Rs 30,000cr (29 Jun 2026)"),
       ("Q2","<b>15 Jul 2026 Cabinet: MPMS Rs 62,500cr (LSEM successor) + Semicon 2.0 Rs 1,27,500cr + NIPU-2026 urea policy</b> (PRIDs 2284789/2284796/2284800) · gasification Round-1 applications open (pre-app conference 16 Jul)")],
  "anchors":[("FDI Apr–Feb FY26","$88.3bn total; $58.85bn equity (+18%)","DPIIT"),("PLI disbursal programme-wide","Rs 28,748cr ≈ 15% of outlay","PRID 2230621"),("Sector verdicts","1 green / 6 amber / 3 red","FY26 re-run")],
  "roster":"<b>Linkage:</b> succession day (15 Jul) extends the proven electronics lane and the assured-return urea design in one sitting — the matured cohort's guaranteed-terms family, applied to the two biggest verified swings still in progress."}
]


def doc(y) -> str:
    qrows = "".join(f"<tr><td class='q'>{q}</td><td>{txt}</td></tr>" for q, txt in y["q"])
    arows = "".join(f"<tr><td>{a}</td><td class='n'>{v}</td><td class='src'>{s}</td></tr>" for a, v, s in y["anchors"])
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
<h1>India Trade Watch — {y['fy']}</h1>
<p class="era">{y['era']}</p>
<h2>Policy launches by quarter</h2>
<table><tr><th>Qtr</th><th>Launches (PRID-cited; majors in bold)</th></tr>{qrows}</table>
<h2>Verified anchors for the year</h2>
<table class="anch"><tr><th>Anchor</th><th>Value</th><th>Source</th></tr>{arows}</table>
<div class="roster">{y['roster']}</div>
<div class="src">Retrospective series generated from data/pib_index.sqlite (122,141 releases, 2017–2026; pre-2017 launches traced through later
releases — the modern portal's day-wise record begins in 2017), the classified Cabinet-launch datasets, and session-verified trade/FDI/forex
anchors. Years the register cannot reach carry fewer anchors by design. Full methodology: the quarterly-refresh blueprint on {SITE}.</div>
</body></html>"""


def main():
    import weasyprint
    OUTDIR.mkdir(parents=True, exist_ok=True)
    for y in YEARS:
        slug = y["fy"].split(" ")[0].replace("/", "-")
        out = OUTDIR / f"India_Trade_Watch_{slug}.pdf"
        weasyprint.HTML(string=doc(y)).write_pdf(str(out))
        print(f"  {out.name}")
    print(f"{len(YEARS)} documents in {OUTDIR}")


if __name__ == "__main__":
    main()
