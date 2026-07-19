# Templates

Reusable starting points for the three output formats this repo produces. Each template ships as editable **source** (HTML or JSON) plus pre-built **PPTX/PDF/DOCX** so you can see the result before editing anything.

| Template | Source (edit this) | Pre-built outputs | Build command |
|---|---|---|---|
| Slide deck | [`slide_deck_template.html`](slide_deck_template.html) | [`Slide_Deck_Template.pptx`](Slide_Deck_Template.pptx) · [`Slide_Deck_Template.pdf`](Slide_Deck_Template.pdf) | `./build_deck.sh slide_deck_template.html Slide_Deck_Template` |
| Dashboard | [`dashboard_template.html`](dashboard_template.html) | [`Dashboard_Template.pptx`](Dashboard_Template.pptx) · [`Dashboard_Template.pdf`](Dashboard_Template.pdf) | `./build_deck.sh dashboard_template.html Dashboard_Template --dashboard` |
| Report card | [`report_card_template.html`](report_card_template.html) | [`Report_Card_Template.pptx`](Report_Card_Template.pptx) · [`Report_Card_Template.pdf`](Report_Card_Template.pdf) | `./build_deck.sh report_card_template.html Report_Card_Template --dashboard` |
| Document (Word) | [`document_template.json`](document_template.json) | [`Document_Template.docx`](Document_Template.docx) | `python3 ../scripts/report_synthesizer.py document_template.json --formats docx --out-dir .` |

## How the pipeline works

- **Slide deck**: the HTML is a sequence of fixed 1920×1080 `<div class="slide">` canvases using the same design tokens as the repo's FDI pitch deck (paper/navy/gold/teal/alert palette). `build_deck.sh` screenshots the whole page with headless Chrome, crops one PNG per slide, assembles a 16:9 PPTX with `python-pptx`, and converts to PDF with LibreOffice. **Edit the HTML, never the PPTX** — the PPTX is one full-bleed image per slide, so text changes belong in the source.
- **Dashboard**: the HTML is a Power BI-style responsive page (chrome bar, slicer pills, KPI cards, matrix tile, action items) using the repo's dashboard tokens, light-default with dark-mode support. `--dashboard` mode renders it at 1280px wide, splits the page into 1920×1080-proportioned crops (one PPT slide per screenful), and also prints a paginated PDF.
- **Report card**: the HTML is a graded-assessment bulletin (letter-grade badges A-F with evidence rows and stated criteria, named-entities chips with delivering/committed/gap status, a pattern callout, corrections block) in the repo's bulletin design system. The convention it encodes: grades are judgment, evidence is the checkable part, an F never rests on paraphrase alone, and attribution gaps are stated rather than papered over.
- **Document**: the JSON follows the loose shape every bulletin in this repo uses (`purpose` / `retrieved` / `method` at top, then any sections — dicts become headings, lists-of-dicts become tables, lists of strings become bullets). `scripts/report_synthesizer.py` walks it schema-agnostically, so add or rename sections freely.

## Requirements

Headless Chrome/Chromium, LibreOffice (`soffice`) for PPTX→PDF, Python with `python-pptx`, `python-docx`, `Pillow`, `pypdf` (`pip install -r ../scripts/requirements.txt Pillow`).
