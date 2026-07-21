#!/usr/bin/env python3
"""Audit how a PATTERN maps onto the garment: orientation, continuity, and warp behaviour.

This measures the thing you actually see wrong on a striped suit — stripes that lean, wobble,
or fail to break at a seam — rather than overall tone, which the other tools cover.

Method: a structure tensor gives the dominant local orientation of the cloth pattern. On a real
striped suit, stripes run close to vertical on the body panels, tilt gently over the chest and
shoulder as the cloth turns, and break cleanly where the lapel folds back. What we do NOT want
is high local variance at fold scale, which reads as wobble (explicitly rejected in the playbook).

    python3 pattern_map.py <image.png> [mask.png]      # ours or a Suitsupply layer

Reports per body band: mean stripe angle from vertical, and the spread of that angle.
Low spread = ruled, straight, panel-like. High spread = wobbly.
"""
import sys
import numpy as np
from PIL import Image, ImageFilter


def _fblur(x, sigma):
    """Separable Gaussian in float. PIL's GaussianBlur rejects mode 'F', and going via uint8
    would quantise the tensor components into uselessness."""
    r = max(1, int(round(3 * sigma)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    x = np.asarray(x, np.float32)
    pad = np.pad(x, ((0, 0), (r, r)), mode="edge")
    x = np.apply_along_axis(lambda m: np.convolve(m, k, "valid"), 1, pad)
    pad = np.pad(x, ((r, r), (0, 0)), mode="edge")
    return np.apply_along_axis(lambda m: np.convolve(m, k, "valid"), 0, pad)


def orientation_field(gray, sigma=2.0):
    """dominant orientation per pixel via the structure tensor"""
    g = _fblur(gray, 1.0)
    gy, gx = np.gradient(g)
    Jxx = _fblur(gx * gx, sigma)
    Jyy = _fblur(gy * gy, sigma)
    Jxy = _fblur(gx * gy, sigma)
    # angle of the dominant gradient; stripe direction is perpendicular to it
    theta = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy)
    coherence = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / np.maximum(Jxx + Jyy, 1e-6)
    stripe_ang = np.degrees(theta)                      # gradient angle
    stripe_ang = (stripe_ang + 90) % 180 - 90           # wrap to [-90, 90)
    return stripe_ang, coherence


def audit(img_path, mask_path=None, bands=5):
    img = Image.open(img_path)
    if mask_path:
        m = np.asarray(Image.open(mask_path).convert("L")) > 127
        rgb = np.asarray(img.convert("RGB"))
    elif img.mode == "RGBA":
        a = np.asarray(img)
        m = a[..., 3] > 200
        rgb = a[..., :3]
    else:
        sys.path.insert(0, "/Users/runiwillner/Desktop/GCC_House_Model/builder")
        from make_mask import suit_mask
        rgb = np.asarray(img.convert("RGB"))
        m = np.asarray(suit_mask(img)) > 127
    gray = rgb.mean(-1)
    ang, coh = orientation_field(gray)
    strong = m & (coh > 0.35)                      # only where a pattern actually reads
    h = gray.shape[0]
    rows = np.where(m.any(1))[0]
    y0, y1 = rows[0], rows[-1]
    print(f"{img_path.split('/')[-1]:38s}  patterned px {strong.sum():,} "
          f"({strong.sum()/max(m.sum(),1):.0%} of garment)")
    print(f'  {"body band":16s} {"mean angle":>11s} {"spread (sd)":>12s} {"verdict":>16s}')
    out = []
    for i in range(bands):
        a0 = int(y0 + (y1 - y0) * i / bands)
        a1 = int(y0 + (y1 - y0) * (i + 1) / bands)
        sel = strong.copy(); sel[:a0] = False; sel[a1:] = False
        if sel.sum() < 500:
            continue
        v = ang[sel]
        # circular stats on a 180-degree axis
        c, s = np.cos(np.radians(2 * v)).mean(), np.sin(np.radians(2 * v)).mean()
        mean = np.degrees(np.arctan2(s, c)) / 2
        R = np.hypot(c, s)
        sd = np.degrees(np.sqrt(max(-2 * np.log(max(R, 1e-9)), 0))) / 2
        # Thresholds calibrated against Suitsupply's own striped production layers, which
        # measure 20-35 deg of spread (weave texture and panel variation both contribute, so
        # a high number is not automatically wobble). Below ~18 would mean an unnaturally
        # ruled, printed-on look; above ~38 is genuine wobble.
        verdict = ("too ruled" if sd < 18 else
                   "in SS range" if sd <= 35 else "WOBBLY")
        # the mean angle is the real alignment test: SS hold every band within +/-0.7 deg
        if abs(mean) > 4:
            verdict += " / LEANING"
        out.append((mean, sd))
        print(f"  band {i+1} ({a0:5d}-{a1:5d}) {mean:+10.1f}° {sd:11.1f}° {verdict:>16s}")
    if out:
        sds = [o[1] for o in out]
        print(f"  {'OVERALL':16s} {'':11s} {np.mean(sds):11.1f}° "
              f"{'(lower = straighter, more panel-like)':>16s}")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    audit(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
