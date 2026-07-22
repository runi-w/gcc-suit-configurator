#!/usr/bin/env python3
"""Segment the SUIT region of a house-model render -> the drape map's alpha channel.

Why this can be a simple classifier rather than a segmentation model: every base render
shows the SAME navy suit. Fabric is composited at runtime, so the segmenter only ever
sees one garment colour. Tuned and validated against the five existing masks.

    suit = darkish AND neutral-to-bluish, minus background, cleaned up

Validated 2026-07-21 against the original hand-made masks (see --verify).

Usage:
    python3 make_mask.py <render.png> <out_mask.png>
    python3 make_mask.py --verify                      # IoU against all existing masks
"""
import sys
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

HM = "/Users/runiwillner/Desktop/GCC_House_Model"
CUTS = ["front_2button_notch", "front_2button_peak", "front_1button_peak",
        "front_doublebreasted", "front_3piece_vest"]

# tuned on the navy house suit; see --verify for the IoU these produce
V_MAX      = 0.55    # suit is darker than skin, shirt and sweep
BLUE_BIAS  = 8       # B >= R - 8 : neutral-to-bluish, excludes warm skin and brown shoes
BG_V, BG_S = 0.90, 0.06
CLEAN      = 5       # morphological radius (px at 1792 wide)
FEATHER    = 0.8       # smaller: the ramp already supplies the soft edge
# SKIN-BOUNCE RECLAIM (2026-07-21). Trouser pixels next to the hands catch warm reflected
# light, fail the BLUE_BIAS test, and get carved out of the mask in ragged blobs — the
# mid-grey base then shows through the composite as a smudge around each hand (invisible
# on grey cloths, obvious on navy). Measured on the notch render: those spill pixels read
# R-B +12 (p90 +18) where real skin reads +52 and up (p10) — a clean margin. Reclaim
# darkish px warmer than BLUE_BIAS but below WARM_SPILL, only ADJACENT to confident
# garment (dilated interior) and only BELOW SPILL_Y0 (hair reads R-B p10 +13, so the
# collar/head zone must stay strict).
WARM_SPILL = 22
SPILL_Y0   = 0.35
SPILL_R    = 31      # MaxFilter kernel (px): "adjacent to garment" reach
# BRIGHT-HIGHLIGHT RECLAIM (2026-07-22). Grey cloth catching light on the shoulders (mostly
# side/back) is brighter than the V_MAX ceiling, drops out of the mask, and shows as grey
# patches on coloured cloth. Measured on back_2button_notch: those px read V 0.55-0.72,
# saturation ~0.07, R-B ~+8; skin in the same V band reads saturation 0.24+ and R-B +46+, the
# white shirt/sweep read V 0.85+. So reclaim bright-but-not-white, LOW-saturation, low-warmth
# px adjacent to confident garment — saturation + warmth exclude skin, the V ceiling the shirt.
HILIGHT_V = 0.85     # brightness ceiling (strictly below the white shirt/sweep/square 0.87+)
HILIGHT_S = 0.15     # saturation ceiling (cloth highlight ~0.07; skin ~0.24+)
HILIGHT_W = 18       # R-B ceiling (cloth ~+8; skin ~+46+)
HILIGHT_R = 41       # adjacency reach from the garment mask itself (thin shoulder tops)
# SHOE CUT (2026-07-21). Black shoes pass every colour test (dark + neutral) so ~95% of
# shoe px were composited as garment. Invisible while the cloths were grey (grey pattern
# on black leather at near-black drape), but a navy cloth's bright pin stripes render
# straight across the leather (user-flagged). Detect the shoe top per column — the first
# sustained run of leather-dark rows in the shoe band — and zero the mask from there down.
# Leather body V < ~0.13; the trouser hem above it stays 0.25-0.45 even in the break shadow.
SHOE_Y0  = 0.855     # shoes exist only below this fraction of height
SHOE_V   = 0.13      # leather-body darkness
SHOE_RUN = 8         # consecutive dark rows that mean "leather", not a crease shadow


def _dilate(b, r):
    """fast separable boolean dilation by radius r (PIL MaxFilter is O(k^2) and too slow at r~40)"""
    a = b.copy()
    for s in range(1, r + 1):
        a[:, s:] |= b[:, :-s]; a[:, :-s] |= b[:, s:]
    out = a.copy()
    for s in range(1, r + 1):
        out[s:, :] |= a[:-s, :]; out[:-s, :] |= a[s:, :]
    return out


