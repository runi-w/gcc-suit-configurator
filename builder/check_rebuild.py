#!/usr/bin/env python3
"""Acceptance gate for a REBUILD candidate render, against the current hero as baseline.

check_render.py answers "is this a valid asset". This answers the different question the rebuild
actually asks: "is this BETTER than what we already ship, on the four things we know are wrong?"

    python3 builder/check_rebuild.py <candidate.png> [--baseline renders/front_2button_notch.orig.png]

Writes a QA sheet to $OUT (default /tmp) and prints a verdict per axis.

⚠ THE GORGE IS NOT SCORED, AND THAT IS DELIBERATE. Three metrics were tried against a
known-broken render and its retouched twin: total edge energy read 0.89-1.00 on BOTH;
largest-connected-component with a per-side percentile threshold read 0.99 on the BROKEN one and
0.61 on the FIXED one (backwards); a shared absolute threshold gave 0.68 vs 0.68. Every variant
locks onto the lapel's outer edge and the shoulder line, which are present either way. A check
that reports PASS on a render with no right gorge is worse than no check. So this tool CROPS both
gorges at 4x and puts them side by side in the sheet — you decide with your eyes. That is the
gate, and it is the one that has never been wrong.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HM = "/Users/runiwillner/Desktop/GCC_House_Model"
OUT = os.environ.get("OUT", "/tmp")
BASELINE = f"{HM}/renders/front_2button_notch.orig.png"   # pristine, pre-retouch


def _font(s):
    try:
        return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", s)
    except Exception:
        return ImageFont.load_default()


def _garment(im):
    """The same 'darkish and neutral' test make_mask.py opens with, so this measures what the
    pipeline will actually treat as cloth — not what a human would call the suit."""
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    mx, mn = a.max(-1), a.min(-1)
    V = mx / 255.0
    S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    g = (V < 0.62) & (S < 0.22) & (a[..., 2] >= a[..., 0] - 26)
    h = g.shape[0]
    g[: int(h * 0.12)] = False           # head
    g[int(h * 0.88):] = False            # shoes and floor
    return g


def detail_density(im, g):
    """Fraction of garment pixels carrying construction structure.

    This is the axis the compositor now depends on: build_configurator's detail layer extracts
    exactly this band (seams, welts, buttonholes, edge stitching) and re-applies it OVER the
    customer's cloth. A render with thin construction detail cannot be rescued downstream — the
    information simply is not there. Band 0.8-6 px: below that is weave noise, above it is folds.
    """
    L = im.convert("L")
    lo = np.asarray(L.filter(ImageFilter.GaussianBlur(6.0)), np.float32)
    hi = np.asarray(L.filter(ImageFilter.GaussianBlur(0.8)), np.float32)
    d = hi - lo
    if g.sum() < 1000:
        return 0.0, 0.0
    return float((np.abs(d[g]) > 8).mean()), float(d[g].std())


def tone(im, g):
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    lum = a.mean(-1)
    mx, mn = a.max(-1), a.min(-1)
    S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    h, w = lum.shape
    # shirt: bright + neutral, inside the figure's upper half, away from the frame edge
    box = np.zeros((h, w), bool)
    box[int(h * 0.13):int(h * 0.55), int(w * 0.30):int(w * 0.70)] = True
    shirt = box & (lum > 195) & (S < 0.12)
    out = {
        "frame_clip255": 100 * float((lum >= 254.5).mean()),
        "frame_over250": 100 * float((lum >= 250).mean()),
        "garment_p1": float(np.percentile(lum[g], 1)) if g.sum() else 0.0,
        "garment_p99": float(np.percentile(lum[g], 99)) if g.sum() else 0.0,
        "garment_crushed": 100 * float((lum[g] <= 2).mean()) if g.sum() else 0.0,
    }
    if shirt.sum() > 500:
        v = lum[shirt]
        out["shirt_px"] = int(shirt.sum())
        out["shirt_p50"] = float(np.percentile(v, 50))
        out["shirt_over250"] = 100 * float((v >= 250).mean())
        out["shirt_std"] = float(v.std())
    return out


def lr_balance(im, g):
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    lum = a.mean(-1)
    h, w = lum.shape
    xs = np.arange(w)[None, :] * np.ones((h, 1))
    if g.sum() < 1000:
        return 0.0
    cx = xs[g].mean()
    L, R = g & (xs < cx), g & (xs >= cx)
    if L.sum() < 500 or R.sum() < 500:
        return 0.0
    return float(lum[R].mean() - lum[L].mean())


def gorge_crops(im, scale=4):
    """Both gorges, cropped and scaled, for the eyeball gate. Located from the shirt opening,
    the same registration fix_gorge.py uses — the jacket laps left over right, so the two gorges
    are NOT symmetric about the neck and a guessed mirror axis lands in the wrong place."""
    a = np.asarray(im.convert("RGB")).astype(np.float32)
    H, W, _ = a.shape
    g = _garment(im)
    y0, y1 = int(H * 0.175), int(H * 0.26)
    L, R = [], []
    for y in range(y0, y1):
        row = g[y]
        d = np.diff(np.concatenate(([0], row.view(np.int8), [0])))
        runs = [(s, e) for s, e in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1)
                if e - s > 12]
        best = None
        for i in range(len(runs) - 1):
            a0, b0 = runs[i][1], runs[i + 1][0]
            if a0 < W / 2 < b0 and (best is None or (b0 - a0) > best[1] - best[0]):
                best = (a0, b0)
        if best:
            L.append(best[0]); R.append(best[1])
    if len(L) < 15:
        cl, cr = int(W * 0.42), int(W * 0.58)
    else:
        cl, cr = int(np.median(L)), int(np.median(R))
    wide = int(W * 0.10)
    box_l = (max(0, cl - wide), y0, min(W, cl + int(wide * 0.35)), y1)
    box_r = (max(0, cr - int(wide * 0.35)), y0, min(W, cr + wide), y1)
    out = []
    for b in (box_l, box_r):
        c = im.crop(b)
        out.append(c.resize((c.width * scale, c.height * scale), Image.LANCZOS))
    return out


def report(path, base_path):
    im = Image.open(path).convert("RGB")
    bs = Image.open(base_path).convert("RGB") if os.path.exists(base_path) else None
    g = _garment(im)
    rows = []

    dd, ds = detail_density(im, g)
    t = tone(im, g)
    lr = lr_balance(im, g)

    bl = {}
    if bs is not None:
        gb = _garment(bs)
        bd, bsd = detail_density(bs, gb)
        bt = tone(bs, gb)
        bl = dict(detail=bd, dstd=bsd, tone=bt, lr=lr_balance(bs, gb))

    def line(name, val, base, good, fmt="{:.2f}", note=""):
        b = fmt.format(base) if base is not None else "  -  "
        mark = "OK " if good else "!! "
        print(f"  {mark}{name:34s} {fmt.format(val):>10s}   baseline {b:>10s}   {note}")
        rows.append(good)

    print(f"\n=== {os.path.basename(path)}  {im.size} ===\n")
    print("CONSTRUCTION DETAIL — the layer the compositor re-applies over the cloth")
    line("garment px with |detail| > 8", 100 * dd, 100 * bl.get("detail", 0) if bl else None,
         dd >= bl.get("detail", 0) if bl else True, "{:.1f}%", "higher is better")
    line("band-pass std (levels)", ds, bl.get("dstd") if bl else None,
         ds >= bl.get("dstd", 0) if bl else True, "{:.2f}", "higher is better")

    print("\nTONE — headroom and shadow detail")
    line("frame px at 255", t["frame_clip255"],
         bl["tone"]["frame_clip255"] if bl else None, t["frame_clip255"] < 0.05, "{:.3f}%",
         "want < 0.05%")
    if "shirt_p50" in t:
        line("shirt median", t["shirt_p50"], bl["tone"].get("shirt_p50") if bl else None,
             t["shirt_p50"] <= 245, "{:.0f}", "want <= 245, reference sits ~242")
        line("shirt px >= 250", t["shirt_over250"], bl["tone"].get("shirt_over250") if bl else None,
             t["shirt_over250"] < 5, "{:.1f}%", "want < 5%")
        line("shirt texture (std)", t["shirt_std"], bl["tone"].get("shirt_std") if bl else None,
             t["shirt_std"] > 3.0, "{:.2f}", "want > 3, flat = paper cutout")
    line("garment p1 (shadow detail)", t["garment_p1"],
         bl["tone"]["garment_p1"] if bl else None, t["garment_p1"] > 8, "{:.0f}",
         "want > 8, crushed folds are dead drape")
    line("garment crushed to black", t["garment_crushed"],
         bl["tone"]["garment_crushed"] if bl else None, t["garment_crushed"] < 0.2, "{:.3f}%",
         "want < 0.2%")

    print("\nLIGHTING — asymmetry is NOT a defect (Suitsupply ships -14 to +23)")
    line("right minus left (levels)", lr, bl.get("lr") if bl else None,
         abs(lr) < 30, "{:+.1f}", "want |x| < 30; 0 would be flat and lifeless")

    bad = rows.count(False)
    print(f"\n  {len(rows) - bad}/{len(rows)} numeric axes OK"
          + ("" if not bad else f"   — {bad} need attention"))

    # ---- the sheet: gorges at 4x, side by side, candidate over baseline ----
    panes = gorge_crops(im)
    labels = ["candidate  LEFT gorge", "candidate  RIGHT gorge"]
    if bs is not None:
        panes += gorge_crops(bs)
        labels += ["baseline  LEFT gorge", "baseline  RIGHT gorge"]
    w = max(p.width for p in panes)
    h = max(p.height for p in panes)
    cols = 2
    rowsn = (len(panes) + 1) // 2
    sheet = Image.new("RGB", (w * cols + 18, (h + 26) * rowsn), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    for i, (lab, p) in enumerate(zip(labels, panes)):
        x = (i % cols) * (w + 12)
        y = (i // cols) * (h + 26) + 22
        d.text((x + 3, y - 17), lab, font=_font(13), fill=(240, 240, 240))
        sheet.paste(p, (x, y))
    out = f"{OUT}/rebuild_gorge.png"
    sheet.save(out)
    print(f"\n  gorge sheet -> {out}")
    print("  ⚠ JUDGE THE GORGE BY EYE. Both notches present, similar size, similar height?")
    print("    No metric can do this — three were tried and one read backwards.\n")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__); sys.exit(2)
    base = BASELINE
    if "--baseline" in sys.argv:
        base = sys.argv[sys.argv.index("--baseline") + 1]
    for p in args:
        report(p, base)
