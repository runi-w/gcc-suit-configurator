#!/usr/bin/env python3
"""R2 — per-panel stripe-angle measurement (Path A research plan).

Extends pattern_map.py's structure-tensor orientation field from horizontal BANDS to named
PANEL regions (lapel, chest, collar, sleeve, trouser) so we get a real per-panel target-angle
table instead of a single torso number. See plan/PATH_A_GRAIN_SPEC.md for the results this
tool produced.

v2 fix (found by rendering a diagnostic overlay and looking, per the playbook's "always look"
rule): pattern_map.py's coherence ratio sqrt((Jxx-Jyy)^2+4Jxy^2)/max(Jxx+Jyy,1e-6) blows up on
flat/near-uniform regions (studio background, smooth shirt/skin, or — on an isolated component
PNG — the silhouette OUTLINE itself) because floating-point noise in a near-zero-energy
denominator can still read as "coherent". A coherence-only threshold is not enough. Fixed with:
  1. A real subject mask — flood-filled background removal for a photo-on-plain-background input,
     or the alpha channel for an isolated RGBA component cutout (pass rgba_alpha=True).
  2. A RAW GRADIENT ENERGY floor (Jxx+Jyy), not just the normalised coherence ratio, so flat
     skin/shirt/background pixels (real energy, no orientation) are excluded too.
  3. Optional interior erosion (erode_px) for isolated cutouts, so the measurement doesn't pick up
     the silhouette edge itself instead of the interior weave — this mattered a lot on Suitsupply's
     small flat component PNGs (lapel/sleeve), where the edge is a strong, wrong signal.

    python3 panel_angles.py <image.png> <rois.json> [--out prefix.json] [--viz prefix]
                            [--rgba-alpha] [--erode N] [--energy-pctl P] [--coh T]

rois.json: {"name": [x0,y0,x1,y1], ...} in the image's native pixel space.
"""
import sys, json
from collections import deque
import numpy as np
from PIL import Image

sys.path.insert(0, "/Users/runiwillner/Desktop/GCC_House_Model/audit")
from pattern_map import _fblur


def orientation_and_energy(gray, sigma=2.0):
    g = _fblur(gray, 1.0)
    gy, gx = np.gradient(g)
    Jxx = _fblur(gx * gx, sigma)
    Jyy = _fblur(gy * gy, sigma)
    Jxy = _fblur(gx * gy, sigma)
    theta = 0.5 * np.arctan2(2 * Jxy, Jxx - Jyy)
    energy = Jxx + Jyy
    coherence = np.sqrt((Jxx - Jyy) ** 2 + 4 * Jxy ** 2) / np.maximum(energy, 1e-6)
    stripe_ang = np.degrees(theta)
    stripe_ang = (stripe_ang + 90) % 180 - 90
    return stripe_ang, coherence, energy


def bg_mask(rgb, tol=14):
    """Flood-fill near-uniform background from the 4 corners (low-res for speed then upscale).
    Returns True where background. Use for a photo shot on a plain studio background."""
    h, w = rgb.shape[:2]
    scale = 4
    small = np.asarray(Image.fromarray(rgb).resize((w // scale, h // scale), Image.BILINEAR))
    H, W = small.shape[:2]
    g = small.mean(-1)
    seeds = [(0, 0), (0, W - 1), (H - 1, 0), (H - 1, W - 1)]
    seed_val = np.mean([g[y, x] for y, x in seeds])
    visited = np.zeros((H, W), bool)
    q = deque(seeds)
    for y, x in seeds:
        visited[y, x] = True
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and not visited[ny, nx]:
                if abs(g[ny, nx] - seed_val) < tol:
                    visited[ny, nx] = True
                    q.append((ny, nx))
    full = np.asarray(Image.fromarray((visited * 255).astype("uint8")).resize((w, h), Image.NEAREST)) > 127
    return full


def erode(mask, r):
    m = mask.copy()
    for _ in range(r):
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
    return m


def panel_stats(ang, keep, box, min_px=80):
    x0, y0, x1, y1 = box
    a = ang[y0:y1, x0:x1]
    k = keep[y0:y1, x0:x1]
    n = int(k.sum())
    if n < min_px:
        return dict(n=n, mean=None, sd=None, note="too few patterned px")
    v = a[k]
    cc, ss = np.cos(np.radians(2 * v)).mean(), np.sin(np.radians(2 * v)).mean()
    mean = np.degrees(np.arctan2(ss, cc)) / 2
    R = np.hypot(cc, ss)
    sd = np.degrees(np.sqrt(max(-2 * np.log(max(R, 1e-9)), 0))) / 2
    return dict(n=n, mean=float(mean), sd=float(sd), note="")


def _hsv2rgb_vec(H, S, V):
    i = np.floor(H * 6.0); f = H * 6.0 - i
    p = V * (1 - S); q = V * (1 - f * S); t = V * (1 - (1 - f) * S)
    i = i.astype(int) % 6
    r = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [V, q, p, p, t, V])
    g = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [t, V, V, q, p, p])
    b = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [p, p, t, V, V, q])
    return np.stack([r, g, b], -1)


