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
from PIL import Image, ImageFilter

HM = "/Users/runiwillner/Desktop/GCC_House_Model"
CUTS = ["front_2button_notch", "front_2button_peak", "front_1button_peak",
        "front_doublebreasted", "front_3piece_vest"]

# tuned on the navy house suit; see --verify for the IoU these produce
V_MAX      = 0.55    # suit is darker than skin, shirt and sweep
BLUE_BIAS  = 8       # B >= R - 8 : neutral-to-bluish, excludes warm skin and brown shoes
BG_V, BG_S = 0.90, 0.06
CLEAN      = 5       # morphological radius (px at 1792 wide)
FEATHER    = 0.8       # smaller: the ramp already supplies the soft edge


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
