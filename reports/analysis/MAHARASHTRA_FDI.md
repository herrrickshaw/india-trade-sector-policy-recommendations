# Maharashtra's FDI: stock-market money, or money in the ground?

*2026-07-21 — every figure below is from a named primary source with a URL in `data/maharashtra_fdi_composition_2026-07-21.json`. Two figures were deliberately NOT asserted because they could not be retrieved (see Limits).*

## The question contains a trap, and it is worth naming first

**No portfolio money is in the FDI number at all — by definition, not by estimate.** RBI's Master Direction on Foreign Investment draws a bright line at **10% of post-issue paid-up equity on a fully diluted basis**: at or above it, an inflow is FDI; below it, the same rupee is Foreign Portfolio Investment and sits in a different account. DPIIT's own factsheet proves the separation on its face — it carries FPI as a distinct column, *'Investment by FPI's Foreign Portfolio investor Fund (net)'*, sitting **outside** the Total FDI Inflow column.

So sub-10% buying of listed Indian shares never enters Maharashtra's **₹8,59,196 crore / USD 107,094 mn** (Oct 2019–Mar 2026, **31.35%** of all India, DPIIT Annexure-C). The literal answer to *how much of Maharashtra's FDI is stock-market money* is **zero, structurally**.

The two channels have also been moving in opposite directions. FDI into Maharashtra kept rising while **net FPI equity flows turned sharply negative** — +₹2,08,212 cr in FY2023-24, then **−₹1,27,041 cr** in FY2024-25 and **−₹1,80,832 cr** in FY2025-26 (NSDL). Foreign portfolio money has been *leaving* Indian equities over precisely the period Maharashtra's FDI grew.

## But the instinct behind the question is right — the distortion is geographic, not portfolio

**DPIIT attributes an inflow to the state of the Indian company that receives the remittance, not the site of the project it funds.** DPIIT's own phrasing for the Maharashtra deal list is *'Remittance-wise – through Indian companies'*.

**A negative finding worth flagging:** DPIIT publishes **no explicit caveat** anywhere stating that state attribution follows the registered/reporting office rather than the project location. It is left entirely implicit in the phrase *'reported at Maharashtra state'*. That is arguably the single most consequential undocumented assumption in the dataset.

DPIIT's own top-25 Maharashtra list shows the artefact plainly:

| # | Recipient | Activity | Investor | Amount |
|---|---|---|---|---|
| 1 | Reliance Retail Ventures | Storage & warehousing | Saudi PIF | ₹9,555 cr |
| 2 | Reliance Retail Ventures | Storage & warehousing | SLP Rainbow (Singapore) | ₹8,813 cr |
| 3 | **Ambuja Cements** | Clinker & cement manufacture | Harmonia (Mauritius) | ₹8,341 cr |
| 4 | Reliance Retail Ventures | Storage & warehousing | Qatar Holding | ₹8,278 cr |
| 5 | **HDFC Credila** | Other credit granting | Kopvoorn BV (Netherlands) | ₹7,642 cr |

Three of the top four are stakes in a **nationwide** retail and warehousing group, booked 100% to Maharashtra because RRVL is Mumbai-registered — the warehouses they finance are in every state. #3 is a cement company whose plants are mostly in Himachal, Gujarat, Rajasthan and Chhattisgarh. #5 is a pure financial transaction with no physical project anywhere.

## A hypothesis I had, which the data killed

I expected a large *'Region not indicated'* bucket to be inflating things. **It was true, and is now obsolete.** In the legacy RBI regional-office series (Apr–Jun 2019) that line was **15.96%** of all FDI equity inflow — *larger than the entire Mumbai office at 9.60%*. In the current state-wise series 'State Not Indicated' is **0.01%**, and a cross-check of Annexure-C's total against DPIIT's annual series (~USD 341.6bn vs ~342.7bn) shows the state table now captures essentially 100% of national inflow.

**So the problem is not missing data. It is complete data assigned to the wrong geography.** (Relatedly: the old Mumbai office bundled Dadra & Nagar Haveli and Daman & Diu with Maharashtra; in the current series they are a separate line, so that particular contamination is gone.)

## What Maharashtra's FDI is actually in

DPIIT Table 6.3(i), *FDI Synopsis on State – Maharashtra* (Oct 2019 – Dec 2024):