def run(img_path, rois_path, rgba_alpha=False, erode_px=0, energy_pctl=50, coh_thresh=0.3,
        out_prefix=None):
    img = Image.open(img_path)
    if rgba_alpha and img.mode == "RGBA":
        a = np.asarray(img)
        subject = a[..., 3] > 200
        rgb = a[..., :3]
    else:
        rgb = np.asarray(img.convert("RGB"))
        subject = ~bg_mask(rgb)
    if erode_px:
        subject = erode(subject, erode_px)
    gray = rgb.mean(-1)
    ang, coh, energy = orientation_and_energy(gray)
    if subject.sum() < 10:
        print("subject mask empty after erosion"); return {}
    e_floor = np.percentile(energy[subject], energy_pctl)
    keep = subject & (coh > coh_thresh) & (energy > e_floor)

    if out_prefix:
        H = (ang + 90) / 180.0
        col = _hsv2rgb_vec(H, np.ones_like(H), np.ones_like(H)) * 255
        base = rgb.astype(float) * 0.35
        base[keep] = col[keep]
        Image.fromarray(np.clip(base, 0, 255).astype("uint8")).save(out_prefix + "_overlay.png")

    rois = json.load(open(rois_path))
    print(f"{img_path.split('/')[-1]}  {rgb.shape[1]}x{rgb.shape[0]}  e_floor(p{energy_pctl})={e_floor:.4g}")
    print(f'  {"panel":16s} {"n px":>8s} {"mean angle":>11s} {"spread(sd)":>11s}')
    out = {}
    for name, box in rois.items():
        st = panel_stats(ang, keep, box)
        out[name] = st
        if st["mean"] is None:
            print(f"  {name:16s} {st['n']:8d}  -- {st['note']} --")
        else:
            flag = " <-LEAN" if abs(st["mean"]) > 4 else ""
            print(f"  {name:16s} {st['n']:8d} {st['mean']:+10.1f}° {st['sd']:10.1f}°{flag}")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(2)
    kw = dict(
        rgba_alpha="--rgba-alpha" in sys.argv,
        erode_px=int(sys.argv[sys.argv.index("--erode") + 1]) if "--erode" in sys.argv else 0,
        energy_pctl=float(sys.argv[sys.argv.index("--energy-pctl") + 1]) if "--energy-pctl" in sys.argv else 50,
        coh_thresh=float(sys.argv[sys.argv.index("--coh") + 1]) if "--coh" in sys.argv else 0.3,
        out_prefix=sys.argv[sys.argv.index("--viz") + 1] if "--viz" in sys.argv else None,
    )
    res = run(sys.argv[1], sys.argv[2], **kw)
    if "--out" in sys.argv:
        outp = sys.argv[sys.argv.index("--out") + 1]
        json.dump(res, open(outp, "w"), indent=2)
        print(f"wrote {outp}")
