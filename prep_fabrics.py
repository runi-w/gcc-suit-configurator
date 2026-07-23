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

SRC = "hires_swatches/2501-117"
OUT = "fabric_build"
TILE_CM = 8.0      # real cloth covered by one tile (fits the 10x7cm scan, keeps big checks whole)
TILE_PX = 384      # tile resolution (weave stays resolvable when the model render is large)
BLEND   = 0.22     # wrap-blend overlap fraction — kills the seam without mirroring
# Stripes/checks read louder on a small on-screen suit than on real cloth. Pull the LARGE-scale
# pattern contrast toward the cloth's mean while leaving weave detail untouched. 1.0 = as scanned.
PATTERN_CONTRAST = 0.68
PATTERN_SCALE_PX = 10        # blur radius separating "pattern" from "weave"
# Stripes run at 0.85 ("B", user-picked 2026-07-21 vs Suitsupply) — crisper lines than the
# 0.68 default, which stays for checks/solids.
CONTRAST_OVERRIDE = {'DBU080A': 0.85, 'DBT6860': 0.85, 'DBU081A': 0.85, 'DBS175A': 0.85}

# ---- PRESTIGE WOOL test fabrics (2026-07-21, one per pattern family) ----
# Source = KuteTailor's vendor swatches (GCC_Fabric_Handoff/prestige_swatches/, 1200x1200,
# no DPI metadata). VERIFIED these are the SAME captures as the 300-DPI flatbed scans, just
# resized: the Elite vendor image of DBU080A is pixel-identical cloth to hires_swatches'
# scan, stripe period 421px vendor vs 280px scan = x1.50 ≈ the resize. Cross-calibrated on
# 3 patterned Elite cloths -> implied ~172 px/cm (436.9 DPI). Scale chain intact, not guessed.
PRESTIGE_SRC = "/Users/runiwillner/Desktop/GCC_Fabric_Handoff/prestige_swatches"
PRESTIGE_DPI = 436.9
PRESTIGE_CODES = {"DBS175A", "DBQ791A", "DBS171A", "DBV120A", "DBP665A"}

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
    ("DBT6860",          "Navy Chalk Stripe"),      # names from Shopify (sku search), per the rule
    ("DBU081A",          "Charcoal Chalk Stripe"),
    # Prestige Wool test set — names from Shopify, per the rule ("Prestige" prefix added
    # to disambiguate from same-named Elite cloths in the test UI)
    ("DBS175A",          "Prestige Grey Chalk Stripe"),
    ("DBQ791A",          "Prestige Navy Fine Windowpane"),
    ("DBS171A",          "Prestige Grey Prince of Wales"),
    ("DBV120A",          "Prestige Grey Houndstooth"),
    ("DBP665A",          "Prestige Forest Green"),
]

# Vertical-stripe cloths get two source corrections (2026-07-21, user-flagged vs Suitsupply):
#   1. DESKEW — the scans lean up to 1.1 deg (cloth not square on the platen); that lean baked
#      into the tile is why our stripes leaned -2..-3.5 deg on the torso where SS holds +/-0.7.
#   2. PERIOD-SNAP the crop — the wrap-blend cross-fades a 22% band; when the tile width is not
#      an integer number of stripe periods the two edges are out of phase and a fifth of every
#      tile gets double-exposed ghost stripes. Snap the crop to whole periods.
#      ⚠ 2026-07-23: snapping the tile WIDTH is necessary but NOT sufficient -- the blend mixes
#      content (px - o) apart, which the width-snap does not make whole. seamless_wrap now takes
#      the period and snaps `o` too. Solids/checks are unaffected (weave has no phase).
STRIPE_CODES = {"DBU080A", "DBT6860", "DBU081A", "DBS175A"}
# DISPLAY LINE-WIDTH FLOOR (2026-07-21, from the Suitsupply pinstripe study). Measured on
# their production still: line contrast x4.3-5.0 (ours already x5.4+), but their lines are
# ~2x PHYSICAL width — a deliberate display idealisation, because a true-scale 1-1.5mm pin
# is sub-pixel at 10 px/cm and shimmers. Adopt the same: keep stripe PITCH at true scale
# (locked standard), widen only the LINE so it never drops below MIN_LINE_CANVAS_PX on the
# canvas. Applied to the tile's bright-line component only; ground cloth untouched.
MIN_LINE_CANVAS_PX = 2.2
PX_PER_CM_CANVAS   = 8.85    # garment-space px/cm in the builder (PX_PER_CM there)
OVERSAMPLE_BUILD   = 2       # must match the builder OVERSAMPLE

