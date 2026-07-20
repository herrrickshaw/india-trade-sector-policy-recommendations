#!/usr/bin/env python3
"""
build_quarterly_report.py — the SIMPLIFIED compendium: one structured
quarterly PDF following NITI Aayog's Trade Watch Quarterly template,
replacing the 19-section pixel-faithful WeasyPrint pipeline (two passes,
Chrome pre-execution, ~3h, one 6-hour layout hang) with a single generated
HTML rendered in ONE WeasyPrint pass (~1 minute, no Chrome, no page-offset
machinery, no pypdf merge — continuous page numbers and bookmarks fall out
naturally from a single document).

Template (mirroring NITI Trade Watch Quarterly's structure):
  Highlights → Merchandise trade performance → Trade by partner →
  Sector performance & verdicts → Special theme chapter →
  Trade & investment policy developments → Investment lifecycle monitor →
  Statistical annex.

Quarterly refresh: edit CONTENT below (every figure carries its source);
the deep bulletins remain the interactive layer on GitHub Pages — this
report cites them instead of reprinting them.

Usage:  /opt/homebrew/bin/python3 scripts/build_quarterly_report.py
Output: reports/published/India_Trade_Watch_Quarterly_2026Q2.pdf
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports/published/India_Trade_Watch_Quarterly_2026Q2.pdf"

EDITION = "July 2026 edition · covering FY2025-26 full-year data and Cabinet decisions to 15 Jul 2026"
SITE = "herrrickshaw.github.io/india-trade-sector-policy-recommendations"

CSS = """
@page { size: A4; margin: 17mm 15mm 16mm 15mm;
  @top-left { content: string(sec); font: 7pt Helvetica; letter-spacing:.06em; text-transform:uppercase; color:#82867a; }
  @top-right { content: "India Trade Watch — Quarterly"; font: 7pt Helvetica; letter-spacing:.06em; text-transform:uppercase; color:#82867a; }
  @bottom-right { content: counter(page) " / " counter(pages); font: 8pt Helvetica; color:#82867a; }
  @bottom-left { content: \"""" + SITE + """\"; font: 6.5pt Helvetica; color:#a8ab9f; } }
@page cover { margin: 0; @top-left {content:none} @top-right {content:none} @bottom-left {content:none} @bottom-right {content:none} }
body { font: 9.5pt/1.55 Helvetica, Arial, sans-serif; color:#14180f; margin:0; }
.cover { page: cover; height: 297mm; background:#0e1c2e; color:#f5f1e7; padding: 40mm 22mm 0; box-sizing:border-box; page-break-after: always; }
.cover .bar { height:6px; width:60mm; background:linear-gradient(90deg,#d9932f,#1f6f5c); margin-bottom:10mm; }
.cover .eyebrow { color:#d9932f; font-size:9pt; letter-spacing:.18em; text-transform:uppercase; font-weight:700; }
.cover h1 { font: 500 27pt/1.2 Georgia, serif; margin:6mm 0; }
.cover .dek { font-size:9.5pt; line-height:1.7; color:#c7cdd3; max-width:150mm; }
.cover .meta { margin-top:14mm; font-size:7.5pt; color:#93a0ad; line-height:1.9; }
h1.sec { string-set: sec content(); font: 600 16pt Georgia, serif; border-bottom:2pt solid #14180f;
  padding-bottom:2mm; margin:0 0 4mm; break-after: avoid; }
section { break-before: page; }
section.flow { break-before: auto; }
h2 { font: 700 10.5pt Helvetica; margin:5mm 0 2mm; break-after: avoid; }
p { margin: 0 0 2.6mm; }
p.lead { font-size:10pt; }
table { width:100%; border-collapse:collapse; font-size:8.3pt; margin: 2mm 0 4mm; }
th { text-align:left; font: 700 7pt Helvetica; text-transform:uppercase; letter-spacing:.05em; color:#6b7280;
  border-bottom:1.2pt solid #14180f; padding:1.6mm 2mm 1.6mm 0; }
td { padding:1.7mm 2mm 1.7mm 0; border-bottom:.4pt solid #d8d2c0; vertical-align:top; }
tr { break-inside: avoid; }
td.k { font-weight:700; }
td.n { font-variant-numeric: tabular-nums; white-space:nowrap; }
.hl { border-left:2.5pt solid #1f6f5c; background:#eef3ef; padding:3mm 4mm; margin:0 0 3mm; break-inside:avoid; }
.hl b { color:#0e1c2e; }
.warn { border-left:2.5pt solid #c98a1f; background:#f8f2e2; padding:3mm 4mm; margin:2mm 0; break-inside:avoid; }
.src { font: 6.7pt "Courier New", monospace; color:#82867a; margin:-1mm 0 3mm; }
.grid2 { display: table; width:100%; }
.grid2 > div { display: table-cell; width:50%; vertical-align:top; padding-right:5mm; }
ul { margin:0 0 3mm; padding-left:5mm; } li { margin-bottom:1.4mm; }
.toc td { border-bottom:.4pt solid #d8d2c0; }
.toc .p::after { content: target-counter(attr(href), page); float:right; color:#6b7280; }
"""


def html() -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>

<div class="cover">
  <div class="bar"></div>
  <div class="eyebrow">India Trade — Sector &amp; Policy Recommendations</div>
  <h1>India Trade Watch<br>Quarterly</h1>
  <div class="dek">A quarterly assessment of India's trade position and the policy architecture answering it,
  structured on NITI Aayog's Trade Watch Quarterly template: the merchandise position, partner
  concentrations, sector verdicts on FY2025-26 data, this quarter's special theme — the five-year migration
  of incentive design away from production-linked payouts — the policy developments register, the
  investment-lifecycle monitor, and a statistical annex. Every figure carries its source; every judgment
  shows its criteria; corrections are displayed, never silent.</div>
  <div class="meta">{EDITION}<br>Interactive bulletins, data JSONs and the PIB register (83,734 releases):
  {SITE}</div>
</div>

<section class="flow">
<h1 class="sec">Highlights</h1>
<div class="hl"><b>The position:</b> imports $776.0bn (+7.4% y/y) against exports $441.7bn (+0.9%) — a
<b>−$333.2bn deficit, widened 17.5%</b> in one year (series −191 → −265 → −241 → −284 → −333). Mineral fuels
alone are 26.2% of the import bill; China alone is a −$112.2bn bilateral gap; the rupee fell 11.9% in twelve
months.</div>
<div class="hl"><b>The verdicts:</b> re-run on FY2025-26 data, the ten-sector scorecard reads <b>1 green /
6 amber / 3 red</b> — both FY25 greens (Electronics −43.5% FDI, Medical Devices −40.4%) reversed;
Pharmaceuticals took the green slot (FDI +114% after real disbursal; Penicillin-G made in India again).</div>
<div class="hl"><b>The machinery engaged:</b> the IEM implementation ratio broke upward to <b>82% (2024) and
109.9% (2025)</b>; environmental-clearance grants accelerated 198 → 734 → 1,102/yr and correlate
<b>0.96</b> with state implementation; Gujarat runs the full chain at 33.8% of national implementation.</div>
<div class="hl"><b>The special theme:</b> incentive design has migrated away from production-linked payouts —
new PLI-type schemes fell <b>11 → 1 → 1 → 0 → 2 → 0</b> across 2021–2026, and even at the 2021 peak
production-linked outlay was only 11.2% of newly committed money. 2026's ~₹1.9 lakh crore wave de-risks
inputs: land, credit, insurance, viability gaps.</div>
<div class="hl"><b>The delivery gap persists:</b> ₹28,748cr disbursed across the PLI programme ≈ 15% of outlay
after five years (Pharma A and Electronics A− carry it; ACC has paid zero; 14 of 58 steel projects withdrew).
836 approved applications programme-wide, but only about half the schemes have ever published per-scheme
counts.</div>

<h2>Contents</h2>
<table class="toc">
<tr><td><a href="#s0">The quarter at a glance: linked movements in policy, trade &amp; forex</a><span class="p" href="#s0"></span></td></tr>
<tr><td><a href="#s1">1 · Merchandise trade performance</a><span class="p" href="#s1"></span></td></tr>
<tr><td><a href="#s2">2 · Trade by partner</a><span class="p" href="#s2"></span></td></tr>
<tr><td><a href="#s3">3 · Sector performance &amp; verdicts (FY2025-26)</a><span class="p" href="#s3"></span></td></tr>
<tr><td><a href="#s4">4 · Special theme: the migration away from production-linked design</a><span class="p" href="#s4"></span></td></tr>
<tr><td><a href="#s4b">4b · Matured schemes: the returns already in</a><span class="p" href="#s4b"></span></td></tr>
<tr><td><a href="#s5">5 · Trade &amp; investment policy developments</a><span class="p" href="#s5"></span></td></tr>
<tr><td><a href="#s6">6 · Investment lifecycle monitor</a><span class="p" href="#s6"></span></td></tr>
<tr><td><a href="#s7">7 · Statistical annex</a><span class="p" href="#s7"></span></td></tr>
</table>
</section>

<section id="s0">
<h1 class="sec">The quarter at a glance: linked movements</h1>
<p class="lead">The recurring roster this report is built around: each row pairs a <b>policy movement</b> with
the <b>trade movement</b> it answers and the <b>forex consequence</b> that links them — because in this
economy the three are one system: deficits are paid in forex, forex pressure motivates substitution policy,
and policy (when it works) shows up back in the trade ledger.</p>
<table>
<tr><th>Policy movement (this cycle)</th><th>Trade movement it answers</th><th>Forex link</th></tr>
<tr><td class="k">Import-substitution wave: gasification ₹37,500cr, NIPU-2026 urea, pulses &amp; cotton missions</td>
    <td>Deficit widened 17.5% to −$333.2bn; fuels 26.2% of the bill; fertiliser imports +118.9%</td>
    <td>Rupee −11.9%/12mo (vs ~3.3%/yr prior decade) — every widening is paid in forex; ethanol's precedent shows the loop can close (₹1.97L cr saved)</td></tr>
<tr><td class="k">MPMS + Semicon 2.0 + ECMS tranches (electronics continuity)</td>
    <td>Electronics exports +324%/5y to $54bn (smartphones #1 export) but imports doubled to $104.9bn — the component gap</td>
    <td>Net electronics forex still negative; component localisation is the swing variable the new schemes target</td></tr>
<tr><td class="k">Bharat Maritime Insurance Pool (₹12,980cr sovereign guarantee)</td>
    <td>Russia at 35.8–35.9% of crude imports, discount-driven, dirham-settled</td>
    <td>Keeps the discounted-crude lane open against insurance exclusion — a forex saving defended by insurance capacity, invisible in any scheme table</td></tr>
<tr><td class="k">Press Note 3 Beneficial-Owner amendment; FDI $88.3bn (equity +18%)</td>
    <td>China −$112.2bn bilateral deficit, 58% industrial inputs, unmoved by six years of PLI</td>
    <td>Capital inflows part-fund the goods deficit — FDI attraction and import substitution are two halves of one balance-of-payments policy</td></tr>
<tr><td class="k">Export Promotion Mission (NIRYAT PROTSAHAN subvention + guarantees) after IES lapsed</td>
    <td>Exports +0.9% y/y — flat against 7.4% import growth; USA is top-8 destination in 11 of 12 growth chapters</td>
    <td>US tariff-regime expiry (24-Jul-2026) is the near-term forex-earnings risk on the most concentrated destination</td></tr>
<tr><td class="k">E20 achieved five years early; beyond-E20 decision due 31-Oct-2026</td>
    <td>~316 lakh MT of crude never imported (cumulative)</td>
    <td>₹1.97 lakh crore of forex saved since 2014-15 — the completed loop every new substitution scheme is measured against</td></tr>
</table>
<div class="src">Figures: TRADESTAT/Exim (trade), PIB PRID-cited releases (policy), RBI-reference rupee series (forex). Each cycle this roster is re-drawn from the quarter's register — the template of this report.</div>
</section>

<section id="s1">
<h1 class="sec">1 · Merchandise trade performance</h1>
<p class="lead">FY2025-26 closed with imports of <b>$776.0bn</b> (+7.4% y/y; +26.6% over five years) against
exports of <b>$441.7bn</b> (+0.9% y/y; +4.7% over five) — imports grew 5.7× faster than exports over the
five-year window, and the deficit widened 17.5% in a single year to <b>−$333.2bn</b>.</p>
<table>
<tr><th>Indicator</th><th>FY2025-26</th><th>Change</th><th>Note</th></tr>
<tr><td class="k">Merchandise imports</td><td class="n">$776.0bn</td><td class="n">+7.4% y/y</td><td>+26.6% over five years</td></tr>
<tr><td class="k">Merchandise exports</td><td class="n">$441.7bn</td><td class="n">+0.9% y/y</td><td>+4.7% over five years</td></tr>
<tr><td class="k">Trade deficit</td><td class="n">−$333.2bn</td><td class="n">+17.5% y/y</td><td>−191 → −265 → −241 → −284 → −333</td></tr>
<tr><td class="k">Largest import head</td><td class="n">$203.4bn</td><td colspan="2">Mineral fuels (HS27) — 26.2% of the entire bill</td></tr>
<tr><td class="k">Currency</td><td class="n">₹ −11.9%/12mo</td><td colspan="2">vs ~3.3%/yr prior-decade average — deficits are paid in forex</td></tr>
<tr><td class="k">Offsetting inflow</td><td class="n">FDI $88.3bn</td><td colspan="2">total Apr–Feb FY26; $58.85bn equity (+18%)</td></tr>
</table>
<div class="src">TRADESTAT; Exim/MOCI cross-validated within 0.3%; DPIIT factsheets. Deep dives: abstract + trade bulletins on the site.</div>
<h2>The export half works; the import half does not yet</h2>
<p>Electronics exports rose <b>+324% over five years to $54bn</b> (smartphones are India's #1 export item) —
but electronics imports also doubled to <b>$104.9bn</b>: the import bill is the input side of the export
success. The only declining export chapters are the cotton-apparel ones PLI Textiles structurally misses.
Seven of twelve growth import chapters still have no matching scheme; after the 2026 launches (§5), the
remaining large uncovered heads are <b>plastics (HS39) and inorganic chemicals (HS28)</b>.</p>
</section>

<section id="s2">
<h1 class="sec">2 · Trade by partner</h1>
<table>
<tr><th>Partner</th><th>Balance / share</th><th>Reading</th></tr>
<tr><td class="k">China</td><td class="n">−$112.2bn</td><td>More than double the next-largest deficit; 58% of imports are HS84/85 industrial inputs feeding India's own assembly lines — unmoved by six years of PLI</td></tr>
<tr><td class="k">Russia</td><td class="n">35.8–35.9% of crude</td><td>From ~2.5% pre-2022 with no scheme behind it — market-driven; the ₹12,980cr Bharat Maritime Insurance Pool (Apr 2026) now hardens this lane against insurance exclusion</td></tr>
<tr><td class="k">UAE / Switzerland</td><td class="n">−$26.5bn / −$23.1bn</td><td>Structural gold/gems re-export flows — a deliberately open door, not a substitution gap</td></tr>
<tr><td class="k">USA</td><td class="n">Surplus; #1 destination</td><td>Top-8 destination in 11 of 12 growth export chapters ($63.9bn) — a bigger concentration than China's grip on imports; the flat-10% tariff replacement expires 24-Jul-2026</td></tr>
</table>
<div class="src">Commerce TIA/TRADESTAT country×commodity validation; details in the country-deficit bulletin.</div>
</section>

<section id="s3">
<h1 class="sec">3 · Sector performance &amp; verdicts (FY2025-26)</h1>
<p class="lead">All ten sector verdicts re-run on FY2025-26 FDI data: <b>1 green / 6 amber / 3 red</b>.
Both prior greens reversed hard — a reminder that verdicts decay and must be re-measured quarterly.</p>
<table>
<tr><th>Sector</th><th>Verdict</th><th>Carrying evidence</th></tr>
<tr><td class="k">Pharmaceuticals</td><td>GREEN</td><td>FDI +114% after real disbursal (₹5,433cr, 36% of outlay); investment 237% of commitment; Penicillin-G restored</td></tr>
<tr><td class="k">Electronics</td><td>AMBER ↓</td><td>FDI −43.5% in FY26 after the FY25 green; exports still #1; LSEM tenure closed → MPMS successor</td></tr>
<tr><td class="k">Medical devices</td><td>AMBER ↓</td><td>FDI −40.4%; disbursal thin (₹157.15cr to 7 applicants)</td></tr>
<tr><td class="k">Auto / EV / steel / white goods / textiles / food</td><td>AMBER</td><td>Mixed delivery; steel carries a 24% project-withdrawal rate; textiles payouts began at ₹54.5cr to two unnamed firms</td></tr>
<tr><td class="k">Inorganic chemicals · plastics · (textiles-apparel)</td><td>RED</td><td>No scheme coverage on the two largest uncovered import heads; apparel sits in PLI Textiles' MMF blind spot</td></tr>
</table>
<div class="src">FY26 verdict re-run bulletin (criteria stated per verdict); grades from the PLI report card.</div>
</section>

<section id="s4">
<h1 class="sec">4 · Special theme: the migration away from production-linked design</h1>
<p class="lead">This quarter's theme chapter, from the programme's 83,734-release PIB register: every
incentive launch in the Cabinet record 2021–2026 (93 classified launches), read as one series.</p>
<table>
<tr><th>Year</th><th>Era</th><th>New PLI-type schemes</th><th>Prod-linked share of new ₹</th></tr>
<tr><td class="k">2021</td><td>The PLI big bang — plus quiet mission money</td><td class="n">11</td><td class="n">11.2%</td></tr>
<tr><td class="k">2022</td><td>Rescue &amp; consolidation (BSNL ₹1.64L cr, ECLGS)</td><td class="n">1</td><td class="n">6.2%</td></tr>
<tr><td class="k">2023</td><td>Missions &amp; VGF arrive (Green Hydrogen, BESS)</td><td class="n">1</td><td class="n">13.8%</td></tr>
<tr><td class="k">2024</td><td>The capex-subsidy year</td><td class="n">0</td><td class="n">0%</td></tr>
<tr><td class="k">2025</td><td>Funds &amp; mega-packages; payouts migrate to jobs</td><td class="n">2 (hybrids)</td><td class="n">7.7%</td></tr>
<tr><td class="k">2026 YTD</td><td>De-risking inputs</td><td class="n">0</td><td class="n">0%</td></tr>
</table>
<p>Three readings: <b>(1)</b> production-linked was never where the money was — the 11 PLI launches of 2021
(₹1.17L cr) were 11.2% of that year's ₹10.5L cr of new commitments; infra missions carried 6× the outlay.
<b>(2)</b> The "linked" payout base migrated output → design → <b>employment</b> (ELI 2025, ₹99,446cr —
larger than any single PLI). <b>(3)</b> 2026's ~₹1.9L cr wave (Urban Challenge Fund ₹1L cr, gasification VGF
₹37,500cr, BHAVYA parks ₹33,660cr, BMI pool, ECLGS 5.0, NIPU-2026) pays for land, credit, risk and viability
gaps — instruments that spend when investment happens, not when output does. After ~15% PLI disbursal in
five years, that reads as revealed preference.</p>
<div class="warn"><b>Investor implication:</b> underwrite output-linked incentives as upside, not base case
(grade-A exceptions: Pharma, Electronics); capex/VGF/credit instruments pay with the build. Windows live now:
UNNATI (→30-Sep-2026), Gasification 2026 Round-1, DoP API-CF/SMDI, ECMS (extended), ALMM. The full 8-step
investor route (NSWS → KYA → portals → gates) is published as the investor-workflow bulletin.</div>
<div class="src">Five-year evolution bulletin (all 93 launches PRID-cited); beyond-PLI 2026 bulletin.</div>
</section>

<section id="s4b">
<h1 class="sec">4b · Matured schemes: the returns already in</h1>
<p class="lead">The counterpart to the theme chapter: schemes launched 2014–2020 whose incentive → investment →
outcome loop has <b>already closed</b> — the cohort that shows which instrument designs actually produce
trade and forex results in India. (The PIB register is being extended to 2017–2020 for a full launch-to-outcome
trace; the modern portal's day-wise record begins in 2017, so 2014–16 launches are traced through later
releases — the method that built the ethanol case.)</p>
<table>
<tr><th>Scheme (launch era)</th><th>Instrument design</th><th>Outcome now on record</th><th>Trade/forex link</th></tr>
<tr><td class="k">Ethanol Blended Petrol (2014 pricing era)</td><td>Administered pricing + guaranteed OMC offtake + distillery subvention + GST 5%</td>
    <td>Blending 1.53% → 20% "five years ahead of schedule" (Factsheet 150699); &gt;₹1.66L cr to farmers</td>
    <td class="n">₹1.97L cr forex saved; ~316 lakh MT crude substituted (PRID 2283118)</td></tr>
<tr><td class="k">M-SIPS → PLI-LSEM (2012/2020)</td><td>Capex subsidy era → production-linked era</td>
    <td>Smartphone base built: LSEM completed its tenure with exports at 121% of target; Foxconn/Dixon/Samsung producing</td>
    <td class="n">Smartphones = India's #1 export item (CY2025); electronics exports $54bn</td></tr>
<tr><td class="k">Solar manufacturing push (NSM era → PLI T1/T2)</td><td>Market-access (ALMM) + tender-linked PLI post-commissioning</td>
    <td>100 GW of ALMM-listed module capacity crossed (Aug 2025); ~30 GW commissioned under PLI design</td>
    <td class="n">Import-dependence in modules falling; List-II cell enforcement (to 31-Dec-2026) extends it upstream</td></tr>
<tr><td class="k">UDAN (2016)</td><td>Route-level VGF to airlines</td>
    <td>Regional network built enough to justify a 10-year, ₹28,840cr Modified UDAN successor (FY27–36)</td>
    <td class="n">Demand-side; services/tourism earnings channel</td></tr>
<tr><td class="k">FAME-I/II (2015/2019) → EMPS → PM E-DRIVE</td><td>Demand incentives via OEMs</td>
    <td>An EV market real enough that successors are extended segment-wise (e-2W to Jul-2026, e-3W to Mar-2028)</td>
    <td class="n">Petroleum-import avoidance channel; battery imports remain the offset (ACC gap)</td></tr>
<tr><td class="k">NIP-2012 urea plants</td><td>Assured-return investment policy</td>
    <td>Plants built (Matix, Ramagundam et al.) — the precedent NIPU-2026 explicitly extends with better terms (RoE band 12–16%)</td>
    <td class="n">Urea import substitution; fertiliser imports (+118.9%) are the gap NIPU now targets</td></tr>
<tr><td class="k">SATAT (2018)</td><td>Assured-price CBG offtake by OMCs</td>
    <td>Ecosystem instruments in place (PSL status, FOM recognition, LTOAs); scale still modest — the honest laggard in the cohort</td>
    <td class="n">Gas-import substitution channel, largely unrealised yet</td></tr>
</table>
<p><b>What the matured cohort teaches:</b> the completed successes share a demand-side guarantee (offtake,
administered price, assured return, market access) rather than an output payout — ethanol, urea-NIP, ALMM and
M-SIPS-era electronics all closed their loops on <b>guaranteed-buyer or guaranteed-terms designs</b>. That is
precisely the design family 2025–26's new instruments (NIPU, gasification VGF, BMI pool, offtake mechanisms)
return to — the five-year migration of §4 is, in hindsight, a reversion to what had already worked.</p>
<div class="src">Session-verified figures (PRIDs as cited; ministry portals for LSEM/ALMM/E-DRIVE). Full launch-to-outcome cohort bulletin in progress on the extended 2017-2026 register.</div>
</section>

<section id="s5">
<h1 class="sec">5 · Trade &amp; investment policy developments</h1>
<h2>Launches and successions this cycle</h2>
<ul>
<li><b>15-Jul-2026 Cabinet:</b> MPMS (PLI-LSEM successor: 2.25–5% on mobile sales FY27–31, ₹62,500cr),
<b>Semicon 2.0</b> (₹1,27,500cr, six pillars incl. a new equipment/materials lane), and <b>NIPU-2026</b>
(urea investment policy, RoE band 12–16%).</li>
<li><b>Scheme endings observed:</b> LSEM completed its tenure (31-Mar-2026, first PLI to do so); PLI Drones
expired FY24 with no successor; IFLDP's ₹1,700cr window closed (NSWS carried the only formal notice);
Interest Equalisation lapsed Dec-2024 → NIRYAT PROTSAHAN; Food Processing sunsets FY27 with no successor announced.</li>
<li><b>Displayed correction:</b> PM E-DRIVE was <b>extended</b> segment-wise (e-2W →31-Jul-2026, e-rickshaws/carts
→31-Mar-2028; L5 closed 26-Dec-2025) — the live portal superseded the announced two-year window.</li>
<li><b>FDI rules:</b> Press Note 3 amended (10-Mar-2026) with defined Beneficial-Owner criteria for
land-border-country screening; Semicon 2.0 admits OCI-owned companies in design.</li>
<li><b>Attrition disclosures:</b> 14 of 58 specialty-steel Round-1 projects withdrew; White Goods slid
85 → 80 beneficiaries unexplained; an ACC awardee (20 GWh) vanished from DHI documents; 10 GWh re-tendered.</li>
</ul>
<h2>Verification notes (why this register, not ministry pages)</h2>
<p>The 20-Jul-2026 sweep of 16 ministry websites found the estate partly headless (MeitY/DoT/DPIIT content
lives in public wp-json CMS APIs behind JS shells) and partly dark (fert.nic.in and texmin.nic.in DNS-dead;
mines.gov.in unreachable; msme.gov.in's scheme list unrenderable) — and six flagship scheme pages provably
stale. Cabinet releases and live application portals are the reliable surfaces; this report cites PRIDs
throughout.</p>
<div class="src">Scheme registry + ministry incentive catalog (site-verified); PIB index (--update quarterly).</div>
</section>

<section id="s6">
<h1 class="sec">6 · Investment lifecycle monitor</h1>
<p class="lead">The programme measures the investment pipeline at seven gates: announcement → IEM Part A
(intent) → land + environmental clearance → IEM Part B (production) → incentive disbursal → FDI equity →
trade outcome.</p>
<table>
<tr><th>Gate</th><th>This cycle's reading</th><th>Signal</th></tr>
<tr><td class="k">IEM implementation ratio</td><td class="n">82% (2024) → 109.9% (2025)</td><td>Implemented investment exceeded same-year intent for the first time — the 2021-22 intent surge matured into plants</td></tr>
<tr><td class="k">Environmental clearances</td><td class="n">198 → 734 → 1,102/yr</td><td>Grant flow accelerating; EC grants correlate <b>0.96</b> with state implementation value — the best forward indicator found</td></tr>
<tr><td class="k">State leadership</td><td class="n">Gujarat 33.8%</td><td>Full-chain leader (intent, clearance, production; 178% conversion); top-3 states hold 63.3%; Odisha is #2 implementer with 0.14% of FDI (domestic steel capital)</td></tr>
<tr><td class="k">PLI disbursal</td><td class="n">₹28,748cr ≈ 15%</td><td>Concentrated in two sectors; ACC at zero; FY25 flow ₹10,114cr and accelerating in electronics/auto</td></tr>
<tr><td class="k">FDI equity</td><td class="n">$58.85bn (+18%)</td><td>State-wise attribution remains registered-office-based — a documented data defect, not a measurement</td></tr>
</table>
<div class="src">State IEM bulletin; PARIVESH EC pipeline (open API, 113,804 proposals); PLI report card; DPIIT quarterly newsletter.</div>
</section>

<section id="s7">
<h1 class="sec">7 · Statistical annex</h1>
<h2>A1 · PLI disbursal report card</h2>
<table>
<tr><th>Scheme</th><th>Outlay ₹cr</th><th>Disbursed ₹cr</th><th>Grade</th></tr>
<tr><td>Electronics (LSEM + IT-HW)</td><td class="n">11,324*</td><td class="n">15,554</td><td>A−</td></tr>
<tr><td>Pharmaceuticals</td><td class="n">15,000</td><td class="n">5,433</td><td>A</td></tr>
<tr><td>Food Processing</td><td class="n">10,900</td><td class="n">1,084</td><td>B</td></tr>
<tr><td>Telecom</td><td class="n">12,195</td><td class="n">~1,175</td><td>B</td></tr>
<tr><td>Bulk Drugs / Medical Devices</td><td class="n">6,940 / 3,420</td><td class="n">~54.8 / 157.2</td><td>B / B</td></tr>
<tr><td>White Goods / Solar</td><td class="n">6,238 / 24,000</td><td class="n">281.4 / 0 (by design)</td><td>B− / B−</td></tr>
<tr><td>Drones (expired)</td><td class="n">120</td><td class="n">30</td><td>C+</td></tr>
<tr><td>Auto &amp; components</td><td class="n">25,938</td><td class="n">2,377.6</td><td>D+</td></tr>
<tr><td>Specialty Steel / Textiles</td><td class="n">6,322 / 10,683</td><td class="n">48 / 54.5</td><td>D / D</td></tr>
<tr><td>ACC Battery</td><td class="n">18,100</td><td class="n">0</td><td>F</td></tr>
</table>
<div class="src">*combined disbursal spans both electronics schemes. Sources per row in the report-card bulletin (PRIDs + Parliament answers).</div>
<h2>A2 · Scheme window calendar</h2>
<table>
<tr><th>Date</th><th>Event</th></tr>
<tr><td class="n">24-Jul-2026</td><td>US flat-10% tariff replacement expires</td></tr>
<tr><td class="n">31-Jul-2026</td><td>PM E-DRIVE e-2W window ends (as extended)</td></tr>
<tr><td class="n">30-Sep-2026</td><td>UNNATI registration closes</td></tr>
<tr><td class="n">31-Oct-2026</td><td>Beyond-E20 ethanol decision due</td></tr>
<tr><td class="n">31-Dec-2026</td><td>ALMM List-II (solar cells) transition window ends</td></tr>
<tr><td class="n">FY2026-27</td><td>PLI Food Processing final incentive year; no successor announced</td></tr>
</table>
<h2>A3 · Where the deep data lives</h2>
<p>Interactive bulletins (24), sourced data JSONs, the PIB register (83,734 releases, 2020–2026, SQL-queryable),
the scheme registry, the site-verified ministry catalog, and the 8-step investor workflow:
<b>{SITE}</b>. Quarterly refresh follows the repository's blueprint (per-gate change-data-capture; corrections
displayed, never silent).</p>
</section>

</body></html>"""


def main():
    import weasyprint
    doc = weasyprint.HTML(string=html(), base_url=str(ROOT)).render()
    doc.write_pdf(str(OUT))
    print(f"{OUT.name}: {len(doc.pages)} pages")


if __name__ == "__main__":
    main()
