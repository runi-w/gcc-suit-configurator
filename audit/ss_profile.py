#!/usr/bin/env python3
"""Suitsupply reference profile — measured from their production layers, used to score ours.

Builds a tonal fingerprint from the 9 SS Jacket/model layers captured 2026-07-21, then scores
our composites against it. Everything is normalised to the garment's own median so the
comparison is about SHAPE OF THE SHADING, not exposure or cloth colour — a dark navy and a
light grey can then be compared directly.

    python3 ss_profile.py                       # print the SS reference profile
    python3 ss_profile.py <prefix_> <dir>       # score our composites against it
"""
import sys, glob
import numpy as np
from PIL import Image

HM = "/Users/runiwillner/Desktop/GCC_House_Model"


def lin(x):
    x = np.asarray(x, float) / 255.0
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def Y(rgb):
    l = lin(rgb)
    return 0.2126 * l[..., 0] + 0.7152 * l[..., 1] + 0.0722 * l[..., 2]


def shape(y):
    """shading shape, normalised to the median so exposure and cloth colour drop out"""
    med = np.median(y)
    if med <= 0:
        return None
    n = y / med
    return dict(
        crease_p1=float(np.percentile(n, 1)),     # structural crease depth
        shadow_p5=float(np.percentile(n, 5)),
        fold_p25=float(np.percentile(n, 25)),
        high_p95=float(np.percentile(n, 95)),
        spec_p99=float(np.percentile(n, 99)),
        range_5_95=float(np.percentile(n, 95) - np.percentile(n, 5)),
    )


KEYS = ["crease_p1", "shadow_p5", "fold_p25", "high_p95", "spec_p99", "range_5_95"]
LABEL = {"crease_p1": "crease depth (p1/med)", "shadow_p5": "shadow (p5/med)",
         "fold_p25": "fold (p25/med)", "high_p95": "highlight (p95/med)",
         "spec_p99": "specular (p99/med)", "range_5_95": "range (p95-p5)/med"}


def ss_reference(kind="aimodel"):
    """kind='aimodel'  -> their PHOTOGRAPHIC model layer. This is the fair reference for us:
                          a garment worn on a body, same as our composites.
       kind='flat'     -> their flat Jacket/model layers. Do NOT tune against these — a garment
                          with no body inside has deep neckline-cavity darks our geometry
                          cannot have, which drags p1 to 0.092 vs 0.032 on the worn version.
                          Chasing it means inventing shadows Suitsupply never shows on a model.
    """
    import sys as _s
    _s.path.insert(0, f"{HM}/builder")
    out = []
    if kind == "aimodel":
        from make_mask import suit_mask                      # same segmenter we use on ours
        for p in sorted(glob.glob(f"{HM}/audit/ss/aimodel_*.png")):
            img = Image.open(p).convert("RGB")
            m = np.array(suit_mask(img)) > 127
            if m.sum() < 10000:
                continue
            s = shape(Y(np.array(img))[m])
            if s:
                out.append(s)
    else:
        for p in sorted(glob.glob(f"{HM}/audit/ss/model_*.png")):
            a = np.array(Image.open(p).convert("RGBA"))
            m = a[..., 3] > 200                    # hard mask, per the standing rule
            if m.sum() < 10000:
                continue
            s = shape(Y(a[..., :3])[m])
            if s:
                out.append(s)
    return out


def ours(prefix, d):
    ps = [p for p in sorted(glob.glob(f"{d}/{prefix}*.png")) if "stripe" not in p]
    if not ps:
        return [], []
    from PIL import ImageFilter
    arrs = {p: np.array(Image.open(p).convert("RGB")) for p in ps}
    M = np.stack([v.astype(float) for v in arrs.values()]).std(0).mean(-1) > 6.0
    # ERODE 3px. The anti-aliased edge band lets the mid-grey base render bleed through, which
    # on a dark cloth reads as pixels many times the median and inflates p99 from ~3.3 to ~10.9.
    # Costs 1.5% of pixels. This is the standing alpha>200 rule applied to a variance mask.
    M = np.asarray(Image.fromarray((M * 255).astype("uint8"))
                   .filter(ImageFilter.MinFilter(3))) > 127
    res, names = [], []
    for p, a in arrs.items():
        s = shape(Y(a)[M])
        if s:
            res.append(s); names.append(p.split("/")[-1][:-4])
    return res, names


if __name__ == "__main__":
    ref = ss_reference("aimodel")
    if not ref:
        print("no SS layers found in audit/ss/"); sys.exit(1)
    band = {k: (np.percentile([r[k] for r in ref], 25),
                np.percentile([r[k] for r in ref], 75),
                np.median([r[k] for r in ref])) for k in KEYS}

    print(f"SUITSUPPLY REFERENCE PROFILE  (n={len(ref)} production layers)")
    print("shading shape, each normalised to that garment's own median\n")
    print(f'  {"measure":26s} {"median":>8s} {"IQR band":>18s}')
    for k in KEYS:
        lo, hi, md = band[k]
        print(f"  {LABEL[k]:26s} {md:8.3f}   {lo:6.3f} - {hi:6.3f}")

    if len(sys.argv) >= 3:
        res, names = ours(sys.argv[1], sys.argv[2])
        if not res:
            print(f"\nno composites matched {sys.argv[2]}/{sys.argv[1]}*.png"); sys.exit(1)
        print(f"\n\nOURS  (n={len(res)})   in-band = within Suitsupply's interquartile range\n")
        print(f'  {"measure":26s} {"ours":>8s} {"SS median":>10s} {"verdict":>26s}')
        for k in KEYS:
            lo, hi, md = band[k]
            v = float(np.median([r[k] for r in res]))
            if lo <= v <= hi:
                verdict = "in band"
            else:
                d = (v - md) / md * 100
                verdict = f"{'flatter' if (v > md) == (k in ('crease_p1','shadow_p5','fold_p25')) else 'deeper'} ({d:+.0f}%)"
                if k in ("high_p95", "spec_p99", "range_5_95"):
                    verdict = f"{'higher' if v > md else 'lower'} ({d:+.0f}%)"
            print(f"  {LABEL[k]:26s} {v:8.3f} {md:10.3f} {verdict:>26s}")
        print("\n  (crease/shadow/fold: LOWER = darker, deeper shading."
              "\n   highlight/specular/range: HIGHER = more contrast.)")
