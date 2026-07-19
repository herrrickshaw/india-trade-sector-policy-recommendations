#!/usr/bin/env python3
"""
build_compendium.py — assemble every bulletin into one professionally
paginated PDF via WeasyPrint (run with Homebrew python3; system Python's
SIP strips the DYLD path pango needs).

Pipeline (the WeasyPrint approach: HTML/CSS in, print-grade PDF out):
  1. For each chart bulletin: headless Chrome --dump-dom executes the page's
     JavaScript and returns the fully-rendered DOM (WeasyPrint runs no JS).
  2. Post-process each DOM: force data-theme="light", strip <script>, inject
     print/print.css (A4, @page running headers from each page's h1,
     break-into-page rules, table de-min-widthing) plus a per-section
     page-counter offset so numbering runs continuously across sections.
  3. Two passes: pass 1 renders every section to count pages; pass 2
     re-renders with the correct counter offsets and the literal grand total.
  4. Cover + TOC (page numbers computed, not guessed) rendered the same way.
  5. pypdf merges everything — WeasyPrint's auto-bookmarks (from h1/h2)
     survive the merge — and appends the landscape FDI deck as the appendix.

Usage:  /opt/homebrew/bin/python3 scripts/build_compendium.py
Output: reports/published/India_Trade_Compendium_2026-07-19.pdf
"""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TMP = Path("/tmp/build_top10/compendium_v2"); TMP.mkdir(parents=True, exist_ok=True)
PRINT_CSS = (ROOT / "print/print.css").read_text()

SECTIONS = [
    ("Abstract: Why Import Substitution — The Story", "abstract_forex_import_substitution"),
    ("Master Report — Findings, Grades & Corrections", None),  # generated from JSON
    ("Project Workflow & Data-Sourcing Schema", "project_workflow_schema"),
    ("Quarterly Refresh Blueprint (TOGAF × Data Stack)", "quarterly_refresh_blueprint"),
    ("Sector & Policy Recommendations (Capstone)", "sector_and_policy_recommendations"),
    ("Import Dependency vs Policy Coverage", "import_dependency_policy_gap_analysis"),
    ("Country-by-Country Trade Deficits", "country_trade_deficit_and_policy_history"),
    ("Import Partners by Growth Sector & PLI", "sector_country_priority_and_pli_coverage"),
    ("Export Destinations by Growth Sector & PLI", "export_destination_priority_and_pli_coverage"),
    ("State & Central Incentives, Emergent Hubs", "state_central_incentives_and_emergent_hubs"),
    ("Top 10 Sectors: Country Strategies & Tariffs", "top10_sector_country_strategies"),
    ("Did the Money Show Up? FDI vs PLI Launches", "fdi_vs_pli_launch_correlation"),
    ("Master Sector Scorecard", "sector_master_scorecard"),
    ("Domestic Capital vs FDI: Rates & Risk", "domestic_vs_fdi_capital_case"),
    ("Policy & Investment Insight Dashboard", "policy_investment_dashboard"),
    ("FY2025-26 Verdict Re-run & Trade Impact", "fy26_verdict_rerun_powerbi"),
    ("PLI Report Card: Disbursal, IEM & Companies", "pli_report_card"),
    ("State-wise Investment Implementation (IEM B)", "state_iem_implementation"),
    ("PARIVESH EC Pipeline & the EC-IEM Correlation", "parivesh_ec_pipeline"),
]
DECK = ROOT / "fdi_pitch/India_Trade_FDI_Pitch_Deck.pdf"
OUT = ROOT / "reports/published/India_Trade_Compendium_2026-07-19.pdf"


def dump_dom(html_path: Path) -> str:
    r = subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-sandbox",
                        "--virtual-time-budget=8000", "--dump-dom", f"file://{html_path}"],
                       capture_output=True, text=True, timeout=120)
    return r.stdout


def master_html() -> str:
    sys.path.insert(0, str(ROOT / "scripts"))
    from report_synthesizer import render_fallback_html
    data = json.loads((ROOT / "data/master_report_2026-07-19.json").read_text())
    return render_fallback_html(data, "Master Report — Findings, Grades & Corrections")


def prepare(html: str, page_start: int, total: str) -> str:
    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S)
    html = re.sub(r"(<html\b[^>]*?)\sdata-theme=\"[^\"]*\"", r"\1", html)
    html = re.sub(r"<html\b([^>]*)>", r'<html\1 data-theme="light">', html, count=1)
    inject = (f"<style>{PRINT_CSS}\nhtml{{counter-reset: page {page_start - 1}}}</style>"
              f"<span id='pgtotal'>{total}</span>")
    if "</head>" in html:
        html = html.replace("</head>", inject + "</head>", 1)
    else:
        html = inject + html
    return html


def render(html: str, out_pdf: Path):
    import weasyprint
    weasyprint.HTML(string=html, base_url=str(ROOT / "charts") + "/").write_pdf(str(out_pdf))


def n_pages(pdf: Path) -> int:
    from pypdf import PdfReader
    return len(PdfReader(str(pdf)).pages)


