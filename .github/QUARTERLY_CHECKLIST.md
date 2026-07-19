Auto-opened by `.github/workflows/quarterly-dashboard-refresh.yml`. The PDF snapshot for this quarter has been committed to `reports/published/`; the checklist below is the **data refresh** — work through it, update `data/policy_investment_dashboard_<date>.json` (save as a new dated file) and `charts/policy_investment_dashboard.html`, then re-run the workflow manually to snapshot the updated figures.

## Ministry-by-ministry re-verification

- [ ] **MeitY / ISM** — PLI-LSEM wind-down status (tenure closed 31 Mar 2026), ECMS approval count (verify on a MeitY-controlled page, not PIB), Semicon 2.0 project approvals, latest Standing Committee on Communications & IT report for fund-utilization figures (Semicon India was 23% FY24 / 9% FY25).
- [ ] **Ministry of Steel** — PLI Specialty Steel Round 1.2 first disbursements (began FY2026-27), new Annual Report capacity-utilization table (was 76% and falling), coking-coal import dependence.
- [ ] **Dept. of Heavy Industry** — PLI-Auto disbursement (was ₹1,350.83cr of ₹25,938cr, ~5%); PLI-ACC commissioned GWh (was 1 of 40); the 10 GWh GSSS re-tender outcome; whether the stale `heavyindustries.gov.in/en/pli-acc` page (still says 30 GWh/3 firms) got corrected; any Standing Committee follow-up to the 332nd Report's demanded "beneficiary-wise review within three months."
- [ ] **Dept. of Pharmaceuticals** (`pharma-dept.gov.in`, NOT the dead pharmaceuticals.gov.in) — Bulk Drug Parks second tranches to AP/HP (only Gujarat had one), Medical Device Parks 2-year extension approval, commissioned-project counts.
- [ ] **DPIIT** — White Goods final beneficiary count stability (85 announced, but Round-3's 84 quietly became 80), any first publication of which beneficiaries actually started production, new FDI Press Notes.
- [ ] **Ministry of Textiles** — PLI Textiles actual-investment progress (was ₹6,416cr of ₹28,711cr for Rounds 1-2), any cotton-apparel scope broadening (none as of last check), PM MITRA parks with commercial production (was 1 of 7 — Telangana).
- [ ] **Chemicals / Aviation / Defence** — whether the proposed chemicals PLI got Cabinet approval (was formulation-stage), RRPCL financial close (check MoPNG, not DCPC), GE-HAL F414 formal signature (terms finalized Apr 2026, unsigned at last check).
- [ ] **IEM (DPIIT/NSWS)** — whether monthly IEM Statistics Reports resumed publishing after the Oct 2025 NSWS migration (unconfirmed beyond Aug-2024 data at last check); recompute the Part-B/Part-A flow ratio if new Annual Report appendices exist.
- [ ] **MoSPI PAIMANA** — latest Flash Report aggregates (was 1,941 projects, 15.64% implied cost overrun); whether "delayed" classification was reinstated (dropped after May 2025).

- [ ] **PIB disbursal aggregates** — latest cross-scheme figures (was ₹28,748cr / 836 applications at 31 Dec 2025, PRID 2230621); scheme-wise disbursals (Electronics ₹15,554cr, Auto ₹2,377.56cr, Steel ₹48cr, ACC zero); any newer Parliament-answer PRIDs.
- [ ] **Exim Bank trackers** (eximbankindia.in/useful-economic-data) — 'India's International Trade and Investment' (monthly) for trade/FDI cross-validation; CEAT Industry Tracker for sector credit growth.

## Rate benchmarks (feeds the domestic-vs-FDI capital case too)

- [ ] RBI repo rate + latest MPC decision (was 5.25%, held).
- [ ] 1-yr MCLR for SBI/HDFC/ICICI/PNB/BoB and system-wide median (was ~8.50%).
- [ ] The 9 FDI-source-country policy rates (all were below India's; Japan & Korea were mid-hiking-cycle).

## After updating

- [ ] Save refreshed data as a NEW dated `data/policy_investment_dashboard_YYYY-MM-DD.json` (the workflow picks the latest), update the chart HTML's hardcoded figures to match, add the new file to `data/repo_manifest_*.json`.
- [ ] Re-run the workflow (`workflow_dispatch`) to commit the refreshed PDF snapshot.