| Sector | Share |
|---|---|
| Services (financial, banking, insurance, outsourcing, R&D) | 23.26% |
| Construction (infrastructure) | 16.13% |
| Computer software & hardware | 13.77% |
| Trading | 5.47% |
| **Automobile industry** — the only unambiguous plant-and-machinery line | **4.33%** |

**Services + software + trading = 42.5%, against 4.33% for automobiles.** DPIIT publishes only the top five sectors, so **37% of the state's FDI is sectorally unpublished** — the true non-plant share is higher than 42.5%, not lower.

## The finding that actually answers the question

**DPIIT's FDI equity inflow explicitly includes the purchase of existing shares.** The factsheet says so verbatim, identically, under the country, sector *and* state tables:

> *'%age worked out in USD terms & FDI inflow received through Government Route + Automatic Route + acquisition of existing shares only.'*

Buying shares from a selling shareholder transfers ownership and creates **zero new capital formation** — no plant, no job, no machine. DPIIT has booked even a **USD 3.1bn pure share swap** as equity inflow.

And yet **DPIIT publishes no greenfield-versus-brownfield split at all** — not nationally, not by state. It is therefore *impossible from official Indian data* to state what fraction of Maharashtra's FDI built anything. That is the real answer, and it is a gap in the source, not in the analysis.

## The independent cross-check: what the ground says

Where official data is silent, implementation data is not. Comparing DPIIT FDI against **IEM Part B** (industrial investment actually *implemented*):

| State | Implemented (5yr) | Share | FDI FY26 | Share | FDI intensity |
|---|---|---|---|---|---|
| Maharashtra | ₹237,988 cr | 12.7% | $18,418m | 41.0% | **3.2×** |
| Karnataka | ₹42,463 cr | 2.3% | $12,939m | 28.8% | **12.7×** |
| Gujarat | ₹660,254 cr | 35.3% | $5,713m | 12.7% | **0.4×** |
| Tamil Nadu | ₹44,627 cr | 2.4% | $4,724m | 10.5% | **4.4×** |
| Telangana | ₹25,134 cr | 1.3% | $2,253m | 5.0% | **3.7×** |
| Andhra Pradesh | ₹140,445 cr | 7.5% | $609m | 1.4% | **0.2×** |

**Maharashtra takes 41% of tracked FDI but shows 13% of implemented industrial investment** — 3.2× intensity — and converts only **34.9%** of its own stated intent into implementation, the weakest of the top four states.

Gujarat is the mirror image: **35% of implemented industrial investment on 13% of the FDI**. Odisha is the extreme — 18% of implementation on **0.2%** of FDI, an industrial economy essentially invisible to anyone reading FDI tables. Karnataka's 12.7× is the cleanest proof that this is a registered-office and services effect: Bengaluru's software FDI is real money that is not plant and machinery.

## Bottom line

1. **Stock-market money: none.** FPI is definitionally excluded, and has been flowing *out* of Indian equities while Maharashtra's FDI rose.

2. **Money in the ground: far less than the 41% headline.** At least 42.5% of Maharashtra's FDI is services, software and trading against 4.33% automobiles; the inflow includes pure share purchases that build nothing; and three of the top four deals are nationwide businesses booked to Mumbai on a registered-office technicality.

3. **The honest number does not exist.** No official source splits greenfield from acquisition, so the share cannot be computed — only bounded. The IEM cross-check is the best available proxy, and it puts Maharashtra's real industrial weight at roughly **a third** of what its FDI share implies.

## Limits

- FDI-vs-FPI can only be compared **nationally**; no source attributes FPI to states (verified against SEBI's AUC page).
- RBI's USD FPI series does not reconcile with NSDL's rupee series — one is all-instrument, the other equity-only. FY2024-25 shows **+USD 3,283mn against −₹1,27,041 cr**; the sign flip is entirely debt.
- Two figures were **not asserted**: current FPI assets under custody (NSDL served only archived 2014/2015 months; the live report needs an ASP.NET POST) and UNCTAD's India greenfield value (unctad.org returned 403). Press numbers for both appeared in search and were excluded as unverified.
- IEM Part B excludes services and sub-threshold projects, so it under-measures exactly the sectors Maharashtra leads in. It is a proxy for *industrial* weight, not total economic activity.
