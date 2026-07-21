#!/usr/bin/env python3
"""Normalise a generated render to the house standard: sweep colour, framing, watermark.

Rationale: the generator reliably produces the MAN and the GARMENT, and reliably ignores
instructions about background colour and framing when a reference image is attached — it
weights the reference over the text. Both of those faults are deterministic and computable,
so they are corrected here rather than by burning generations on prompt-fighting.

    1. SWEEP  -> keyed off the background (connected to the frame edge), mapped multiplicatively
                 to neutral 246,246,246 so the floor shadow keeps its gradient.
    2. FRAME  -> canvas padded/cropped so the figure lands at exactly FIGURE_FRAC of frame
                 height, centred. Scale is preserved: only the canvas changes, never the man.
    3. MARK   -> the generator's sparkle watermark, if present, healed with sweep colour.

    python3 normalize_render.py <in.png> [out.png]
"""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

TARGET_BG    = (246, 246, 246)
FIGURE_FRAC  = 0.898       # matches the approved house reference
ASPECT       = 3 / 4
FIG_THRESH   = 150         # firm: excludes the soft floor shadow


def _bg_mask(a):
    """near-white and reachable from the frame edge (so enclosed white — shirt — is excluded)"""
    mx, mn = a.max(-1), a.min(-1)
    V = mx / 255.0
    S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    near = (V > 0.72) & (S < 0.16)
    h, w = near.shape
    sw = 448; sh = max(1, int(h * sw / w))
    small = Image.fromarray((near * 255).astype("uint8")).resize((sw, sh), Image.NEAREST)
    for seed in ((0, 0), (sw - 1, 0), (0, sh - 1), (sw - 1, sh - 1), (sw // 2, 0)):
        if small.getpixel(seed) == 255:
            ImageDraw.floodfill(small, seed, 128, thresh=0)
    reach = Image.fromarray(((np.asarray(small) == 128) * 255).astype("uint8"))
    reach = reach.filter(ImageFilter.MaxFilter(3)).resize((w, h), Image.BILINEAR)
    return near & (np.asarray(reach).astype(np.float32) > 110)


def normalise(img):
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    notes = []

    # ---- 1. sweep -> neutral target, multiplicatively so the contact shadow survives ----
    bg = _bg_mask(a)
    if bg.sum() > 1000:
        cur = np.array([np.percentile(a[..., c][bg], 90) for c in range(3)], np.float32)
        gain = np.array(TARGET_BG, np.float32) / np.maximum(cur, 1)
        soft = np.asarray(Image.fromarray((bg * 255).astype("uint8"))
                          .filter(ImageFilter.GaussianBlur(1.2)), np.float32)[..., None] / 255.0
        a = a * (1 - soft) + np.clip(a * gain, 0, 255) * soft
        notes.append(f"sweep {cur.round(0).astype(int).tolist()} -> {list(TARGET_BG)}")

    # NOTE: no watermark step. API output (imageSize 2K) carries no visible sparkle — only the
    # web-UI download does. An earlier version healed "anomalies in the lower-right sweep" and
    # flattened the floor contact shadow into a hard-edged rectangle. If a web-UI image ever
    # needs de-marking, detect the glyph as pixels BRIGHTER than the sweep, not merely different.
    h, w, _ = a.shape

    # ---- 2. framing: pad/crop the CANVAS so the figure lands at FIGURE_FRAC ----
    fg = (255 - a).sum(-1) > FIG_THRESH
    rows = np.where(fg.sum(1) > 3)[0]
    cols = np.where(fg.sum(0) > 3)[0]
    if len(rows) > 10:
        fh = rows[-1] - rows[0]
        newH = int(round(fh / FIGURE_FRAC))
        newW = int(round(newH * ASPECT))
        cx = (cols[0] + cols[-1]) // 2
        top = int(rows[0] - (newH - fh) / 2)
        left = int(cx - newW / 2)
        canvas = Image.new("RGB", (newW, newH), TARGET_BG)
        canvas.paste(Image.fromarray(np.clip(a, 0, 255).astype("uint8")), (-left, -top))
        notes.append(f"reframed {w}x{h} -> {newW}x{newH} (figure {fh/h:.3f} -> {FIGURE_FRAC})")
        return canvas, notes

    return Image.fromarray(np.clip(a, 0, 255).astype("uint8")), notes


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    src = sys.argv[1]; dst = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1]
    out, notes = normalise(Image.open(src))
    out.save(dst, optimize=True)
    for n in notes:
        print(f"  {n}")
    print(f"  wrote {dst} {out.size}")
