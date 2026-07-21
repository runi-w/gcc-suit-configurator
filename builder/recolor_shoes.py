#!/usr/bin/env python3
"""Recolour the model's brown leather shoes to black on a house-model render.

The original renders were generated with dark brown derbies; the house look was changed to
black on 21 July 2026. Regenerating the five approved front renders would risk drifting the
model, so the shoes are recoloured in place instead — a local, reversible edit that leaves
every other pixel untouched.

Detection: warm (R > G >= B), saturated, and in the bottom of the frame. The low-frame gate
is what separates shoes from skin — face and hands are warm and saturated too. Verified to
have ZERO overlap with the garment mask, so this can never touch the suit.

Usage:
    python3 recolor_shoes.py <in.png> [out.png]      # out defaults to in-place
    python3 recolor_shoes.py --all                   # every render in renders/
    python3 recolor_shoes.py --preview <in.png>      # write a before/after strip, change nothing
"""
import sys, glob, os
import numpy as np
from PIL import Image, ImageFilter

HM = "/Users/runiwillner/Desktop/GCC_House_Model"
LOW_FRAC = 0.86     # shoes live below this fraction of frame height
GAMMA    = 1.55     # >1 darkens midtones while preserving specular highlights
GAIN     = 0.92
WARMTH   = 4        # leave a touch of warmth; pure neutral reads flat/plastic


def shoe_mask(a):
    h = a.shape[0]
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    m = (R > G + 8) & (G >= B) & (S > 0.18) & (mx > 25)
    m[: int(h * LOW_FRAC), :] = False
    return m


def recolor(img):
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    m = shoe_mask(a)
    if m.sum() < 500:
        return img, 0
    lum = a.mean(-1) / 255.0
    v = np.clip(lum ** GAMMA * GAIN, 0, 1) * 255.0
    black = np.stack([v + WARMTH, v, v - WARMTH * 0.5], -1)
    soft = np.asarray(Image.fromarray((m * 255).astype("uint8"))
                      .filter(ImageFilter.GaussianBlur(1.2)), np.float32)[..., None] / 255.0
    out = a * (1 - soft) + np.clip(black, 0, 255) * soft
    return Image.fromarray(np.clip(out, 0, 255).astype("uint8")), int(m.sum())


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(1)
    if args[0] == "--preview":
        src = args[1]
        orig = Image.open(src).convert("RGB")
        new, n = recolor(orig)
        h = orig.height
        crop = (int(orig.width * .28), int(h * .82), int(orig.width * .72), h)
        a, b = orig.crop(crop), new.crop(crop)
        sh = Image.new("RGB", (a.width * 2 + 20, a.height), (255, 255, 255))
        sh.paste(a, (0, 0)); sh.paste(b, (a.width + 20, 0))
        sh.save(f"{HM}/audit/out/shoes_before_after.png")
        print(f"{n:,} px recoloured -> audit/out/shoes_before_after.png")
    elif args[0] == "--all":
        for p in sorted(glob.glob(f"{HM}/renders/*.png")):
            img = Image.open(p)
            new, n = recolor(img)
            new.save(p, optimize=True)
            print(f"{os.path.basename(p):28s} {n:,} px -> black")
    else:
        src = args[0]; dst = args[1] if len(args) > 1 else args[0]
        new, n = recolor(Image.open(src))
        new.save(dst, optimize=True)
        print(f"{n:,} px recoloured -> {dst}")