def suit_mask(img, clean=CLEAN, feather=FEATHER):
    """Returns a COVERAGE mask, not a blurred binary.

    The alpha at the silhouette must equal the garment's own pixel coverage. A hard threshold
    plus square-kernel morphology puts the boundary *inside* the garment's antialiased edge,
    so the mid-grey base render shows through as a ragged light fringe along the sleeves —
    visible at 5x against the clean edge the hand-made masks produced. So: morphology decides
    the INTERIOR only, and the edge comes from a soft ramp on the classifier's own margin.
    """
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    mx, mn = a.max(-1), a.min(-1)
    V = mx / 255.0
    S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    bg = (V > BG_V) & (S < BG_S)
    blue_ok = a[..., 2] >= a[..., 0] - BLUE_BIAS

    # soft coverage ramp across the silhouette: 1 well inside the cloth, 0 on the sweep
    ramp = np.clip((V_MAX + 0.10 - V) / 0.16, 0, 1) * blue_ok * ~bg

    # interior: morphology fills pinholes (buttons, shadows) and drops specks (hair, glints)
    hard = Image.fromarray(((ramp > 0.5) * 255).astype("uint8"))
    hard = hard.filter(ImageFilter.MaxFilter(clean)).filter(ImageFilter.MinFilter(clean))
    hard = hard.filter(ImageFilter.MinFilter(clean)).filter(ImageFilter.MaxFilter(clean))
    # pull the morphology result back off the boundary so it can only fill, never reshape
    interior = np.asarray(hard.filter(ImageFilter.MinFilter(clean))).astype(np.float32) / 255.0

    alpha = np.maximum(ramp, interior)

    # skin-bounce reclaim — see constants above
    warm = a[..., 0] - a[..., 2]
    spill_ramp = np.clip((V_MAX + 0.10 - V) / 0.16, 0, 1) * (warm < WARM_SPILL) * ~bg
    near = np.asarray(Image.fromarray(((interior > 0.5) * 255).astype("uint8"))
                      .filter(ImageFilter.MaxFilter(SPILL_R))) > 127
    below = np.zeros_like(near)
    below[int(alpha.shape[0] * SPILL_Y0):, :] = True
    alpha = np.maximum(alpha, spill_ramp * (near & below))

    # MID/BRIGHT INTERIOR-CLOTH RECLAIM — see constants above. Shoulder highlights (side/back)
    # read V ~0.55-0.85; the darkness ramp only PARTIALLY covers V 0.49-0.65 (~0.3 alpha), so
    # the grey base shows through as patches. Give FULL alpha to neutral, non-warm cloth that
    # is adjacent to garment but NOT within a few px of the background (so the silhouette edge
    # keeps its soft antialiased ramp). Skin is excluded by saturation + warmth, the white
    # shirt/sweep/pocket-square by the V ceiling (they read 0.87+).
    garm_near = _dilate(alpha > 0.5, HILIGHT_R)
    bg_edge = _dilate(bg, 6)
    hilite = ((V >= 0.50) & (V < HILIGHT_V) & (S < HILIGHT_S) & (warm < HILIGHT_W)
              & ~bg & ~bg_edge & garm_near)
    alpha = np.maximum(alpha, hilite.astype(np.float32))

    # INTERIOR HOLE FILL (2026-07-21). Sleeve/shoulder highlights on some renders exceed
    # the darkness ceiling and punch grey holes mid-garment (peak sleeve, visible as grey
    # blotches on navy). Fill any ENCLOSED non-garment pixel that is neutral and mid-dark;
    # the shirt stays a hole (bright) and the hands stay holes (warm).
    # NB: ImageDraw.floodfill is a silent no-op on 'L' images in Pillow 11.3 — run it on RGB.
    inv_a = ((alpha <= 0.5) * 255).astype("uint8")
    inv = Image.fromarray(np.repeat(inv_a[..., None], 3, axis=2))
    for pt in [(0, 0), (inv.width - 1, 0), (0, inv.height - 1), (inv.width - 1, inv.height - 1)]:
        if inv.getpixel(pt)[0] == 255:
            ImageDraw.floodfill(inv, pt, (128, 128, 128))
    encl = np.asarray(inv)[..., 0] == 255
    # enclosed neutral px are interior cloth (incl. bright shoulder-blade highlights) — the
    # shirt/sweep/pocket-square are never enclosed and stay bright (V>=0.85), skin is warm.
    fill = encl & (S < 0.15) & (a[..., 0] - a[..., 2] < 20) & (V < 0.85)
    alpha = np.where(fill, 1.0, alpha)

    # shoe cut — see constants above
    h = alpha.shape[0]
    y0 = int(h * SHOE_Y0)
    dark = V[y0:, :] < SHOE_V
    c = np.cumsum(dark, axis=0)
    run = np.zeros_like(dark)
    run[SHOE_RUN:, :] = (c[SHOE_RUN:, :] - c[:-SHOE_RUN, :]) == SHOE_RUN   # ends of full runs
    has = run.any(axis=0)
    start = np.where(has, run.argmax(axis=0) - SHOE_RUN, dark.shape[0])    # top of the run
    # climb through the dim vamp / break-shadow rows above the leather run (the shoe's top
    # rows sit in the hem's shadow at V 0.13-0.24 and escaped the dark-run test — the right
    # shoe kept faint stripes). Stop at clearly-lit trouser cloth.
    Vb = V[y0:, :]
    for _ in range(25):
        can = has & (start > 0)
        dim = np.take_along_axis(Vb, np.maximum(start - 1, 0)[None, :], axis=0)[0] < 0.24
        step = can & dim
        start = start - step.astype(int)
        if not step.any(): break
    # regional hull: columns at the shoe edges (highlight/penumbra) have no clean leather
    # run and kept their cloth all the way down, leaving translucent vertical bands beside
    # each shoe. Take the running MIN of start over ±15 columns so the cut covers the whole
    # shoe blob; columns further than that from any shoe are untouched.
    startf = np.where(has, start, 10 ** 6).astype(np.int32)
    hull = startf.copy()
    for s in range(1, 16):
        hull = np.minimum(hull, np.roll(startf, s))
        hull = np.minimum(hull, np.roll(startf, -s))
    rows = np.arange(dark.shape[0])[:, None]
    cut = rows >= np.maximum(hull, 0)[None, :] - 2
    alpha[y0:, :] = np.where(cut & (hull[None, :] < 10 ** 6), 0, alpha[y0:, :])

    # KEEP THE CONNECTED GARMENT BLOB (2026-07-22). On the cooler side/back renders the hair
    # is dark-and-neutral enough to pass the classifier — it sits above the collar as a blob
    # SEPARATE from the suit (the neck / white-collar sliver is the gap). Flood-fill from a
    # seed deep inside the garment and drop everything not connected to it; the jacket and
    # trousers overlap at the waist so they are one blob. Harmless on the front (the hair was
    # already excluded there, so the largest blob is unchanged).
    binm = alpha > 0.5
    colsum = binm.sum(0)
    if colsum.max() > 0:
        sx = int(np.argmax(colsum))
        rows = np.where(binm[:, sx])[0]
        sy = int(rows[len(rows) // 2])   # an ACTUAL garment row (median value could be a gap)
        ff = Image.fromarray(np.repeat((binm * 255).astype("uint8")[..., None], 3, axis=2))
        ImageDraw.floodfill(ff, (sx, sy), (128, 128, 128))
        keep = np.asarray(ff)[..., 0] == 128
        alpha = alpha * keep

    im = Image.fromarray(np.clip(alpha * 255, 0, 255).astype("uint8"))
    return im.filter(ImageFilter.GaussianBlur(feather))


def iou(a, b):
    a, b = a > 127, b > 127
    return (a & b).sum() / max(1, (a | b).sum())


def verify():
    print(f'{"cut":24s} {"IoU":>7s} {"recall":>8s} {"precision":>10s}  coverage new/old')
    scores = []
    for c in CUTS:
        img = Image.open(f"{HM}/renders/{c}.png")
        new = np.asarray(suit_mask(img))
        old = np.asarray(Image.open(f"{HM}/drape_maps/{c}_drape.png").getchannel("A"))
        n, o = new > 127, old > 127
        rec = (n & o).sum() / max(1, o.sum())
        prec = (n & o).sum() / max(1, n.sum())
        s = iou(new, old); scores.append(s)
        print(f"{c:24s} {s:7.3f} {rec:8.3f} {prec:10.3f}  {n.mean():.1%} / {o.mean():.1%}")
    print(f"\nmean IoU across {len(scores)} cuts: {np.mean(scores):.3f}")
    return np.mean(scores)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--verify":
        verify()
    elif len(sys.argv) == 3:
        suit_mask(Image.open(sys.argv[1])).save(sys.argv[2], optimize=True)
        print(f"wrote {sys.argv[2]}")
    else:
        print(__doc__)
        sys.exit(1)
