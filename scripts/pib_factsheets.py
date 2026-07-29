"""
Parse PIB (Press Information Bureau) factsheets into markdown.

PIB publishes topic factsheets at pib.gov.in/AllFactsheet.aspx, each linking a
FactsheetDetails.aspx?Id=N page with body text plus PDF attachments hosted on
static.pib.gov.in. This script indexes the listing, extracts each factsheet's
body, downloads its PDF attachments, and pulls their text with pdfplumber.
Scanned (image-only) PDFs fall back to the shared Unlimited-OCR client in
~/ocr/ when UNLIMITED_OCR_URL is configured (see ~/ocr/serve/README.md);
otherwise they are flagged and skipped.

Usage:
    python3 scripts/pib_factsheets.py                    # index + parse all
    python3 scripts/pib_factsheets.py --id 150759        # one factsheet
    python3 scripts/pib_factsheets.py --no-pdfs          # bodies only
    python3 scripts/pib_factsheets.py --out data/pib_factsheets

Note (see reference_pib_index memory): always hit www.pib.gov.in — the bare
domain 301s and silently degrades requests. GETs only here.
"""
from __future__ import annotations

import argparse
import html
import io
import re
import sys
import time
from pathlib import Path

import requests

BASE = 'https://www.pib.gov.in'
LISTING = f'{BASE}/AllFactsheet.aspx?MenuId=12&reg=3&lang=1'
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}


def _get(url: str) -> str:
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    return r.text


def list_factsheets() -> list[dict]:
    """[{id, title, url}] from the AllFactsheet listing, newest first."""
    page = _get(LISTING)
    seen: dict[str, dict] = {}
    for m in re.finditer(
            r"<a[^>]*FactsheetDetails\.aspx\?Id=(\d+)[^>]*>([^<]{3,200})", page, re.I):
        fid, title = m.group(1), html.unescape(m.group(2)).strip()
        if fid not in seen:
            seen[fid] = {'id': fid, 'title': title,
                         'url': f'{BASE}/FactsheetDetails.aspx?Id={fid}'}
    return sorted(seen.values(), key=lambda d: int(d['id']), reverse=True)


def _strip_html(fragment: str) -> str:
    fragment = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', fragment,
                      flags=re.S | re.I)
    fragment = re.sub(r'<br\s*/?>|</p>|</div>|</li>|</h[1-6]>|</tr>', '\n', fragment,
                      flags=re.I)
    fragment = re.sub(r'<[^>]+>', ' ', fragment)
    fragment = html.unescape(fragment)
    lines = [re.sub(r'[ \t\xa0]+', ' ', ln).strip() for ln in fragment.splitlines()]
    return '\n'.join(ln for ln in lines if ln)


def parse_factsheet(fid: str) -> dict:
    """{id, title, body, pdf_urls} for one FactsheetDetails page."""
    page = _get(f'{BASE}/FactsheetDetails.aspx?Id={fid}')
    title_m = re.search(r'<meta name="og:title" content="([^"]+)"', page) \
        or re.search(r'<h2 class="pageHead[^"]*">\s*([^<]+)', page)
    title = html.unescape(title_m.group(1)).strip() if title_m else fid
    date_m = re.search(r'(\d{1,2} [A-Z]{3} \d{4} \d{1,2}:\d{2})', page)
    # Body = pageHead heading through the feedback link at the end of content.
    start = page.find('<h2 class="pageHead')
    end = page.find('ContentPlaceHolder1_FeedbackLink')
    if start != -1 and end > start:
        body = _strip_html(page[start:page.rfind('<', start, end)])
    else:
        body = _strip_html(page)
    pdfs = sorted(set(re.findall(r'href="(https?://[^"]+\.pdf[^"]*)"', page, re.I)))
    return {'id': fid, 'title': title, 'date': date_m.group(1) if date_m else '',
            'body': body, 'pdf_urls': pdfs}


def pdf_text(pdf_bytes: bytes) -> tuple[str, str]:
    """(text, method) — pdfplumber first, Unlimited-OCR fallback for scans."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text = '\n'.join((p.extract_text() or '') for p in pdf.pages).strip()
        if text:
            return text, 'pdfplumber'
    except Exception:
        pass
    home = str(Path.home())
    if home not in sys.path:
        sys.path.append(home)
    try:
        from ocr.unlimited_ocr import is_configured, ocr_pdf_bytes
        if is_configured():
            return ocr_pdf_bytes(pdf_bytes), 'unlimited-ocr'
    except ImportError:
        pass
    return '', 'none (scanned PDF, UNLIMITED_OCR_URL not configured)'


def write_markdown(fs: dict, out_dir: Path, with_pdfs: bool) -> Path:
    slug = re.sub(r'[^a-z0-9]+', '-', fs['title'].lower()).strip('-')[:60] or fs['id']
    path = out_dir / f"{fs['id']}_{slug}.md"
    parts = [f"# {fs['title']}\n",
             f"Source: {BASE}/FactsheetDetails.aspx?Id={fs['id']}"
             + (f"  \nPublished: {fs['date']}" if fs.get('date') else '') + '\n',
             '## Page body\n', fs['body'], '']
    if with_pdfs:
        for url in fs['pdf_urls']:
            name = url.rsplit('/', 1)[-1]
            try:
                r = requests.get(url, headers=UA, timeout=120)
                r.raise_for_status()
                text, method = pdf_text(r.content)
            except Exception as e:
                text, method = '', f'download failed: {e}'
            parts += [f'## Attachment: [{name}]({url})  \n_extracted via {method}_\n',
                      text or '_(no text extracted)_', '']
    path.write_text('\n'.join(parts))
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('--id', help='parse a single factsheet id')
    ap.add_argument('--out', default='data/pib_factsheets', help='output directory')
    ap.add_argument('--no-pdfs', action='store_true', help='skip PDF attachments')
    ap.add_argument('--sleep', type=float, default=1.0, help='delay between requests')
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    targets = [{'id': args.id}] if args.id else list_factsheets()
    index_lines = ['| Id | Title | PDFs | File |', '|---|---|---|---|']
    for t in targets:
        fs = parse_factsheet(t['id'])
        path = write_markdown(fs, out_dir, with_pdfs=not args.no_pdfs)
        index_lines.append(
            f"| {fs['id']} | {fs['title']} | {len(fs['pdf_urls'])} | {path.name} |")
        print(f"{fs['id']}  {fs['title'][:70]}  ({len(fs['pdf_urls'])} PDFs) -> {path}")
        time.sleep(args.sleep)
    (out_dir / 'INDEX.md').write_text(
        '# PIB factsheets\n\n' + '\n'.join(index_lines) + '\n')
    print(f'\nIndex: {out_dir}/INDEX.md ({len(targets)} factsheets)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
