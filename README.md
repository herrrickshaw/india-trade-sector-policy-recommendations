# India Trade: Sector and Policy Recommendations

The prescriptive companion to [`india-trade-data-analysis`](https://github.com/herrrickshaw/india-trade-data-analysis). It takes that repo's import/export chapter rankings, country-concentration findings and TRADESTAT-derived trade data and turns them into explicit, checkable claims about which sectors need PLI-style intervention, which country relationships need active management, and where the current policy response has genuine gaps, cross-checked against NITI Aayog's Trade Watch Quarterly framework. Outputs are static HTML bulletins (`charts/`), sourced data JSON (`data/`), generated PDF/Word/PowerPoint reports (`reports/`), an FDI pitch deck (`fdi_pitch/`) and a few SQLite indexes of public announcements built by the scripts in `scripts/`.

> Status: maintained research repository (data as of July 2026 unless a file says otherwise). Research and education only; not investment, legal or policy advice. Figures come from public Indian government and regulator sources cited inside each bulletin and data JSON.

Both repos were originally one (`mospi-dataset-analysis`); they were split so the descriptive "what does the data show" analysis and the prescriptive "what should be done about it" recommendations could be published and read independently.

**Live site:** [herrrickshaw.github.io/india-trade-sector-policy-recommendations](https://herrrickshaw.github.io/india-trade-sector-policy-recommendations/) (every chart and JSON served by GitHub Pages, no build step).
**New to the repo?** See [How to use this repo with AI](HOW_TO_USE_WITH_AI.md).

## What it does
- Scores import-dependent sectors against existing PLI/incentive coverage and names the gaps (HSN chapters, partner countries, export destinations).
- Grades 14 PLI/incentive schemes on disbursal, IEM record and companies in production, and re-runs the 10-sector verdicts on FY2025-26 FDI.
- Publishes a tiered capstone, "Sector and Policy Recommendations", including two findings validated against NITI Aayog's Trade Watch: a **$20.7bn CBAM export risk** on iron/steel (HS72/73) and a **structural decline in gems and jewellery exports (-29.9%)**.
- Builds a 9-page quarterly PDF in the NITI Trade Watch Quarterly format, plus a master report (9 parts, 12 data tables).
- Turns any bulletin data JSON into PDF, Word and PowerPoint via `scripts/report_synthesizer.py`.
- Maintains SQLite indexes of PIB releases, CCI combination orders and SEBI draft offer documents, and extracts company mentions from PIB titles.

## Quick start
```bash
git clone https://github.com/herrrickshaw/india-trade-sector-policy-recommendations.git
cd india-trade-sector-policy-recommendations
python3 -m venv .venv && source .venv/bin/activate
pip install -r scripts/requirements.txt      # python-docx, python-pptx, pypdf
cd scripts
python3 report_synthesizer.py ../data/fdi_vs_pli_launch_2026-07-19.json \
  --html ../charts/fdi_vs_pli_launch_correlation.html \
  --formats pdf,docx,pptx --out-dir ../reports/
```
The `pdf` format needs a local Chrome/Chromium. Batch mode: `python3 report_synthesizer.py --manifest ../data/repo_manifest_2026-07-19.json --formats pdf,docx,pptx --out-dir ../reports/`.
To read the analysis, open any `charts/*.html` in a browser, or start from [`docs/FINDINGS_AND_BULLETINS.md`](docs/FINDINGS_AND_BULLETINS.md).

## How it works
| Stage | Module / path | Output |
|---|---|---|
| Source data, hand-verified and dated | `data/*_YYYY-MM-DD.json` | one sourced JSON per bulletin |
| Interactive bulletin | `charts/*.html` | one self-contained page per JSON |
| Generic report builder | `scripts/report_synthesizer.py` | PDF (headless Chrome), DOCX, PPTX from any bulletin JSON |
| Quarterly report | `scripts/build_quarterly_report.py` | `reports/published/India_Trade_Watch_Quarterly_*.pdf` in one WeasyPrint pass |
| Retrospective series | `scripts/build_quarterly_series.py` | one document per fiscal year FY2014-15 to FY2026-27 |
| Compendium (archived) | `scripts/build_compendium.py` | 19-section pixel-faithful PDF, superseded by the quarterly report |
| State FDI vs IEM | `scripts/build_state_fdi_iem.py` | FDI-share / implemented-investment intensity ratio per state |
| PIB index and scans | `scripts/pib_index.py`, `pib_company_scan.py`, `pib_idex_birac_body_scan.py`, `pib_factsheets.py` | `data/pib_index.sqlite`, `data/pib_company_mentions.sqlite`, CSV exports, factsheet markdown |
| Regulator indexes | `scripts/cci_index.py`, `scripts/sebi_index.py` | CCI orders and SEBI DRHP filings in SQLite |
| Pitch deck | `fdi_pitch/`, `templates/build_deck.sh` | HTML deck exported to PPTX/PDF |

Design notes: every claim lives in a dated JSON beside its chart, so a refresh is a new dated file rather than an edit; the quarterly report replaced a roughly 3-hour two-pass pipeline with a single generated HTML rendered in about a second; shared constants for the indexers live in `scripts/_common.py`.

## Repository layout
| Path | Purpose |
|---|---|
| `charts/` | Interactive HTML bulletins (29 pages) |
| `data/` | Sourced data JSON/CSV, SQLite indexes, PIB factsheet markdown |
| `reports/` | Generated and published reports (`reports/published/`) |
| `fdi_pitch/` | FDI pitch deck (HTML, PPTX, PDF, slides, social post) |
| `templates/` | Slide deck, dashboard, report card and Word templates plus `build_deck.sh` |
| `scripts/` | Report builders and public-announcement indexers (see above) |
| `tests/` | pytest characterisation and smoke tests (no network) |
| `docs/FINDINGS_AND_BULLETINS.md` | Full bulletin-by-bulletin findings, data-and-charts table and synthesizer notes (previous README, verbatim) |
| `.github/` | Quarterly dashboard refresh workflow, its re-verification checklist and CI |

## Data sources
| Source | What is taken | Access route | Licence / caveat |
|---|---|---|---|
| TRADESTAT / MoSPI (via the companion repo) | HSN-chapter import/export values | companion repo outputs | public government data |
| DPIIT / RBI | FDI equity inflow, IEM Part A/B | published statistics | public; vintages noted per file |
| PIB (pib.gov.in) | releases, factsheets, PRIDs | `pib_index.py`, `pib_factsheets.py` | scraped; fetch politely |
| CCI (cci.gov.in) | combination orders | `cci_index.py` (DataTables endpoint) | scraped; rate limit unconfirmed (1.5 s delay) |
| SEBI (sebi.gov.in) | DRHP/UDRHP/Addendum/Corrigendum listings | `sebi_index.py` (Selenium) | scraped |
| PARIVESH, ministry sites, NITI Aayog Trade Watch | clearance pipeline, scheme status, framework | cited per bulletin | Trade Watch edition used is Q1 FY2024-25 |

## Configuration
No secrets and no environment variables are required. `scripts/cci_index.py` and `scripts/sebi_index.py` write to `data/cci_index.sqlite` and `data/sebi_index.sqlite` (the CCI database is gitignored). `sebi_index.py` additionally needs `selenium` and `beautifulsoup4`; `pib_factsheets.py` can use an optional OCR service (`requirements-ocr.txt`, `UNLIMITED_OCR_URL`).

## Testing
```bash
pip install pytest ruff python-docx python-pptx pypdf
pytest -q
ruff check scripts tests
```
Tests compare script outputs against `tests/golden.json`, captured from the pre-refactor code, and never touch the network.

## Limitations and known issues
- This repo makes recommendations; it does not make policy. Tier and priority labels are its own stated scoring choices, not an official risk assessment or a validated model.
- RCA and TII are explicitly not computed (they need UN Comtrade / WTO global trade-share data).
- The NITI Aayog Trade Watch used for structure is the Q1 FY2024-25 edition (April to June 2024), older than the FY2025-26 claims, so it corroborates framework and direction rather than exact figures.
- Some links in `docs/FINDINGS_AND_BULLETINS.md` point to PDFs that are gitignored (`reports/*.pdf`) and so are absent from a fresh clone; the pitch deck is described as 20 slides in one table and 23 in another (carried over unchanged from the old README).
- The quarterly workflow regenerates a PDF snapshot only; the data itself is refreshed manually via `.github/QUARTERLY_CHECKLIST.md`.
- `scripts/pib_index.py`, `pib_factsheets.py`, `pib_idex_birac_body_scan.py`, `build_*` scripts have not yet had the refactor pass and have no tests.

## Related repositories
- [`india-trade-data-analysis`](https://github.com/herrrickshaw/india-trade-data-analysis): the descriptive half of the split (MoSPI CPI/WPI/GDP, currency and forex reserves, TRADESTAT trade-balance and HSN-chapter analysis, FY2025-26 sample report, Colab notebook).

## Licence
No licence file yet; all rights reserved.
