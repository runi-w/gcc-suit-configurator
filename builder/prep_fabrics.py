#!/usr/bin/env python3
"""Fabric prep for the configurator — items 2,3,4,6,7.

From the 300-DPI Elite Wool scans produce, per fabric:
  • a SEAMLESS tile with NO mirror symmetry (wrap-blend, not 4-way mirror)   [item 3]
  • exact real-world scale, cmPerTile, straight from the DPI metadata        [item 2]
  • a weave MICRO-NORMAL map derived from the swatch itself                  [item 7]
  • material params: sheen strength + micro relief, auto-derived per cloth   [item 4]
  • measured mean colour / Lab for a colour sanity report                    [item 6]
"""
import os, json, math, glob
import numpy as np
from PIL import Image, ImageFilter

HM  = "/Users/runiwillner/Desktop/GCC_House_Model"
SRC = f"{HM}/hires_swatches/2501-117"
OUT = f"{HM}/fabric_build"
TILE_CM = 8.0      # real cloth covered by one tile (fits the 10x7cm scan, keeps big checks whole)
TILE_PX = 384      # tile resolution (weave stays resolvable when the model render is large)
BLEND   = 0.22     # wrap-blend overlap fraction — kills the seam without mirroring
# Stripes/checks read louder on a small on-screen suit than on real cloth. Pull the LARGE-scale
# pattern contrast toward the cloth's mean while leaving weave detail untouched. 1.0 = as scanned.
PATTERN_CONTRAST = 0.68
PATTERN_SCALE_PX = 10        # blur radius separating "pattern" from "weave"

# real Elite Wool names, taken from the Shopify products (not guessed from colour)
FABRICS = [
    ("DBS131A",          "Navy Herringbone"),
    ("DBP677A",          "Midnight Herringbone"),
    ("DBV305A",          "Navy Houndstooth"),
    ("DEE1020 DBN802A",  "Deep Navy"),
    ("DBT572A",          "Jet Black"),
    ("DBV196A",          "Silver Glen Check"),
    ("DBU080A",          "Grey Chalk Stripe"),
    ("DBS137A",          "Grey Glen Check"),
    ("DBS139A",          "Navy Prince of Wales"),
    ("DEE1017 DBN317A",  "Charcoal Windowpane"),
]

def tame_pattern(tile, amount=PATTERN_CONTRAST, radius=PATTERN_SCALE_PX):
    """Reduce large-scale stripe/check contrast, keep yarn-scale weave fully intact."""
    a = np.asarray(tile, float)
    coarse = np.asarray(tile.filter(ImageFilter.GaussianBlur(radius)), float)
    fine = a - coarse                       # weave detail — preserved exactly
    m = coarse.reshape(-1, 3).mean(0)
    coarse = m + (coarse - m) * amount      # pull the pattern toward the cloth's mean colour
    return Image.fromarray(np.clip(coarse + fine, 0, 255).astype('uint8'))

def load(code):
    p = os.path.join(SRC, code + ".JPG")
    if not os.path.exists(p): return None, None
    im = Image.open(p)
    dpi = im.info.get("dpi", (300, 300))[0] or 300
    return im.convert("RGB"), float(dpi)

def seamless_wrap(im, px, blend=BLEND):
    """Make a tile seamless by cross-fading opposite edges. No mirroring -> no chevron artefact."""
    a = np.asarray(im.resize((px, px), Image.LANCZOS), float)
    o = max(2, int(px * blend))
    r = np.linspace(0, 1, o)[None, :, None]                 # horizontal ramp
    a[:, px-o:px] = a[:, px-o:px] * (1 - r) + a[:, 0:o] * r  # right edge -> left edge
    r = np.linspace(0, 1, o)[:, None, None]                 # vertical ramp
    a[px-o:px, :] = a[px-o:px, :] * (1 - r) + a[0:o, :] * r  # bottom edge -> top edge
    return Image.fromarray(np.clip(a, 0, 255).astype('uint8'))

def micro_normal(tile, strength):
    """Weave-scale normal map from the swatch's own luminance (Diffuse->Height->Normal)."""
    L = np.asarray(tile.convert("L"), float)
    lo = np.asarray(tile.convert("L").filter(ImageFilter.GaussianBlur(6)), float)
    h = L - lo                                    # high-pass = weave only, drops the check pattern
    h = h / (np.abs(h).max() + 1e-6)
    gx = np.roll(h, -1, 1) - np.roll(h, 1, 1)     # wrap-aware gradients keep the map tileable
    gy = np.roll(h, -1, 0) - np.roll(h, 1, 0)
    nx, ny, nz = -gx * strength, -gy * strength, np.ones_like(h)
    ln = np.sqrt(nx*nx + ny*ny + nz*nz)
    rgb = np.stack([(nx/ln*0.5+0.5), (ny/ln*0.5+0.5), (nz/ln*0.5+0.5)], -1) * 255
    return Image.fromarray(np.clip(rgb, 0, 255).astype('uint8'))

