#!/usr/bin/env bash
# build_deck.sh — render an HTML slide deck (or dashboard) to PPTX + PDF.
#
#   ./build_deck.sh slide_deck_template.html Slide_Deck_Template
#   ./build_deck.sh dashboard_template.html Dashboard_Template --dashboard
#
# Deck mode: expects fixed 1920x1080 .slide divs; one PPT slide per div.
# --dashboard mode: renders a responsive page at 1280px wide, slices the full
# page into 1920x1080-proportioned screenfuls (one PPT slide each), and prints
# a paginated PDF directly from the HTML.
#
# Requires: Chrome/Chromium, LibreOffice (soffice), python3 with python-pptx + Pillow.
set -euo pipefail

HTML="$1"; OUT="$2"; MODE="${3:-deck}"
CHROME="${CHROME:-}"
for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" google-chrome google-chrome-stable chromium chromium-browser; do
  if [ -z "$CHROME" ]; then command -v "$c" >/dev/null 2>&1 && CHROME="$c"; [ -x "$c" ] && CHROME="$c"; fi
done
[ -n "$CHROME" ] || { echo "No Chrome/Chromium found (set CHROME=...)"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
HTML_ABS="$(cd "$(dirname "$HTML")" && pwd)/$(basename "$HTML")"

if [ "$MODE" = "--dashboard" ]; then
  WIDTH=1280; SLIDE_W=1280; SLIDE_H=720   # 16:9 screenfuls at dashboard width
  "$CHROME" --headless --disable-gpu --no-sandbox --print-to-pdf="$OUT.pdf" \
    --print-to-pdf-no-header --virtual-time-budget=8000 "file://$HTML_ABS" >/dev/null 2>&1
else
  WIDTH=1920; SLIDE_W=1920; SLIDE_H=1080
fi

N_SLIDES=$(grep -c 'class="slide"' "$HTML" || true)
if [ "$MODE" = "--dashboard" ] || [ "$N_SLIDES" -eq 0 ]; then CANVAS_H=20000; else CANVAS_H=$((N_SLIDES * SLIDE_H)); fi

"$CHROME" --headless --disable-gpu --no-sandbox --window-size="$WIDTH,$CANVAS_H" \
  --screenshot="$TMP/full.png" --hide-scrollbars --force-device-scale-factor=1 \
  --virtual-time-budget=8000 --run-all-compositor-stages-before-draw "file://$HTML_ABS" >/dev/null 2>&1

python3 - "$TMP" "$OUT" "$MODE" "$SLIDE_W" "$SLIDE_H" "$N_SLIDES" <<'PYEOF'
import sys, glob
from PIL import Image
import numpy as np
from pptx import Presentation
from pptx.util import Emu

tmp, out, mode, sw, sh, n = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
im = Image.open(f"{tmp}/full.png")
if mode == "--dashboard" or n == 0:
    a = np.array(im.convert("L"))
    rows = np.where(np.abs(a.astype(int) - int(a[5,5])).max(axis=1) > 12)[0]
    h = int(rows.max()) + 20 if len(rows) else im.height
    n = max(1, -(-h // sh))  # ceil
else:
    h = n * sh
slides = []
for i in range(n):
    top = i * sh
    crop = im.crop((0, top, sw, min(top + sh, im.height)))
    if crop.height < sh:  # pad final screenful
        pad = Image.new("RGB", (sw, sh), crop.getpixel((5,5)))
        pad.paste(crop, (0,0)); crop = pad
    p = f"{tmp}/s{i:02d}.png"; crop.save(p); slides.append(p)

prs = Presentation()
prs.slide_width = Emu(12192000); prs.slide_height = Emu(6858000)
blank = prs.slide_layouts[6]
for p in slides:
    s = prs.slides.add_slide(blank)
    s.shapes.add_picture(p, 0, 0, width=prs.slide_width, height=prs.slide_height)
prs.save(f"{out}.pptx")
print(f"{out}.pptx: {len(slides)} slides")
PYEOF

if [ "$MODE" != "--dashboard" ]; then
  soffice --headless --convert-to pdf "$OUT.pptx" >/dev/null 2>&1 || echo "soffice not found — skipped PDF"
fi
echo "done: $OUT.pptx $([ -f "$OUT.pdf" ] && echo "$OUT.pdf")"
