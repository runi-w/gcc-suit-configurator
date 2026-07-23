#!/usr/bin/env python3
"""Restore the missing gorge/notch on the RIGHT lapel of the front renders.

WHY THIS EXISTS. The image generator invented a key light from screen-right and then never drew
the lapel's gorge cut on that side. Measured: the right half of every front render is +20.6 to
+24.4 sRGB levels brighter, and the notch seam is a 535 px connected component on the left
against 203 px of scatter on the right. It is in 10/10 front generations ever made, including
`renders/_superseded/`, so it is inherent to the prompt (`plan/PROMPT_01_hero.txt` asks for
"soft, even, frontal studio light" and was ignored), not a regression from any session.

WHY RETOUCH RATHER THAN REGENERATE. Regenerating the hero is ~75 min of Marigold plus
re-deriving all 14 other renders, and it would not reliably fix anything — the defect appears in
every generation the model produces. The gorge is a ~19x80 canvas px feature (0.06% of the frame)
and the two roll lines are mirror-symmetric to within 3%, so a mirror transfer lands within about
a pixel.

HOW. Not a straight pixel copy: the two sides have genuinely different illumination, so pasting
mirrored pixels would drop a visibly darker patch onto a brighter lapel. Instead transfer only
the STRUCTURE — mirror the left patch, take its high-frequency component, and add that to the
right patch's own low-frequency base. The right side keeps its own lighting and gains the left
side's shape. The patch is feathered and clipped to the garment mask so nothing lands on the
shirt, the skin or the background.

    python3 builder/fix_gorge.py            # writes renders/*.png in place, keeps .orig backups
    python3 builder/fix_gorge.py --dry      # writes a before/after sheet only
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

HM = "/Users/runiwillner/Desktop/GCC_House_Model"
OUT = os.environ.get("OUT", "/tmp")

# The patch is REGISTERED, not placed on a guessed axis. There is no single mirror line that
# works: the jacket laps left over right, so the two gorges are NOT symmetric about the neck (on
# front_2button_notch the lapel midpoint reads 901 against a neck centre of 940 — a 39 px offset,
# and it differs per render). Instead each lapel's INNER EDGE — the boundary between lapel cloth
# and the shirt opening — is found independently on both sides, and the mirrored left patch is
# shifted so its inner edge lands on the right's. That self-corrects for the overlap.
#
# The band stops ABOVE the pocket square (which starts at y~640 on the hero). A first attempt ran
# to y=700 with a 274 px half-width and dragged the left chest's structure across the right's
# pocket welt, leaving scattered dark specks. The gorge itself is ~27x115 px; keep it tight.
BAND_Y0, BAND_Y1 = 462, 612      # native px on the 2499-tall hero, scaled per render
PATCH_W = 165                    # px outboard of the inner edge
PATCH_GAP = 4                    # px kept clear of the inner edge itself
LOW_SIGMA = 9.0     # px. Splits "lighting" (kept from the right) from "structure" (taken from
                    # the mirrored left). Must be well above the seam's own width (2.5-6.7 px)
                    # and well below the lapel's tonal scale.
FEATHER = 22.0      # px, on the patch mask
STRENGTH = 1.0      # 1.0 = full structure transfer


def _mask(img):
    """Garment only: darkish and neutral-to-bluish, the same test make_mask.py opens with."""
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    mx, mn = a.max(-1), a.min(-1)
    V = mx / 255.0
    S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return (V < 0.62) & (S < 0.22) & (a[..., 2] >= a[..., 0] - 26)


def _inner_edges(im, y0, y1, gar):
    """Per row, each lapel's INNER edge — the inner end of the two garment runs that flank the
    shirt opening. Driven by the production garment mask, not a brightness test: a naive
    "bright and neutral" shirt test also matches the studio background and collapses to the whole
    frame width."""
    W = gar.shape[1]
    L, R = [], []
    for y in range(y0, y1):
        row = gar[y]
        d = np.diff(np.concatenate(([0], row.view(np.int8), [0])))
        runs = [(a, b) for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1)
                if b - a > 12]
        if len(runs) < 2:
            continue
        # the gap straddling the frame centre is the shirt opening
        best = None
        for i in range(len(runs) - 1):
            g0, g1 = runs[i][1], runs[i + 1][0]
            if g0 < W / 2 < g1 and (best is None or (g1 - g0) > best[1] - best[0]):
                best = (g0, g1)
        if best:
            L.append(best[0]); R.append(best[1])
    return (float(np.median(L)) if len(L) > 20 else None,
            float(np.median(R)) if len(R) > 20 else None)


def fix(name, p, dry=False):
    src = f"{HM}/renders/{name}.png"
    if os.path.exists(f"{HM}/renders/{name}.orig.png"):
        src_read = f"{HM}/renders/{name}.orig.png"     # always retouch from the pristine original
    else:
        src_read = src
    im = Image.open(src_read).convert("RGB")
    a = np.asarray(im).astype(np.float32)
    H, W, _ = a.shape
    sc = H / 2499.0
    y0, y1 = int(BAND_Y0 * sc), int(BAND_Y1 * sc)
    half, gap = int(PATCH_W * sc), int(PATCH_GAP * sc)

    gar = _mask(im)
    eL, eR = _inner_edges(im, y0, y1, gar)
    if eL is None or eR is None:
        print(f"  {name}: could not register the inner edges, skipped"); return None

    xl1 = int(eL) - gap                     # left source: outboard of the left inner edge
    xl0 = xl1 - half
    xr0 = int(eR) + gap                     # right target: outboard of the right inner edge
    xr1 = xr0 + half
    if xl0 < 0 or xr1 > W:
        print(f"  {name}: window off-frame, skipped"); return None

    left = a[y0:y1, xl0:xl1]
    right = a[y0:y1, xr0:xr1]
    mirrored = left[:, ::-1]                # mirror; its inner edge is now on the LEFT, matching
    w = min(mirrored.shape[1], right.shape[1])
    mirrored, right = mirrored[:, :w], right[:, :w]

    def low(x):
        return np.stack([np.asarray(Image.fromarray(x[..., c].astype(np.uint8))
                                    .filter(ImageFilter.GaussianBlur(LOW_SIGMA)), np.float32)
                         for c in range(3)], -1)

    structure = mirrored - low(mirrored)           # the notch, the collar edge, the seam
    merged = low(right) + STRENGTH * structure     # right's own lighting + left's shape

    # feather the patch, and clip it to garment pixels on BOTH sides so the transfer can never
    # land on shirt, skin or background
    hh, ww = merged.shape[:2]
    fx = np.clip(np.minimum(np.arange(ww), ww - 1 - np.arange(ww)) / FEATHER, 0, 1)[None, :]
    fy = np.clip(np.minimum(np.arange(hh), hh - 1 - np.arange(hh)) / FEATHER, 0, 1)[:, None]
    wgt = (fx * fy)[..., None]
    gm = gar[y0:y1, xr0:xr0 + w]
    gsrc = gar[y0:y1, xl0:xl1][:, ::-1][:, :w]
    wgt = wgt * (gm & gsrc)[..., None]

    out = a.copy()
    out[y0:y1, xr0:xr0 + w] = right * (1 - wgt) + merged * wgt
    out = np.clip(out, 0, 255).astype(np.uint8)

    if not dry:
        bak = f"{HM}/renders/{name}.orig.png"
        if not os.path.exists(bak):
            im.save(bak)
        Image.fromarray(out).save(src)
    return im, Image.fromarray(out), (xl0, xl1, xr0, xr1, y0, y1)


if __name__ == "__main__":
    dry = "--dry" in sys.argv
    pairs = []
    for name in ["front_2button_notch", "front_2button_peak", "front_1button_peak",
                 "front_doublebreasted", "front_3piece_vest"]:
        r = fix(name, None, dry=dry)
        if r is None:
            continue
        before, after, geo = r
        xl0, xl1, xr0, xr1, y0, y1 = geo
        print(f"  {name}: src x{xl0}..{xl1} -> dst x{xr0}..{xr1}, y{y0}..{y1}"
              f"  {'(dry)' if dry else 'WRITTEN'}")
        box = (xl0 - 30, y0 - 25, xr1 + 30, y1 + 25)
        pairs.append((name, before.crop(box), after.crop(box)))

    from PIL import ImageDraw, ImageFont
    def font(s):
        try:
            return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", s)
        except Exception:
            return ImageFont.load_default()
    h = 300
    cols = [im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
            for _, b, a2 in pairs for im in (b, a2)]
    cw = cols[0].width
    sheet = Image.new("RGB", (cw * 2 + 14, (h + 22) * len(pairs)), (17, 17, 19))
    d = ImageDraw.Draw(sheet)
    for i, (name, _, _) in enumerate(pairs):
        y = i * (h + 22) + 22
        d.text((5, y - 18), f"{name}    BEFORE  |  AFTER", font=font(13), fill=(235, 235, 235))
        sheet.paste(cols[2 * i], (0, y)); sheet.paste(cols[2 * i + 1], (cw + 14, y))
    sheet.save(f"{OUT}/gorge_fix.png")
    print(f"wrote {OUT}/gorge_fix.png")