def srgb_to_lab(rgb):
    c = np.array(rgb, float) / 255.0
    c = np.where(c <= .04045, c/12.92, ((c+.055)/1.055)**2.4)
    M = np.array([[.4124,.3576,.1805],[.2126,.7152,.0722],[.0193,.1192,.9505]])
    xyz = M @ c / np.array([.95047, 1.0, 1.08883])
    f = np.where(xyz > .008856, xyz**(1/3), 7.787*xyz + 16/116)
    return [116*f[1]-16, 500*(f[0]-f[1]), 200*(f[1]-f[2])]

os.makedirs(OUT, exist_ok=True)
report = []
for code, name in FABRICS:
    im, dpi = load(code)
    if im is None:
        print(f"  !! missing {code}"); continue
    pxcm = dpi / 2.54
    crop_px = int(round(TILE_CM * pxcm))
    crop_px = min(crop_px, min(im.size))                    # stay inside the scan
    cm_per_tile = crop_px / pxcm
    cx, cy = im.width // 2, im.height // 2
    sq = im.crop((cx-crop_px//2, cy-crop_px//2, cx+crop_px//2, cy+crop_px//2))
    tile = tame_pattern(seamless_wrap(sq, TILE_PX))

    # --- material params derived from the cloth itself (weave and pattern measured at DIFFERENT scales) ---
    Lm = np.asarray(tile.convert("L"), float)
    fine = np.asarray(tile.convert("L").filter(ImageFilter.GaussianBlur(2.5)), float)
    coarse = np.asarray(tile.convert("L").filter(ImageFilter.GaussianBlur(16)), float)
    weave = float((Lm - fine).std())      # yarn-scale contrast only
    pattern = float(coarse.std())         # check / stripe energy only
    mean_rgb = [float(x) for x in np.asarray(tile, float).reshape(-1,3).mean(0)]
    lab = srgb_to_lab(mean_rgb)

    tile.save(f"{OUT}/tile_{code.split()[0]}.jpg", "JPEG", quality=92, optimize=True)
    report.append(dict(code=code.split()[0], file=code, name=name, dpi=dpi, pxPerCm=round(pxcm,2),
                       cmPerTile=round(cm_per_tile,2), tilePx=TILE_PX, weave=round(weave,2),
                       pattern=round(pattern,2),
                       # flat sheen tint = LINEAR luminance of the cloth's mean colour (Filament's
                       # recipe). Using per-pixel luminance instead would amplify stripes/checks.
                       meanLum=round(float(sum(w * ((c/255)/12.92 if c/255 <= .04045 else (((c/255)+.055)/1.055)**2.4)
                                     for w, c in zip((.2126, .7152, .0722), mean_rgb))), 4),
                       rgb=[round(v) for v in mean_rgb], lab=[round(v,1) for v in lab]))

# ---- second pass: normalise across the actual observed range, then bake micro-normals ----
wv = np.array([r["weave"] for r in report]); pt = np.array([r["pattern"] for r in report])
wlo, whi = float(wv.min()), float(wv.max())
norm = lambda v, lo, hi: 0.0 if hi <= lo else (v - lo) / (hi - lo)
PAT_THRESH = float(np.median(pt)) * 1.25   # data-driven, not a guessed constant

print(f"\nweave range {wlo:.1f}–{whi:.1f} | pattern median {np.median(pt):.2f} -> threshold {PAT_THRESH:.2f}\n")
print(f"{'code':9} {'name':22} {'cm/tile':>8} {'weave':>6} {'patt':>6} {'sheen':>6} {'relief':>7}  kind")
for r in report:
    t = norm(r["weave"], wlo, whi)
    r["sheen"]  = round(0.10 + 0.16 * t, 3)   # crisper worsted -> more sheen; fuzzy flannel -> less
    r["relief"] = round(0.70 + 1.30 * t, 2)   # weave relief strength
    r["kind"]   = "pattern" if r["pattern"] > PAT_THRESH else "solid"
    tile = Image.open(f"{OUT}/tile_{r['code']}.jpg").convert("RGB")
    micro_normal(tile, r["relief"]).save(f"{OUT}/norm_{r['code']}.jpg", "JPEG", quality=88, optimize=True)
    print(f"{r['code']:9} {r['name']:22} {r['cmPerTile']:>7.1f}  {r['weave']:>6.1f} {r['pattern']:>6.2f} "
          f"{r['sheen']:>6.3f} {r['relief']:>7.2f}  {r['kind']}")

json.dump(report, open(f"{OUT}/fabrics.json", "w"), indent=1)
print(f"\nwrote {len(report)} fabrics -> {OUT}/fabrics.json  (tile {TILE_PX}px = {TILE_CM}cm real cloth)")
print("colour check (item 6) — measured Lab, evenly-lit scans so as-shot should be trustworthy:")
for r in report:
    print(f"   {r['code']:9} {r['name']:22} rgb={tuple(r['rgb'])} L*={r['lab'][0]:.0f} a*={r['lab'][1]:+.1f} b*={r['lab'][2]:+.1f}")
