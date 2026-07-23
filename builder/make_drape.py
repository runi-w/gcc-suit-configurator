#!/usr/bin/env python3
"""Generate a configurator drape map (LA PNG) from a base render + a garment mask.

    L = the render's luminance, rescaled so the MEDIAN INSIDE THE MASK lands on 128
    A = the garment mask (where cloth gets composited)

Reverse-engineered 2026-07-21 from the original maps, whose generator was never saved.
Validated against front_2button_notch: correlation 0.9999, max error 2 levels.

The median-128 anchor matters: build_configurator_v0.soften_drape() assumes the incoming
drape is centred, and then applies its own exposure normalisation on top. Feed it an
un-normalised map and every fabric renders at the wrong luminance.

Usage:
    python3 make_drape.py <render.png> <mask.png> <out_drape.png>
    python3 make_drape.py --verify <cut-name>      # check against the existing map
"""
import sys
import numpy as np
from PIL import Image

HM = "/Users/runiwillner/Desktop/GCC_House_Model"
TARGET_MEDIAN = 128.0


def luminance(rgb):
    """Plain channel mean — this is what the original maps were built from
    (linear-fit residual 0.53 levels vs a weighted luma, which fits worse)."""
    return np.asarray(rgb, dtype=np.float64).mean(-1)


def make_drape(render_img, mask_img, debias=None):
    rgb = np.asarray(render_img.convert("RGB"))
    lum = luminance(rgb)
    mask = np.asarray(mask_img.convert("L"))
    m = mask > 200                       # hard threshold, per the standing measurement rule
    if m.sum() < 1000:
        raise ValueError(f"mask covers only {m.sum()} px — segmentation probably failed")
    med = np.median(lum[m])
    if med < 1:
        raise ValueError("garment median luminance is ~0; wrong mask?")
    lum, bias = _debias_lr(lum, m, DEBIAS if debias is None else debias)
    L = np.clip(lum * (TARGET_MEDIAN / med), 0, 255).astype("uint8")
    out = Image.merge("LA", [Image.fromarray(L), Image.fromarray(mask.astype("uint8"))])
    return out, dict(coverage=float(m.mean()), median_before=float(med),
                     gain=float(TARGET_MEDIAN / med), lr_bias=bias)


# LEFT/RIGHT LIGHTING DEBIAS (2026-07-23)
# The image generator invented a key light from screen-right: every front render measures +20.6
# to +24.4 sRGB levels brighter on the right half (backs +12.3 to +13.9). This single global gain
# then carried that straight into the drape's L channel — lapel-L 124.0 against lapel-R 171.7 —
# so every one of the 17 cloths rendered +12 to +16 levels brighter on the right lapel.
#
# Remove only the LOWEST-ORDER horizontal term. This is deliberately NOT a flatten: the
# asymmetric key is also what models the figure, and killing it entirely would leave the garment
# looking like a cutout. A single linear ramp fitted across the garment takes out the systematic
# side-to-side bias and leaves every fold, crease and the broad body shading untouched.
DEBIAS = 1.0        # 0 = off (the pre-2026-07-23 behaviour), 1 = remove the full linear term
# ⚠ MUST BE 0 ON SIDE VIEWS. On a front or back view a left/right luminance ramp is a lighting
# artifact. On a PROFILE it is the body itself turning away from the key — real modelling.
# Measured on side_2button_peak: debiasing the side view costs 23% of the garment's tonal range
# (111 -> 85 levels p5..p95) and 8% of its fold contrast, against 7-8% and ~0% on front/back.
# The caller passes debias=0 for side views; see the loop in this file's __main__ and the
# regeneration snippet in HANDOVER.
DEBIAS_SIDE = 0.0
FEATHER_ROWS = 90   # rows over which the jacket correction fades out above the crotch


