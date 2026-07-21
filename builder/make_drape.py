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


def make_drape(render_img, mask_img):
    rgb = np.asarray(render_img.convert("RGB"))
    lum = luminance(rgb)
    mask = np.asarray(mask_img.convert("L"))
    m = mask > 200                       # hard threshold, per the standing measurement rule
    if m.sum() < 1000:
        raise ValueError(f"mask covers only {m.sum()} px — segmentation probably failed")
    med = np.median(lum[m])
    if med < 1:
        raise ValueError("garment median luminance is ~0; wrong mask?")
    L = np.clip(lum * (TARGET_MEDIAN / med), 0, 255).astype("uint8")
    out = Image.merge("LA", [Image.fromarray(L), Image.fromarray(mask.astype("uint8"))])
    return out, dict(coverage=float(m.mean()), median_before=float(med),
                     gain=float(TARGET_MEDIAN / med))


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