def widen_lines(tile, cm_per_tile, line_w_cm):
    """Widen bright stripe lines HORIZONTALLY to the display floor. Restricted to the
    line columns (weave untouched), x-only dilation (dashes keep their y-structure),
    additive only where the widening extends past the original line. No-op if wide enough."""
    line_w_canvas = line_w_cm * PX_PER_CM_CANVAS
    if line_w_canvas >= MIN_LINE_CANVAS_PX:
        return tile
    px_per_cm_tile = tile.width / cm_per_tile
    line_w_tile = line_w_cm * px_per_cm_tile
    k = int(round(line_w_tile * (MIN_LINE_CANVAS_PX / line_w_canvas - 1)))
    half = max(1, k // 2)
    a = np.asarray(tile, float)
    # 1D column profile finds the line columns
    prof = a.mean((0, 2))
    basep = np.convolve(np.pad(prof, 15, 'wrap'), np.ones(31)/31, 'same')[15:-15]
    ln = np.clip(prof - basep - 2, 0, None)
    if ln.max() <= 0:
        return tile
    colmask = ln > ln.max() * 0.25
    for s in range(1, half + 1):                       # dilate the column window
        colmask = colmask | np.roll(colmask, s) | np.roll(colmask, -s)
    # per-pixel bright-line component, horizontal base so vertical dash structure survives
    baseh = np.stack([np.apply_along_axis(
        lambda r: np.convolve(np.pad(r, 15, 'wrap'), np.ones(31)/31, 'same')[15:-15],
        1, a[..., c]) for c in range(3)], -1)
    comp = np.clip(a - baseh - 4, 0, None) * colmask[None, :, None]
    wide = comp.copy()
    for s in range(1, half + 1):                       # x-only dilation
        wide = np.maximum(wide, np.roll(comp, s, axis=1))
        wide = np.maximum(wide, np.roll(comp, -s, axis=1))
    return Image.fromarray(np.clip(a + np.clip(wide - comp, 0, None), 0, 255).astype('uint8'))

def _stripe_centers(prof):
    p = prof - np.convolve(prof, np.ones(61)/61, 'same')
    th = p.mean() + 1.2 * p.std()
    idx = np.where(p > th)[0]
    if not len(idx): return []
    return [g.mean() for g in np.split(idx, np.where(np.diff(idx) > 5)[0] + 1) if len(g) >= 2]

def stripe_angle(im):
    """dominant lean of the bright stripes, degrees from vertical (tracked centrelines)"""
    a = np.asarray(im.convert('L'), float); H = a.shape[0]
    nb = 8; bh = H // nb
    rows = [_stripe_centers(a[b*bh:(b+1)*bh].mean(0)) for b in range(nb)]
    angs = []
    for s0 in rows[0]:
        xs = [s0]
        for b in range(1, nb):
            c = [x for x in rows[b] if abs(x - xs[-1]) < 25]
            if not c: xs = None; break
            xs.append(min(c, key=lambda x: abs(x - xs[-1])))
        if not xs or len(xs) < nb: continue
        angs.append(np.degrees(np.arctan(np.polyfit(np.arange(nb)*bh + bh/2, xs, 1)[0])))
    return float(np.median(angs)) if angs else 0.0

def stripe_line_width(im):
    """median bright-line width in px on the deskewed scan"""
    prof = np.asarray(im.convert('L'), float).mean(0)
    p = prof - np.convolve(prof, np.ones(61)/61, 'same')
    th = p.mean() + 1.2 * p.std()
    idx = np.where(p > th)[0]
    if not len(idx): return 0.0
    groups = [g for g in np.split(idx, np.where(np.diff(idx) > 5)[0] + 1) if len(g) >= 2]
    return float(np.median([len(g) for g in groups])) if groups else 0.0

def stripe_period(im):
    """FULL motif repeat in px, on the deskewed scan. Autocorrelation of the column profile,
    HIGHEST peak (not first): chalk stripes often alternate strong/faint companions, and the
    centre-threshold spacing halves depending on which the detector catches — the full motif
    is the lag where the profile truly repeats, and only that keeps the wrap-blend edges on
    the SAME stripe type."""
    prof = np.asarray(im.convert('L'), float).mean(0)
    d = 61
    p = prof - np.convolve(prof, np.ones(d)/d, 'same')
    p = p[d:-d]
    ac = np.correlate(p, p, 'full')[len(p)-1:]
    ac /= ac[0] + 1e-9
    n = len(ac) // 2                              # need >= 2 repeats inside the scan
    peaks = [(ac[l], l) for l in range(30, n)
             if ac[l] > ac[l-1] and ac[l] > ac[l+1] and ac[l] > 0.25]
    return float(max(peaks)[1]) if peaks else 0.0

def tame_pattern(tile, amount=PATTERN_CONTRAST, radius=PATTERN_SCALE_PX):
    """Reduce large-scale stripe/check contrast, keep yarn-scale weave fully intact."""
    a = np.asarray(tile, float)
    coarse = np.asarray(tile.filter(ImageFilter.GaussianBlur(radius)), float)
    fine = a - coarse                       # weave detail — preserved exactly
    m = coarse.reshape(-1, 3).mean(0)
    coarse = m + (coarse - m) * amount      # pull the pattern toward the cloth's mean colour
    return Image.fromarray(np.clip(coarse + fine, 0, 255).astype('uint8'))

def load(code):
    code0 = code.split()[0]
    if code0 in PRESTIGE_CODES:
        p = os.path.join(PRESTIGE_SRC, code0 + ".jpg")
        if not os.path.exists(p): return None, None
        # vendor images carry no DPI metadata; scale is the cross-calibrated constant
        return Image.open(p).convert("RGB"), PRESTIGE_DPI
    p = os.path.join(SRC, code + ".JPG")
    if not os.path.exists(p): return None, None
    im = Image.open(p)
    dpi = im.info.get("dpi", (300, 300))[0] or 300
    return im.convert("RGB"), float(dpi)

def seamless_wrap(im, px, blend=BLEND, period=None):
    """Make a tile seamless by cross-fading opposite edges. No mirroring -> no chevron artefact.

    ⚠ THE HORIZONTAL BLEND MUST BE A WHOLE NUMBER OF PATTERN PERIODS (2026-07-23).
    The cross-fade mixes column px-o+i with column i, i.e. it blends content that is (px-o)
    apart. For a stripe that is only in phase when (px-o) is a whole number of periods. The
    period-snap below snaps the tile WIDTH to whole periods, which does NOT make (px-o) whole
    -- and the old fixed o = 0.22*px left DBT6860 at px-o = 300 against a 192px period = 1.56
    periods, i.e. near ANTI-phase: every second stripe got a dark band cross-faded onto it.
    Measured: the raw 300 DPI scan's three stripes are uniform (amplitudes 89.4 / 94.9 / 95.1,
    min/max 0.94) but the shipped tile read 111.6 / 66.4 (min/max 0.595). That "strong/weak
    companion stripe" was never in the cloth -- it was this blend.
    Passing `period` snaps o to the nearest whole number of periods (>=1), so the blend mixes
    stripe onto stripe at identical phase: amplitude is preserved and only the weave cross-fades.
    The VERTICAL blend needs no such treatment -- vertical stripes have no phase along y.
    """
    a = np.asarray(im.resize((px, px), Image.LANCZOS), float)
    o = max(2, int(px * blend))
    if period and period > 2:
        o = int(max(1, round(o / period)) * round(period))
        o = min(o, px // 2)
    r = np.linspace(0, 1, o)[None, :, None]                 # horizontal ramp
    a[:, px-o:px] = a[:, px-o:px] * (1 - r) + a[:, 0:o] * r  # right edge -> left edge
    ov = max(2, int(px * blend))
    r = np.linspace(0, 1, ov)[:, None, None]                # vertical ramp
    a[px-ov:px, :] = a[px-ov:px, :] * (1 - r) + a[0:ov, :] * r  # bottom edge -> top edge
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
    code0 = code.split()[0]
    per_src = None                       # stripe period in SOURCE px, for the in-phase blend
    if code0 in STRIPE_CODES:
        ang = stripe_angle(im)
        if abs(ang) > 0.05:
            im = im.rotate(-ang, Image.BICUBIC)             # empirically verified: -ang zeroes the lean
            marg = int(math.ceil(math.tan(math.radians(abs(ang))) * max(im.size))) + 2
            im = im.crop((marg, marg, im.width - marg, im.height - marg))
        per = stripe_period(im)
        crop_px = min(crop_px, min(im.size))
        if per > 20:                                        # snap to whole stripe periods
            crop_px = max(1, int(crop_px / per)) * int(round(per))
            crop_px = min(crop_px, min(im.size))
            per_src = per
        print(f"  {code0}: deskew {ang:+.2f} deg, period {per:.1f}px, tile {crop_px}px = {crop_px/pxcm:.2f}cm")
    crop_px = min(crop_px, min(im.size))                    # stay inside the scan
    cm_per_tile = crop_px / pxcm
    cx, cy = im.width // 2, im.height // 2
    sq = im.crop((cx-crop_px//2, cy-crop_px//2, cx+crop_px//2, cy+crop_px//2))
    # period in TILE px after the resize to TILE_PX (the crop is a whole number of periods)
    per_tile = (per_src * TILE_PX / crop_px) if per_src else None
    tile = tame_pattern(seamless_wrap(sq, TILE_PX, period=per_tile),
                        amount=CONTRAST_OVERRIDE.get(code0, PATTERN_CONTRAST))
    if code0 in STRIPE_CODES:
        # The floor only helps thin lines on wide pitch. Verified 2026-07-21: DBT6860
        # (0.6px line / 27px pitch) lands the SS look; but lines already >=1px wide get
        # overdriven into awning stripes (DBU081A), and pitches under ~10 canvas px can't
        # hold a 2.2px line at all — they merge into bands (DBS175A). Those stay true-scale.
        lw_cm = stripe_line_width(im) / pxcm
        lw_px = lw_cm * PX_PER_CM_CANVAS
        pitch_px = (per / pxcm) * PX_PER_CM_CANVAS if per > 0 else 0
        if lw_cm > 0 and lw_px < 1.0 and pitch_px > 10:
            tile = widen_lines(tile, cm_per_tile, lw_cm)
            print(f"  {code0}: line {lw_cm*10:.1f}mm = {lw_px:.1f}px canvas, pitch {pitch_px:.0f}px -> floored to {MIN_LINE_CANVAS_PX}")
        else:
            print(f"  {code0}: line {lw_cm*10:.1f}mm = {lw_px:.1f}px canvas, pitch {pitch_px:.0f}px -> true scale (no floor)")

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

# ---- second pass: normalise against ABSOLUTE anchors, then bake micro-normals ----
# Frozen 2026-07-21 from the original 10-fabric batch (weave 9.32-61.04, pattern median
# 0.75 x 1.25). Per-batch normalisation meant ADDING a fabric shifted every existing
# sheen/relief value — the documented blocker for the 117 batch (HANDOVER §6.5). With the
# anchors frozen, params are a pure function of the cloth. Clamped, so an outlier cloth
# outside the anchored range saturates instead of stretching everyone else.
WEAVE_LO, WEAVE_HI = 9.32, 61.04
PAT_THRESH = 0.9375
wlo, whi = WEAVE_LO, WEAVE_HI
norm = lambda v, lo, hi: min(1.0, max(0.0, (v - lo) / (hi - lo)))

print(f"\nweave anchors {wlo:.1f}–{whi:.1f} (frozen) | pattern threshold {PAT_THRESH:.2f} (frozen)\n")
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