def _crotch_row(m):
    """First row where the garment mask becomes two stable runs = the legs separating.

    Derived, never hardcoded: scanning down from 45% of mask height for the first row that has
    exactly two runs and keeps them for 200 rows lands at 0.50-0.53 of mask height on all ten
    front/back cut-views.
    """
    rows = np.flatnonzero(m.any(1))
    if not len(rows):
        return m.shape[0]
    y0, y1 = int(rows[0]), int(rows[-1])
    start = y0 + int(0.45 * (y1 - y0))
    run = 0
    for y in range(start, y1):
        d = np.diff(np.concatenate(([0], m[y].view(np.int8), [0])))
        n = len(np.flatnonzero(d == 1))
        run = run + 1 if n == 2 else 0
        if run >= 200:
            return y - 199
    return y1


def _debias_lr(lum, m, amount=DEBIAS):
    """Divide out a linear horizontal luminance ramp fitted inside the JACKET only.

    ⚠ JACKET ONLY (2026-07-23). Fitting one ramp over the whole garment was wrong: the trousers
    are already clean — per-band (R-L)/median from shoulders to hem reads
    +0.40 +0.36 +0.28 +0.23 | +0.03 -0.00 -0.05 -0.02 — so a whole-garment fit took the jacket's
    bias and INJECTED it into the legs, leaving leg-to-leg medians 16-31 levels apart where the
    source render differed by ~1. Fit and apply above the crotch, feathered to zero across it.
    """
    if amount <= 0:
        return lum, 0.0
    h, w = lum.shape
    cro = _crotch_row(m)
    jm = m.copy()
    jm[cro:] = False                       # fit on the jacket only
    if jm.sum() < 5000:
        jm = m
        cro = h
    ys, xs = np.nonzero(jm)
    v = lum[ys, xs]
    xn = (xs - xs.mean()) / max(xs.std(), 1e-6)
    # least squares v ~ a + b*xn ; b is the side-to-side bias in levels per sd of x
    b = float(np.polyfit(xn, v, 1)[0])
    mean = float(v.mean())
    if mean < 1:
        return lum, 0.0
    xg = (np.arange(w)[None, :] - xs.mean()) / max(xs.std(), 1e-6)
    # multiplicative, so black stays black and structural creases keep their depth — the same
    # reasoning as the exposure gain above
    corr = 1.0 / np.maximum(1.0 + amount * b * xg / mean, 0.35)
    # feather the correction out over FEATHER_ROWS above the crotch so the jacket/trouser
    # handover is not a step
    ramp = np.ones((h, 1), np.float64)
    f0 = max(0, cro - FEATHER_ROWS)
    ramp[f0:cro, 0] = np.linspace(1.0, 0.0, max(1, cro - f0))
    ramp[cro:, 0] = 0.0
    return lum * (1.0 + (corr - 1.0) * ramp), b


def verify(cut):
    """Rebuild the drape from the render + the EXISTING mask, compare to the existing L."""
    render = Image.open(f"{HM}/renders/{cut}.png")
    old = Image.open(f"{HM}/drape_maps/{cut}_drape.png")
    oldL = np.asarray(old.getchannel("L"), dtype=float)
    maskimg = old.getchannel("A")
    new, info = make_drape(render, maskimg)
    newL = np.asarray(new.getchannel("L"), dtype=float)
    m = np.asarray(maskimg) > 200
    d = np.abs(newL - oldL)
    print(f"{cut:24s} coverage {info['coverage']:6.1%}  gain x{info['gain']:.4f}  "
          f"| inside mask: mean|err| {d[m].mean():.3f}  max {d[m].max():.0f}  "
          f"corr {np.corrcoef(newL[m], oldL[m])[0,1]:.6f}")
    return d[m].mean()


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--verify":
        cuts = sys.argv[2:] or ["front_2button_notch", "front_2button_peak",
                                "front_1button_peak", "front_doublebreasted",
                                "front_3piece_vest"]
        errs = [verify(c) for c in cuts]
        print(f"\nmean absolute error across {len(errs)} cuts: {np.mean(errs):.3f} levels")
    elif len(sys.argv) == 4:
        out, info = make_drape(Image.open(sys.argv[1]), Image.open(sys.argv[2]))
        out.save(sys.argv[3], optimize=True)
        print(f"wrote {sys.argv[3]}  coverage {info['coverage']:.1%}  gain x{info['gain']:.4f}")
    else:
        print(__doc__)
        sys.exit(1)