def cover_toc(entries, total: int) -> str:
    rows = "".join(f"<tr><td>{t}</td><td class='p'>{s}</td></tr>" for t, s in entries)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 0; }}
@page content {{ size: A4; margin: 16mm 13mm 15mm 13mm; }}
body {{ margin:0; font-family: Helvetica, Arial, sans-serif; color:#14180f; }}
.cover {{ page: cover; height: 297mm; background:#0e1c2e; color:#f5f1e7; display:flex;
  flex-direction:column; justify-content:center; padding:0 22mm; box-sizing:border-box; page-break-after:always; }}
.cover .bar {{ height:6px; width:60mm; background:linear-gradient(90deg,#d9932f,#1f6f5c); margin-bottom:10mm; }}
.cover .eyebrow {{ color:#d9932f; font-size:9pt; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; }}
.cover h1 {{ font-family: Georgia, serif; font-size:26pt; line-height:1.18; margin:6mm 0; }}
.cover .dek {{ font-size:9pt; line-height:1.7; color:#c7cdd3; max-width:150mm; }}
.cover .meta {{ margin-top:12mm; font-size:7.5pt; color:#93a0ad; line-height:1.9; }}
.toc {{ page: content; padding: 10mm 8mm; }}
.toc h2 {{ font-family: Georgia, serif; font-size:16pt; border-bottom:2pt solid #14180f; padding-bottom:3mm; }}
.toc table {{ width:100%; border-collapse:collapse; margin-top:4mm; font-size:8.5pt; }}
.toc td {{ padding:2.2mm 0; border-bottom:0.4pt solid #d8d2c0; }}
.toc td.p {{ text-align:right; color:#6b7280; width:14mm; font-variant-numeric:tabular-nums; }}
.toc .note {{ margin-top:6mm; font-size:6.5pt; color:#6b7280; line-height:1.7; }}
</style></head><body>
<div class="cover">
  <div class="bar"></div>
  <div class="eyebrow">India Trade — Sector &amp; Policy Recommendations</div>
  <h1>The Complete Compendium:<br>India's Trade, FDI &amp; PLI Program,<br>Measured Gate by Gate</h1>
  <div class="dek">Every bulletin from the research program in one paginated document: the seven-gate
  investment-lifecycle schema; trade position and sector verdicts on FY2025-26 data; the PLI disbursal
  report card with named producing companies; state-wise implementation combining domestic and foreign
  capital; the environmental-clearance pipeline and its 0.96 correlation with implementation; the full
  methodology and corrections ledger. Compiled from primary sources with every judgment stated and every
  caveat visible.</div>
  <div class="meta">Compiled 19 July 2026 · {total} pages + appendix ·
  herrrickshaw/india-trade-sector-policy-recommendations<br>
  Interactive versions: herrrickshaw.github.io/india-trade-sector-policy-recommendations</div>
</div>
<div class="toc">
  <h2>Contents</h2>
  <table>{rows}<tr><td>Appendix: FDI Pitch Deck (23 slides, landscape)</td><td class='p'>{total + 1}</td></tr></table>
  <div class="note">Each section is the print rendering of its live bulletin (JavaScript pre-executed,
  light theme enforced, repaginated for A4 with running headers). Underlying sourced data JSONs live in
  the repository's data/ directory, indexed in the repo manifest. Page numbers are continuous across
  sections; the appendix keeps the deck's own slide numbering.</div>
</div>
</body></html>"""


def main():
    # Pass 1: render each section once to learn its page count
    htmls, counts = [], []
    for title, slug in SECTIONS:
        raw = master_html() if slug is None else dump_dom(ROOT / f"charts/{slug}.html")
        htmls.append(raw)
        tmp = TMP / f"pass1_{len(htmls):02d}.pdf"
        render(prepare(raw, 1, "?"), tmp)
        counts.append(n_pages(tmp))
        print(f"  pass1 {title[:44]:<46} {counts[-1]:>3}p")

    total = sum(counts)
    starts, pg = [], 1
    for c in counts:
        starts.append(pg); pg += c

    # Pass 2: correct offsets + literal total
    finals = []
    for i, ((title, slug), raw) in enumerate(zip(SECTIONS, htmls)):
        out = TMP / f"final_{i:02d}.pdf"
        render(prepare(raw, starts[i], str(total)), out)
        finals.append(out)

    front = TMP / "front.pdf"
    render(cover_toc(list(zip([t for t, _ in SECTIONS], starts)), total), front)

    from pypdf import PdfReader, PdfWriter
    w = PdfWriter()
    w.append(str(front), import_outline=False)
    w.add_outline_item("Cover & Contents", 0)
    page = n_pages(front)
    for (title, _), f in zip(SECTIONS, finals):
        w.append(str(f), import_outline=True)
        w.add_outline_item(title, page)
        page += n_pages(f)
    w.append(str(DECK), import_outline=False)
    w.add_outline_item("Appendix: FDI Pitch Deck", page)
    with open(OUT, "wb") as fh:
        w.write(fh)
    print(f"\n{OUT.name}: {n_pages(OUT)} pages "
          f"({n_pages(front)} front + {total} content + {n_pages(DECK)} deck)")


if __name__ == "__main__":
    main()
