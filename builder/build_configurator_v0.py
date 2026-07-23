#!/usr/bin/env python3
"""Gage Court — Suit Configurator v0. Guided picker in front of the normal-warp compositor.
Fabric + Style + Lapel drive the live preview; buttons/lining/pockets/monogram feed the KuteTailor
order spec + indicative price. Self-contained (data-URIs). Reuses the validated compositor."""
import base64, io, json, os
from PIL import Image

HM = "/Users/runiwillner/Desktop/GCC_House_Model"
ROOT = "/Users/runiwillner/Desktop/GCC_Fabric_Handoff"
CFG = f"{HM}/config"
OUT = f"{HM}/configurator-v0.html"
AN = f"{HM}/fabric_analysis.json"   # legacy, unused by the current fabric pipeline
# Render width. Source renders/maps are 1792x2400, so anything up to 1792 is real detail.
# Audit 2026-07-21: at W=700 the model showed cloth at 4.75 device px/cm vs Suitsupply's
# ~10.3 — the single largest perceptual gap, and it was a display-size choice, not an
# asset-quality one. NOTE: every px-scale constant below is expressed via RSCALE so the
# locked look (playbook, tuned at W=700) survives the resolution change.
W = 1300
BASE_W = 700.0          # the width every px-tuned constant was calibrated at
RSCALE = W / BASE_W
# Fraction of the frame kept, from the top. 1.0 = the full figure including shoes, which
# is what the approved right-rail design calls for. (Suitsupply crop to 0.7 to buy cloth
# density on a short stage; the right rail gives the stage the height instead.)
CROP_FRAC = 1.0

CUTS = [
    ("notch", "front_2button_notch", True), ("peak", "front_2button_peak", True),
    ("one", "front_1button_peak", True), ("db", "front_doublebreasted", False),
    ("three", "front_3piece_vest", False),
]
# Fabrics come from prep_fabrics.py (real Elite Wool scans, 300 DPI -> true cm scale).
FAB_DIR = f"{HM}/fabric_build"
# PATTERN WARP AMPLITUDE, in units of the original 6-at-BASE_W tuning. 0 = the cloth pattern is
# RULED STRAIGHT per panel (Path A's per-panel rotation still applies).
#
# ⚠ Set to 0 on 2026-07-23 after measuring what this term actually does. It is NOT a drape term:
# the garment's whole three-dimensionality — folds, creases, shading, sheen — comes from the
# drape map overlay and the additive sheen pass, both independent of dispX/dispY. This term only
# moves WHERE THE TILE IS SAMPLED, and it was doing that badly:
#   - Displacement reached 12.07 canvas px against a 26.6 px chalk-stripe pitch — up to 45% of a
#     whole stripe period, varying across the garment. That is the visible stripe wander.
#   - It DILATED the pattern: measured stripe spacing 29.32 px median (+9.6%) with it on, against
#     a nominal 26.75 px, spread 22.3..32.1. It was silently breaking the 0.99x true-scale
#     calibration that PX_PER_CM/FIGURE_FRAC exist to guarantee.
#   - Scored against a cylinder-foreshortening ideal it was WORSE THAN A FLAT PATTERN on 24 of 24
#     panel-cases across 6 cut-views, and it EXPANDED where foreshortening must compress on 86.6%
#     of torso pixels. It is derived from a LIGHTING-derived Marigold normal, so it correlates
#     with where the cloth catches light, not with how the cloth curves — wrong quantity, and on
#     the torso the wrong sign.
# The only thing lost is that matched-estimator torso swing goes to 0 deg where Suitsupply's
# photographic reference measures 2.8 deg. That statistic was being matched by the wrong
# mechanism; judged by eye on chalk stripe and glen check, front and back, ruled-straight wins.
# Solids are unaffected either way (8 of 17 cloths show no measurable change at any amplitude).
WARP_AMP_MULT = 0.0
SIL_WRAP   = 0.00       # silhouette-relative pattern wrap. VALIDATED on the torso: at 0.70 the
                        # four central bands order correctly (-7.2 -4.5 -0.2 +3.7) where before they
                        # were noise. DISABLED because hw[y] spans the whole row, so the SLEEVES --
                        # separate tubes, no background gap between arm and body in this pose -- get
                        # sheared as if they were the torso, breaking the outer bands and adding 5deg
                        # of wobble. Needs per-panel centre/width (torso vs each sleeve) before it
                        # can be enabled. Target: swing 22.7deg, spread 16.7deg, monotonic.
FOOTPRINT  = 0.55       # runtime filter width, in OVERSAMPLE texels. The tile is already
                        # LANCZOS-prefiltered at bake time; a full-width (1.0) runtime box filters
                        # it TWICE and cost 29% of the cloth's sharpness. 0.55 recovers it to 95%
                        # of the true cloth measured at our px/cm, with no moire. Verified DBV196A.
                        # already LANCZOS-prefiltered at bake time, so a full-width runtime
                        # box filters it TWICE and costs sharpness. See notes at OVERSAMPLE.
OVERSAMPLE = 2          # tile baked at this multiple of on-screen size; PAT_DENSITY is emitted
                        # from it. samples/texel = SS/OVERSAMPLE; at 4 it was 0.75 (below Nyquist)
                        # and fine checks aliased into heavy moire. See FOOTPRINT above.
                        # steps this many texels per pixel (PAT_DENSITY is emitted from it).
                        # With SS=3 that is 3/OVERSAMPLE samples per texel. At 4 it was 0.75 --
                        # far below Nyquist -- and fine checks aliased into heavy moire across
                        # the sleeves and legs. 2 gives 1.5 and is visually clean; 1 gives 3.0
                        # but visibly softens the cloth. Verified on DBV196A/DBS137A 2026-07-21.
FIGURE_CM = 183.0       # model height, for px-per-cm on the render
FIGURE_FRAC = 0.93      # fraction of frame height the figure occupies

_MIME = {"JPEG": "jpeg", "PNG": "png", "WEBP": "webp"}

def datauri(img, fmt, **kw):
    b = io.BytesIO(); img.save(b, fmt, **kw)
    return f"data:image/{_MIME[fmt]};base64," + base64.b64encode(b.getvalue()).decode()

def file_datauri(path, box=120):
    if not path or not os.path.exists(path): return None
    im = Image.open(path).convert("RGB"); im.thumbnail((box, box), Image.LANCZOS)
    return datauri(im, "JPEG", quality=84, optimize=True)

def seamless_tile(path, size=132):
    im = Image.open(path).convert("RGB"); s = int(min(im.size) * 0.52)
    cx, cy = im.width // 2, im.height // 2
    c = im.crop((cx - s//2, cy - s//2, cx + s//2, cy + s//2)).resize((size//2, size//2), Image.LANCZOS)
    n = size//2; t = Image.new("RGB", (size, size))
    t.paste(c, (0, 0)); t.paste(c.transpose(Image.FLIP_LEFT_RIGHT), (n, 0))
    t.paste(c.transpose(Image.FLIP_TOP_BOTTOM), (0, n))
    t.paste(c.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.FLIP_TOP_BOTTOM), (n, n))
    return t

import numpy as _np
from PIL import ImageFilter as _IF
import sys as _sys
_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panels import segment, anchors, N_PANELS, PANEL_ANGLES   # Path A per-panel grain
# Match Suitsupply's measured shading statistics (navy jacket body layer, 2026-07-21):
#   broad-shading std 0.049, fold-band std 0.042, fold/broad ratio 0.86 -> a pressed,
#   softly-lit suit. Our raw drape map measured 0.092/0.111 (2.6x harsher folds).
DRAPE_BROAD_K = 0.75   # compress broad body shading
DRAPE_FOLD_K  = 0.55   # compress fold shadows (the big one)
DRAPE_FINE_K  = 0.80   # keep fine cloth detail
DRAPE_SOFT_PX = 1.5    # soften fold edges like a pressed garment (at BASE_W; scaled by RSCALE)
# Suitsupply keeps STRUCTURAL creases near-black and crisp (lapel edge, cavity, under-flap
# measured 0.001-0.03 L) while fold shading stays soft. Preserve any original dark below
# STRUCT_T; allow it to lift at most STRUCT_LIFT.
STRUCT_T    = 90
STRUCT_LIFT = 12
# Exposure anchor for the softened drape (audit 2026-07-21). Canvas 'overlay' blends in
# sRGB, so the drape's masked median is an exposure term with ~2.2 gamma leverage on the
# final linear luminance — a 1.44x drape gain lands as ~2.2x on screen. 128 ("overlay
# neutral") therefore OVERSHOOTS. Calibrated against the mill scans so the rendered
# garment's median linear luminance matches the cloth's (Suitsupply measures 105% on the
# same statistic). Was landing at 89 unnormalised => 70% of the cloth, i.e. visibly dark.
DRAPE_TARGET_MED = 111.4
# STRUCTURAL CREASE RESTORE (2026-07-21, crease-depth fix). The composite's crease depth
# measured p1/med 0.25-0.27 vs Suitsupply's 0.031 — but the RENDER measures 0.060 and the
# raw drape file 0.045: the depth exists and is destroyed HERE (the K-compression toward
# 128, the exposure gain and the final blur together lift the deep tail ~3x, and the
# overlay pass doubles it again). So after the locked pipeline runs, restore the deep tail
# from the ORIGINAL drape: where the raw L is below CREASE_T, pull the output down toward
# l*CREASE_K. Feathered over CREASE_F levels; collar-eased like the deepen (user rule).
# This touches only px the raw drape already marks as structural creases (p1..p5 zone,
# l<~46 at median 89) — folds live at l~71 and are untouched, so the locked BROAD_K/FOLD_K
# look is preserved. NOT the STRUCT_T gate the 2026-07-21 note warns about: that proposal
# REPLACED the ungated deepen (which is load-bearing for fold compression); this ADDS a
# tail-only restore after it.
CREASE_T = 58     # raw-drape level below which restore engages (creases ~17, shadow p5 ~39,
CREASE_F = 18     # folds ~71 stay above it); feathered over CREASE_F levels
CREASE_K = 0.32   # restored depth = min(current, l*CREASE_K + CREASE_B) — deeper than raw
CREASE_B = 0.5

def soften_drape(L_img, mask=None):
    # blur radii are in px and were tuned at BASE_W -> scale with the render width,
    # otherwise raising W quietly weakens the softening and the locked drape look drifts.
    l   = _np.asarray(L_img, float)
    lo  = _np.asarray(L_img.filter(_IF.GaussianBlur(40 * RSCALE)), float)
    mid = _np.asarray(L_img.filter(_IF.GaussianBlur(6 * RSCALE)), float)
    out = 128 + (lo - 128) * DRAPE_BROAD_K + (mid - lo) * DRAPE_FOLD_K + (l - mid) * DRAPE_FINE_K
    # SS creases are near-black: deepen — but EASE OFF around the collar/neck zone,
    # where the deepened shadow reads too heavy (user 2026-07-21).
    h, w = l.shape
    yy, xx = _np.mgrid[0:h, 0:w]
    cz = (_np.clip(1 - _np.abs(xx / w - 0.5) / 0.16, 0, 1)      # centre band
          * _np.clip(1 - _np.abs(yy / h - 0.115) / 0.10, 0, 1)) # collar height
    strength = 1.0 - 0.75 * cz                                   # 1 elsewhere, 0.25 at collar core
    deepened = _np.minimum(out, l * 0.65 + 4)
    out = out + (deepened - out) * strength

    # EXPOSURE NORMALISATION (audit 2026-07-21). The drape's masked median is an exposure
    # term: unnormalised it landed at 89, rendering every fabric at ~70% of the cloth's
    # linear luminance (dL* -3.9..-11.1 vs the mill scans). The deepen step above is what
    # pulls it down — but it is also what compresses fold contrast, and the locked
    # BROAD_K/FOLD_K were tuned with it in place. So correct EXPOSURE only and leave the
    # approved contrast untouched. A MULTIPLICATIVE gain is the right form for a shading
    # term: it pins black at black, so structural creases keep their depth.
    if mask is not None:
        med = _np.median(out[mask])
        if med > 1:
            out = out * (DRAPE_TARGET_MED / med)
    im = Image.fromarray(_np.clip(out, 0, 255).astype('uint8'))
    im = im.filter(_IF.GaussianBlur(DRAPE_SOFT_PX * RSCALE))
    # structural crease restore — AFTER the softening blur so the restored creases stay
    # crisp (SS creases are "near-black and CRISP"); the feather supplies the antialiasing.
    base = _np.asarray(im, float)
    w = _np.clip((CREASE_T - l) / CREASE_F, 0, 1) * strength
    deep = _np.minimum(base, l * CREASE_K + CREASE_B)
    return Image.fromarray(_np.clip(base + (deep - base) * w, 0, 255).astype('uint8'))

# The renders are shot on a near-white sweep (~246.6, std ~1). The approved design puts the
# model on the cream stage, so a white plate would read as a hard box. Recolour the SWEEP
# ONLY — keep the figure and the floor shadow, which is what makes the model sit on a floor
# rather than float. Connectivity comes from a low-res flood fill (so enclosed white — the
# shirt, the pocket square — is never touched); the crisp edge comes from a full-res test.
from PIL import ImageDraw as _ID
STAGE_RGB = (245, 242, 236)          # must equal --stage in the CSS; injected below

def on_stage(im):
    a = _np.asarray(im.convert("RGB")).astype(_np.float32)
    mx, mn = a.max(-1), a.min(-1)
    sat = (mx - mn) / _np.maximum(mx, 1e-6)
    lum = a.mean(-1)
    near = (lum > 218) & (sat < 0.10)                  # sweep + its shadow, not the suit/skin
    h, w = near.shape
    # --- connectivity on a proxy, so we only take sweep that reaches the frame edge ---
    sw = 448; sh = max(1, int(h * sw / w))
    small = Image.fromarray((near * 255).astype("uint8")).resize((sw, sh), Image.NEAREST)
    _ID.floodfill(small, (0, 0), 128, thresh=0)
    for seed in ((sw - 1, 0), (0, sh - 1), (sw - 1, sh - 1), (sw // 2, 0)):
        if small.getpixel(seed) == 255:
            _ID.floodfill(small, seed, 128, thresh=0)
    reach = Image.fromarray(((_np.asarray(small) == 128) * 255).astype("uint8"))
    reach = reach.filter(_IF.MaxFilter(3)).resize((w, h), Image.BILINEAR)
    bg = near & (_np.asarray(reach).astype(_np.float32) > 110)
    # --- feather, then map the sweep onto the stage colour MULTIPLICATIVELY so the
    #     floor shadow keeps its gradient instead of flattening to a flat fill ---
    soft = _np.asarray(Image.fromarray((bg * 255).astype("uint8"))
                       .filter(_IF.GaussianBlur(1.0)), _np.float32)[..., None] / 255.0
    ratio = _np.array(STAGE_RGB, _np.float32) / 246.6
    out = a * (1.0 - soft) + _np.clip(a * ratio, 0, 255) * soft
    return Image.fromarray(_np.clip(out, 0, 255).astype("uint8"))

cuts = []; H = None; H_FULL = None

def _fit(im):
    """resize to the full frame, then crop to the top CROP_FRAC — all four layers
    must be cropped identically or the composite tears."""
    return im.resize((W, H_FULL), Image.LANCZOS).crop((0, 0, W, H))

# cut x VIEW. Each cut's front filename is front_<base>; side/back share the base with a
# swapped prefix. A view is embedded only when all three assets exist, so the build works
# incrementally while sides/backs are still being generated. id = "<cut>__<view>".
VIEWS = ["front", "side", "back"]
cutviews = {}
for cid, fn, openf in CUTS:
    for view in VIEWS:
        vfn = fn.replace("front_", view + "_", 1)
        rp, dpth, npth = (f"{HM}/renders/{vfn}.png", f"{HM}/drape_maps/{vfn}_drape.png",
                          f"{HM}/drape_maps/{vfn}_normal.png")
        if not (os.path.exists(rp) and os.path.exists(dpth) and os.path.exists(npth)):
            continue
        la = Image.open(dpth)
        if H is None:
            H_FULL = int(W * la.height / la.width)
            H = int(H_FULL * CROP_FRAC)
            # px/cm is a property of the FULL frame's geometry (FIGURE_FRAC is measured against
            # it), so it must come from H_FULL — cropping moves the viewport, not the model's
            # scale. Needed here, not just below, because the panel segmentation measures the
            # garment in cm.
            PX_PER_CM = (FIGURE_FRAC * H_FULL) / FIGURE_CM
        L, A = la.split()
        ub = datauri(_fit(on_stage(Image.open(rp))), "JPEG", quality=82, optimize=True)
        # the garment mask gates the exposure normalisation (hard threshold, per the standing rule)
        _m = _np.asarray(_fit(A).convert("L")) > 200
        # q90: at q86 JPEG's near-black quantisation lifted the restored crease tail from
        # p1/med 0.13 to 0.19 — the crease-depth fix is only as good as what survives encoding
        ud = datauri(soften_drape(_fit(L).convert("L"), _m), "JPEG", quality=90, optimize=True)
        um = datauri(_fit(A).convert("L"), "PNG", optimize=True)
        # normal maps stay LOSSLESS — lossy codecs corrupt the vectors (JPEG q95 and WebP q95
        # both measured up to ~18-20 deg of angular error). WebP lossless is bit-exact
        # (0.000 deg, verified 2026-07-21) and ~27% smaller than PNG.
        # ...but they do NOT need full RESOLUTION, which is a different question from codec
        # fidelity and was costing 64% of the deliverable (482 KB x 15 = 7.1 MB). The compositor
        # consumes this map in exactly two ways, both of which discard high frequencies: dispX/
        # dispY, which is box-blurred at NSMOOTH (22 px here) and capped at WARP_CAP; and graze,
        # a broad grazing-angle term for the sheen. Measured at half scale (2026-07-23, on front/
        # side/back): displacement error p95 0.05-0.12 px and MAX 0.30 px against a 12 px cap,
        # graze error p95 <0.01 — sub-pixel, for 2.8x fewer bytes. No JS change needed either:
        # buildWarpNormal already does drawImage(nimg,0,0,W,H), so the browser upsamples it.
        NORMAL_SCALE = 0.5
        _n = _fit(Image.open(npth).convert("RGB"))
        _n = _n.resize((max(1, round(_n.width * NORMAL_SCALE)),
                        max(1, round(_n.height * NORMAL_SCALE))), Image.LANCZOS)
        un = datauri(_n, "WEBP", lossless=True, quality=100)
        # PATH A — per-panel grain (plan/PATH_A_GRAIN_SPEC.md). Segment the garment into its
        # tailoring panels here, where the render's own pixels are available and the result can
        # be rendered as an overlay and looked at (builder/panels.py's __main__ writes the QA
        # sheet). The map rides along as a 9-value greyscale PNG — flat regions, so all 15
        # cut-views together cost ~128 KB base64, ~1% of the deliverable.
        pmap, plm = segment(_fit(Image.open(rp).convert("RGB")), _fit(A).convert("L"),
                            view, PX_PER_CM)
        anc = anchors(pmap, plm)
        up = datauri(Image.fromarray(pmap), "PNG", optimize=True)
        # openFront (front-opening seam/lapel break) is a FRONT-view property only
        cuts.append({"id": f"{cid}__{view}", "base": ub, "drape": ud, "mask": um, "normal": un,
                     "panel": up,
                     "anchor": [[round(anc.get(p, (0, 0))[0], 1), round(anc.get(p, (0, 0))[1], 1)]
                                for p in range(N_PANELS)],
                     "openFront": bool(openf and view == "front")})
        cutviews.setdefault(cid, []).append(view)
print("  cut-views embedded: " + ", ".join(f"{k}[{'/'.join(v)}]" for k, v in cutviews.items()))

# PX_PER_CM is set in the cut-view loop above, as soon as H_FULL is known (the segmentation
# needs it there). See the comment at that assignment for why it derives from H_FULL.
FABMETA = json.load(open(f"{FAB_DIR}/fabrics.json"))
# Per-fabric BAKED STILLS — the Suitsupply fabric-step architecture (2026-07-21): at the
# fabric step the stage shows the fabric's approved catalog image (one gorgeous per-fabric
# bake) instead of the live composite; the compositor stays for the Style steps. URLs are
# the Shopify-CDN catalog images (hotlinked deliberately: the page ships ON Shopify, and
# data-URI-ing ~350KB x N stills would bloat the deliverable).
# TEST ROLLOUT: one pinstripe. Add codes here to extend; back view enables automatically.
# TEST RESULT (2026-07-21): the catalog still is a DIFFERENT model/pose than the house
# model the compositor draws, so switching Fabric->Style swapped the man — user rejected it
# ("it changes the whole model"). Disabled. The code path stays (works); re-enable only once
# fabric stills are baked on the HOUSE model so the transition is seamless.
STILLS = {
    # "DBT6860": {"front": "...", "back": "..."},   # disabled — model-swap, see note above
}

fabs = []
for m in FABMETA:
    tp = os.path.join(FAB_DIR, f"tile_{m['code']}.jpg")
    npth = os.path.join(FAB_DIR, f"norm_{m['code']}.jpg")
    if not os.path.exists(tp):
        continue
    # TRUE SCALE: bake the tile at OVERSAMPLE x its real on-screen size
    on_screen = m["cmPerTile"] * PX_PER_CM
    out_px = max(24, int(round(on_screen * OVERSAMPLE)))
    tile = Image.open(tp).convert("RGB").resize((out_px, out_px), Image.LANCZOS)
    micro = Image.open(npth).convert("RGB").resize((out_px, out_px), Image.LANCZOS) if os.path.exists(npth) else None
    fab = {
        "code": m["code"], "name": m["name"], "kind": m["kind"],
        "tile": datauri(tile, "JPEG", quality=90, optimize=True),
        "sheen": m["sheen"], "relief": m["relief"], "meanLum": m.get("meanLum", 0.18),
        "cmPerTile": m["cmPerTile"], "onScreenPx": round(on_screen, 1),
        "price2pc": 575, "priceVest": 200,
    }
    if m["code"] in STILLS:
        fab["still"] = STILLS[m["code"]]["front"]
        if STILLS[m["code"]].get("back"):
            fab["stillBack"] = STILLS[m["code"]]["back"]
    if micro is not None:
        fab["micro"] = datauri(micro, "JPEG", quality=86, optimize=True)
    fabs.append(fab)
print(f"px/cm on render = {PX_PER_CM:.2f}; fabric tiles baked at {OVERSAMPLE}x true scale")

# curated option set — embed images as data URIs
OPTS = json.load(open(f"{CFG}/configurator_options.json"))
def embed(items, box=120):
    for it in items:
        if it.get("image"):
            it["img"] = file_datauri(os.path.join(CFG, it["image"]) if not os.path.isabs(it["image"]) else it["image"], box)
        it.pop("image", None)
    return items
for k in ("lapel", "chestPocket", "lowerPocket", "vent", "buttons", "linings"):
    OPTS[k] = embed(OPTS.get(k, []))
OPTS["monogram"]["fonts"] = embed(OPTS["monogram"].get("fonts", []), 160)

print(f"{len(cuts)} cuts, {len(fabs)} fabrics; options:",
      {k: (len(v) if isinstance(v, list) else {kk: len(vv) for kk, vv in v.items()}) for k, v in OPTS.items()})

HTML = r"""<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gage Court — Design your suit</title>
<style>
 :root{
  --bg:#f2efe9;--stage:__STAGE__;--rail:#f2efe9;--line:#e4dfd7;--line2:#d6d0c6;
  --ink:#1a1a1a;--soft:#8b857d;--faint:#a8a29a;--on:#111;--chip:#fff;
  --sans:system-ui,-apple-system,"Helvetica Neue","Segoe UI",Arial,sans-serif;
  --railw:clamp(320px,35%,440px);
  /* aliases kept so the make-ticket dialog styles work unchanged */
  --dock:#f2efe9;--ground:#f2efe9;--panel:#fff;--hair:#e4dfd7;--hair2:#d6d0c6;--brassd:#8b857d;}
 *{box-sizing:border-box}
 html,body{margin:0}
 body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-weight:300;line-height:1.4;-webkit-font-smoothing:antialiased}
 .app{display:flex;flex-direction:column;height:100vh;min-height:560px;background:var(--bg)}
 /* ---- top bar: centred wordmark, price + cart on the right ---- */
 .topbar{flex:none;position:relative;display:flex;align-items:center;justify-content:flex-end;gap:18px;
   padding:0 22px;height:72px;background:var(--bg);border-bottom:1px solid var(--line)}
 /* The wordmark is also the way BACK to the site: this page renders with {% layout none %} on
    Shopify, so there is no theme header and this is the only exit. Never hide it. */
 .brand{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);font-weight:600;letter-spacing:.26em;font-size:15px;white-space:nowrap;
   color:inherit;text-decoration:none}
 .brand:hover{opacity:.62}
 .tot b{font-weight:500;font-size:17px;letter-spacing:-.01em}
 .tot small{display:none}
 .finish{border:none;background:var(--on);color:#fff;border-radius:999px;padding:12px 24px;font:500 13.5px var(--sans);cursor:pointer;white-space:nowrap;transition:.14s}
 .finish:hover{background:#2a2a2a}
 .finish[disabled]{opacity:.55;cursor:default}
 /* ---- body: stage + right rail ---- */
 .main{flex:1;min-height:0;display:flex}
 .stage{flex:1;min-width:0;position:relative;display:flex;align-items:center;justify-content:center;background:var(--stage);overflow:hidden}
 /* per-fabric baked still — overlays the canvas at the Fabric step, fades in when loaded */
 .still{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;opacity:0;
   transition:opacity .28s ease;pointer-events:none;visibility:hidden}
 .still.show{opacity:1;visibility:visible}
 canvas.hero{display:block}
 .approx{position:absolute;left:24px;top:18px;max-width:38%;font-size:11px;color:var(--soft);line-height:1.35}
 /* view control card, bottom-left of the stage */
 .viewbar{position:absolute;left:24px;bottom:24px;display:flex;align-items:stretch;background:#fff;
   border:1px solid var(--line);border-radius:13px;overflow:hidden;box-shadow:0 1px 2px rgba(0,0,0,.04),0 8px 22px -14px rgba(0,0,0,.22)}
 .viewbar button{border:none;background:transparent;color:var(--soft);font:400 14px var(--sans);cursor:pointer;padding:14px 20px;transition:.14s;position:relative}
 .viewbar button:hover:not(:disabled){color:var(--ink)}
 .viewbar button.on{color:var(--ink);font-weight:500}
 .viewbar button.on::after{content:"";position:absolute;left:20px;right:20px;bottom:9px;height:2px;background:var(--ink);border-radius:2px}
 /* while the lazily-loaded side/back bundle is in flight (Shopify build only) */
 .viewbar button.busy{color:var(--soft);cursor:progress}
 .viewbar button.busy::after{content:"";position:absolute;left:20px;right:20px;bottom:9px;height:2px;border-radius:2px;
   background:linear-gradient(90deg,transparent,var(--ink),transparent);background-size:200% 100%;animation:gccload 1s linear infinite}
 @keyframes gccload{0%{background-position:100% 0}100%{background-position:-100% 0}}
 .viewbar button:disabled{color:var(--faint);cursor:not-allowed}
 .viewbar .exp{padding:0 15px;border-right:1px solid var(--line);display:flex;align-items:center}
 .viewbar .exp svg{width:17px;height:17px;stroke:currentColor;fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
 .app.zen .rail{display:none}
 /* ---- right rail ---- */
 .rail{flex:none;width:var(--railw);background:var(--rail);border-left:1px solid var(--line);display:flex;flex-direction:column;min-height:0}
 .tabs{flex:none;display:flex;gap:0;padding:0 24px;border-bottom:1px solid var(--line)}
 .tab{position:relative;border:none;background:transparent;color:var(--soft);font:400 14.5px var(--sans);
   padding:20px 16px 17px;cursor:pointer;white-space:nowrap;transition:.14s}
 .tab:first-child{padding-left:0}
 .tab:hover{color:var(--ink)}
 .tab.on{color:var(--ink);font-weight:500}
 .tab.on::after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:2px;background:var(--ink)}
 .tab:first-child.on::after{left:0;right:16px}
 .panel{flex:1;min-height:0;overflow-y:auto;padding:22px 24px 26px}
 .panel::-webkit-scrollbar{width:9px}
 .panel::-webkit-scrollbar-thumb{background:var(--line2);border-radius:9px;border:3px solid var(--rail)}
 .phead{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:0 0 14px}
 .phead .lbl{font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:var(--soft);font-weight:500}
 .filter{border:none;background:transparent;color:var(--ink);font:400 13.5px var(--sans);cursor:pointer;
   display:inline-flex;align-items:center;gap:6px;padding:4px 0}
 .filter svg{width:11px;height:11px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
 .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:11px}
 .sw{position:relative;aspect-ratio:1;border:1px solid var(--line2);border-radius:3px;background:var(--chip);
   background-size:cover;background-position:center;cursor:pointer;padding:0;transition:.14s}
 .sw:hover{border-color:var(--soft)}
 .sw.on{border:2px solid var(--ink)}
 .sw .tick{position:absolute;top:7px;right:7px;width:22px;height:22px;border-radius:50%;background:#fff;
   display:none;align-items:center;justify-content:center;box-shadow:0 1px 3px rgba(0,0,0,.2)}
 .sw.on .tick{display:flex}
 .sw .tick svg{width:11px;height:11px;stroke:var(--ink);fill:none;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round}
 /* option groups on the Style tab */
 .grp{margin-bottom:24px}
 .grp:last-child{margin-bottom:4px}
 .grp>.lbl{display:block;font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:var(--soft);font-weight:500;margin-bottom:11px}
 .row{display:flex;flex-wrap:wrap;gap:8px}
 .tile{border:none;background:transparent;padding:0;cursor:pointer;text-align:center;color:var(--soft);font:400 11px var(--sans);line-height:1.25;width:calc(33.333% - 6px)}
 .tile img{width:100%;aspect-ratio:4/3;object-fit:contain;background:#fff;border:1px solid var(--line2);border-radius:3px;margin-bottom:5px;transition:.14s}
 .tile.on{color:var(--ink)}.tile.on img{border:2px solid var(--ink)}
 .chip{width:44px;height:44px;border-radius:50%;border:1px solid var(--line2);background:var(--chip);
   background-size:cover;background-position:center;cursor:pointer;padding:0;transition:.14s}
 .chip.on{box-shadow:0 0 0 2px var(--ink);border-color:#fff}
 .pill{border:1px solid var(--line2);background:#fff;color:var(--soft);border-radius:999px;padding:9px 16px;
   font:400 13px var(--sans);cursor:pointer;white-space:nowrap;transition:.14s}
 .pill:hover{border-color:var(--ink);color:var(--ink)}
 .pill.on{background:var(--ink);color:#fff;border-color:var(--ink)}
 .mono-row{display:flex;gap:9px;align-items:center;flex-wrap:wrap}
 .mono-row input{font:inherit;font-size:13px;padding:9px 11px;border:1px solid var(--line2);border-radius:3px;background:#fff;width:110px;color:var(--ink)}
 .toggle{display:inline-flex;align-items:center;gap:9px;cursor:pointer;font-size:13.5px;color:var(--ink)}
 .toggle .sw2{width:38px;height:22px;border-radius:999px;background:var(--line2);position:relative;flex:none;transition:.15s}
 .toggle.on .sw2{background:var(--ink)}
 .toggle .sw2::after{content:"";position:absolute;top:2.5px;left:2.5px;width:17px;height:17px;border-radius:50%;background:#fff;transition:.15s}
 .toggle.on .sw2::after{left:18.5px}
 .note{font-size:13.5px;color:var(--soft);line-height:1.55;margin:0 0 14px}
 .note b{color:var(--ink);font-weight:500}
 .kv{display:flex;justify-content:space-between;gap:14px;padding:10px 0;border-bottom:1px solid var(--line);font-size:13.5px}
 .kv:last-child{border-bottom:none}
 .kv span{color:var(--soft)}
 /* rail footer: the selected cloth */
 .railfoot{flex:none;border-top:1px solid var(--line);padding:16px 24px;display:flex;align-items:center;gap:14px}
 .railfoot .ic{flex:none;width:44px;height:44px;border-radius:50%;background:#e8e4dc;display:flex;align-items:center;justify-content:center}
 .railfoot .ic svg{width:19px;height:19px;stroke:var(--ink);fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
 .railfoot .t{flex:1;min-width:0}
 .railfoot .t b{display:block;font-weight:500;font-size:14.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .railfoot .t small{display:block;color:var(--soft);font-size:12.5px;margin-top:2px}
 .spec-link{flex:none;background:transparent;border:none;color:var(--ink);font:400 13px var(--sans);cursor:pointer;
   display:inline-flex;align-items:center;gap:5px;padding:6px 0}
 .spec-link svg{width:11px;height:11px;stroke:currentColor;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
 @media(max-width:900px){
  .app{height:auto;min-height:100vh}
  .main{flex-direction:column}
  .stage{min-height:52vh}
  .rail{width:auto;border-left:none;border-top:1px solid var(--line)}
  .panel{max-height:none}
  .brand{font-size:13px;letter-spacing:.2em}
  .viewbar{left:14px;bottom:14px}
 }
 @media(max-width:560px){
  /* was display:none — but with no theme header there was then no branding and no way back to
     the site at all on a phone. Un-centre it instead so it sits left of the price and button. */
  .brand{position:static;transform:none;font-size:11px;letter-spacing:.14em;margin-right:auto}
  .topbar{justify-content:flex-end;padding:0 14px;gap:10px}
  .tot b{font-size:15px}
  .finish{padding:11px 17px;font-size:12.5px}
  .grid{grid-template-columns:repeat(4,1fr)}
  /* keep the floating view card clear of the model's feet on a narrow stage */
  .viewbar{left:12px;bottom:12px;border-radius:11px}
  .viewbar button{padding:11px 14px;font-size:13px}
  .viewbar button.on::after{left:14px;right:14px;bottom:7px}
  .viewbar .exp{padding:0 11px}
 }
 /* make-ticket dialog */
 dialog{border:none;border-radius:14px;max-width:560px;width:92%;padding:0;background:#fff;color:var(--ink)}
 dialog::backdrop{background:rgba(0,0,0,.45)}
 .dlg{padding:20px 22px}.dlg h3{font-weight:600;margin:0 0 4px;font-size:19px}
 .dlg .sub{color:var(--soft);font-size:13px;margin:0 0 14px}
 .codes{background:var(--bg);border:1px solid var(--line);border-radius:9px;padding:12px;font-size:12px;max-height:46vh;overflow:auto}
 .codes .r{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid var(--line)}
 .codes .r:last-child{border:none}.codes .c{font-family:ui-monospace,monospace;color:var(--soft)}
 .dlg .x{margin-top:14px;display:flex;gap:8px}.dlg button{font:500 13px var(--sans);border-radius:999px;padding:9px 16px;cursor:pointer;border:1px solid var(--line2);background:#fff;color:var(--ink)}
 .dlg button.p{background:var(--on);color:#fff;border-color:var(--on)}
 .codes .sec{margin-bottom:12px}
 .codes .sech{font:600 11px var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--soft);padding:2px 0 5px;border-bottom:1px solid var(--line2);margin-bottom:3px;display:flex;justify-content:space-between}
 .codes .sech .pc{color:var(--faint);font-weight:400;letter-spacing:0;text-transform:none}
 .codes .secn{font-size:11px;color:var(--soft);margin:1px 0 5px;line-height:1.4}
 .codes .sec.default{opacity:.8}
 .codes .r.tot{border-top:2px solid var(--line2);margin-top:9px;padding-top:9px;font-size:13px;font-weight:600}
</style>
<div class="app" id="app">
 <div class="topbar">
  <a class="brand" href="/" title="Gage Court Clothiers &mdash; back to the site">GAGE COURT</a>
  <div class="tot"><b id="totVal">$575</b><small id="totSub"></small></div>
  <button class="finish" id="addCart">Add to cart</button>
 </div>
 <div class="main">
  <div class="stage">
   <canvas class="hero" id="hero"></canvas>
   <img class="still" id="still" alt="" draggable="false" crossorigin="anonymous">
   <div class="approx" id="approx"></div>
   <div class="viewbar">
    <button class="exp" id="expand" title="Expand the preview" aria-label="Expand the preview">
     <svg viewBox="0 0 24 24"><path d="M15 3h6v6M21 3l-7 7M9 21H3v-6M3 21l7-7"/></svg>
    </button>
    <button id="viewFront" class="on">Front</button>
    <button id="viewSide">Side</button>
    <button id="viewBack">Back</button>
   </div>
  </div>
  <div class="rail">
   <div class="tabs" id="tabs"></div>
   <div class="panel" id="panel"></div>
   <div class="railfoot">
    <div class="ic"><svg viewBox="0 0 24 24"><path d="M12 2 2 7l10 5 10-5-10-5Z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg></div>
    <div class="t"><b id="selName">&mdash;</b><small id="selMeta"></small></div>
    <button class="spec-link" id="specLink">View details <svg viewBox="0 0 24 24"><path d="M9 18l6-6-6-6"/></svg></button>
   </div>
  </div>
 </div>
</div>
<dialog id="dlg"><div class="dlg">
  <h3>Your make ticket</h3>
  <p class="sub">This is exactly what would be sent to production — the KuteTailor craft codes for your suit.</p>
  <div class="codes" id="codes"></div>
  <div class="x"><button class="p" id="copyCodes">Copy make ticket</button><button id="copyJson">Copy order JSON</button><button id="closeDlg">Close</button></div>
</div></dialog>
<script>
const CUTS=__CUTS__, CUTVIEWS=__CUTVIEWS__, OPTS=__OPTS__;
let curView='front';   // front | side | back — orthogonal to the cut (style) choice
// Fabrics: the demo set by default; when embedded on Shopify we fetch the live collection (see bootstrap at end) and reassign.
const DEMO_FABRICS=__FABRICS__;
let FABRICS=(window.GCC_FABRICS&&window.GCC_FABRICS.length)?window.GCC_FABRICS:DEMO_FABRICS;
const FABRIC_COLLECTION='elite-wool';  // Shopify collection handle the customizer pulls fabrics from
const STYLES=[
  {label:"2-button",front:"0012",db:false,pieces:2,desc:"Single-breasted · 2-button"},
  {label:"1-button",front:"0011",db:false,pieces:2,desc:"Single-breasted · 1-button"},
  {label:"Double-breasted",front:"0016",db:true,pieces:2,desc:"Double-breasted · 6×2"},
  {label:"3-piece",front:"0012",db:false,pieces:3,desc:"Single-breasted · 2-button + waistcoat"}];
// House construction defaults = GCC's ACTUAL standard, derived from 10 live orders (real KuteTailor ecodes)
const JKT_DEF=[["Canvas","Fused","00C1"],["Lining","Full","AAQL"],["Inner facing","A","0701"],["Shoulder","Regular","0601"],["Front hem","Regular round","AAAC"],["Inner pocket","Regular","0801"],["Ticket pocket","None","027H"]];
const PANTS_DEF=[["Pleats","Flat front, no pleat","302L"],["Front pocket","2.5cm slant","3104"],["Back pocket","Besom w/ button","3201"],["Leg opening","9.0cm","360H"],["Waistband","Regular + snugtex","3440"],["Fly","Fish-mouth, nylon zip","3400"],["Closure","Hook & button","3412"],["Lining","Front-half","3501"]];
const VEST_DEF=[["Front","5-button","401G"],["Collar","V, no collar","4000"],["Bottom","Regular","401J"],["Lower pockets","Welt","4300"],["Back","Matched lining + strap","4210"],["Inner lining","Regular","4714"]];
const CUTMAP={"2-button":{"Notch":"notch","Peak":"peak","_":"notch"},"1-button":{"Peak":"one","_":"one"},
  "Double-breasted":{"Peak":"db","_":"db"},"3-piece":{"Notch":"three","_":"three"}};
const hero=document.getElementById('hero'),hx=hero.getContext('2d');
let W=0,H=0,off,ox,cutAssets={},pat={},fabPix={},microPix={};
let state={fabric:FABRICS[0].code,style:"2-button",lapel:"Notch",chest:OPTS.chestPocket[0]?.code,lower:OPTS.lowerPocket[0]?.code,
  vent:OPTS.vent[0]?.code,button:OPTS.buttons[0]?.code,lining:OPTS.linings[0]?.code,
  mono:{on:false,initials:"",thread:OPTS.monogram.thread[0]?.code,font:OPTS.monogram.fonts[0]?.code,pos:OPTS.monogram.positions[0]?.code}};
// WARP_AMP_N / NSMOOTH / WARP_CAP are in canvas px, tuned at W=700 — the builder scales
// them with the render width so the warp keeps its broad-bend-only character.
const WARP_AMP_N=__WARP_AMP__,NZ_MIN=0.35,NSMOOTH=__NSMOOTH__,WARP_CAP=__WARP_CAP__,PAT_DENSITY=__PAT_DENSITY__,SEAM_PHASE=0.42,SEAM_BUTTON=0.46,SS=3;
const OVERSAMPLE=__PAT_DENSITY__;   // must equal the builder OVERSAMPLE — tiles are pre-scaled
const SIL_WRAP=__SIL_WRAP__;   // how much the pattern follows the garment silhouette
// PATH A per-panel grain, degrees, indexed by panel id (see builder/panels.py — that file is
// where this table is defined and documented; it is emitted here so it ships with the compositor).
// [none, torso-L, torso-R, lapel-L, lapel-R, sleeve-L, sleeve-R, collar, trouser]
const PANEL_ANG=__PANEL_ANG__;
const FOOT=__FOOT__;           // runtime sampling footprint, in units of dens texels
const SHEEN_POW=1.6;           // how tightly the sheen hugs grazing angles
const GLINT=0.55;              // how much the weave micro-normal modulates the sheen
const TO_LIN=new Float32Array(256);for(let i=0;i<256;i++){const c=i/255;TO_LIN[i]=c<=0.04045?c/12.92:Math.pow((c+0.055)/1.055,2.4);}
function lin2srgb(l){l=l<0?0:l>1?1:l;return (l<=0.0031308?12.92*l:1.055*Math.pow(l,1/2.4)-0.055)*255;}
function load(src){return new Promise(r=>{const i=new Image();if(/^https?:/.test(src))i.crossOrigin='anonymous';i.onload=()=>r(i);i.onerror=()=>r(i);i.src=src;});}
function boxBlur(src,w,h,r){if(r<=0)return src.slice();const t=new Float32Array(w*h),o=new Float32Array(w*h),n=2*r+1;
  for(let y=0;y<h;y++){let s=0;for(let x=-r;x<=r;x++)s+=src[y*w+Math.min(w-1,Math.max(0,x))];
    for(let x=0;x<w;x++){t[y*w+x]=s/n;const a=Math.min(w-1,x+r+1),b=Math.max(0,x-r);s+=src[y*w+a]-src[y*w+b];}}
  for(let x=0;x<w;x++){let s=0;for(let y=-r;y<=r;y++)s+=t[Math.min(h-1,Math.max(0,y))*w+x];
    for(let y=0;y<h;y++){o[y*w+x]=s/n;const a=Math.min(h-1,y+r+1),b=Math.max(0,y-r);s+=t[a*w+x]-t[b*w+x];}}
  return o;}
function buildWarpNormal(nimg,alpha){const nc=document.createElement('canvas');nc.width=W;nc.height=H;
  const nxc=nc.getContext('2d');nxc.drawImage(nimg,0,0,W,H);const g=nxc.getImageData(0,0,W,H).data;
  const sx=new Float32Array(W*H),sy=new Float32Array(W*H);
  for(let i=0;i<W*H;i++){if(!alpha[i])continue;const nx=g[i*4]/127.5-1,ny=g[i*4+1]/127.5-1,nz=Math.max(Math.abs(g[i*4+2]/127.5-1),NZ_MIN);sx[i]=nx/nz;sy[i]=ny/nz;}
  const bx=boxBlur(sx,W,H,NSMOOTH),by=boxBlur(sy,W,H,NSMOOTH);const dispX=new Float32Array(W*H),dispY=new Float32Array(W*H);
  // --- SILHOUETTE WRAP -------------------------------------------------------------------
  // Parallax (nx/nz) compresses the pattern toward the silhouette but CANNOT tilt it: dispX
  // varies with x, barely with y, and the tilt is d(dispX)/dy. Suitsupply's stripes splay
  // from -11deg at the left edge to +11deg at the right (measured), which is the cloth
  // following the garment's changing width — a panel effect, not a surface-projection one.
  // So map x relative to the body's own centre and half-width per row: a texture-vertical
  // line then sits at x = cen[y] + C*hw[y], whose slope is the silhouette slope. Centre
  // stays vertical, edges splay, monotonic in between — the shape we measured on theirs.
  const cen=new Float32Array(H),hw=new Float32Array(H);
  for(let y=0;y<H;y++){let a=-1,b=-1;for(let x=0;x<W;x++){if(alpha[y*W+x]){if(a<0)a=x;b=x;}}
    if(a<0){cen[y]=W/2;hw[y]=0;}else{cen[y]=(a+b)/2;hw[y]=(b-a)/2;}}
  const R=Math.max(4,Math.round(NSMOOTH*1.5));           // smooth: silhouette, not lapel notches
  const cS=new Float32Array(H),hS=new Float32Array(H);
  for(let y=0;y<H;y++){let sc=0,sh=0,n=0;
    for(let k=-R;k<=R;k++){const yy=y+k;if(yy>=0&&yy<H&&hw[yy]>0){sc+=cen[yy];sh+=hw[yy];n++;}}
    cS[y]=n?sc/n:W/2;hS[y]=n?sh/n:1;}
  const hv=[];for(let y=0;y<H;y++)if(hS[y]>1)hv.push(hS[y]);
  hv.sort((a,b)=>a-b);const hRef=hv.length?hv[hv.length>>1]:1;   // median half-width
  for(let i=0;i<W*H;i++){if(!alpha[i])continue;
    const x=i%W,y=(i/W)|0;let dx=-WARP_AMP_N*bx[i],dy=-WARP_AMP_N*by[i];
    const m=Math.hypot(dx,dy);if(m>WARP_CAP){dx*=WARP_CAP/m;dy*=WARP_CAP/m;}
    if(hS[y]>1){const k=Math.max(0.55,Math.min(1.8,hRef/hS[y]));dx+=SIL_WRAP*(x-cS[y])*(k-1);}
    dispX[i]=dx;dispY[i]=dy;}
  const graze=new Float32Array(W*H);
  for(let i=0;i<W*H;i++){if(!alpha[i])continue;const nz=Math.min(1,Math.abs(g[i*4+2]/127.5-1));
    graze[i]=Math.pow(1-nz,SHEEN_POW);}
  return {dispX,dispY,alpha,graze};}
// The FRONT-OPENING phase break. Unchanged from before Path A, on purpose: the grain spec's
// seam research tested both a "collar-to-lapel matching is unnatural" claim and a "mismatch there
// is normal" claim and refuted BOTH, so there is no grounded reason to move SEAM_PHASE. It stays
// a per-PIXEL rule (right of the body's centre line, above the button) rather than becoming a
// per-panel one, so the existing look is preserved exactly.
function buildSeamPhase(alpha){const cen=new Float32Array(H);
  for(let y=0;y<H;y++){let s=0,c=0;for(let x=0;x<W;x++){if(alpha[y*W+x]){s+=x;c++;}}cen[y]=c?s/c:W/2;}
  const sm=new Float32Array(H),r=15;for(let y=0;y<H;y++){let s=0,c=0;for(let k=-r;k<=r;k++){const yy=y+k;if(yy>=0&&yy<H){s+=cen[yy];c++;}}sm[y]=s/c;}
  const bY=Math.floor(SEAM_BUTTON*H),seam=new Uint8Array(W*H);for(let y=0;y<bY;y++)for(let x=0;x<W;x++)if(alpha[y*W+x]&&x>sm[y])seam[y*W+x]=1;return seam;}
// PATH A — per-panel grain. The map itself is segmented at build time (builder/panels.py), where
// the render's own pixels are available and the result can be looked at; here we only decode it.
// Greyscale PNG, one panel id per pixel, so the red channel IS the id.
function buildPanels(img){const c=document.createElement('canvas');c.width=W;c.height=H;
  const x=c.getContext('2d');x.drawImage(img,0,0,W,H);const d=x.getImageData(0,0,W,H).data;
  const p=new Uint8Array(W*H);for(let i=0;i<W*H;i++)p[i]=d[i*4];return p;}
function sizeHero(){const st=hero.parentElement;if(!st||!W)return;const sw=Math.max(40,st.clientWidth-6),sh=Math.max(40,st.clientHeight-6),AR=W/H;
  let h=sh,w=h*AR;if(w>sw){w=sw;h=w/AR;}hero.style.width=Math.round(w)+'px';hero.style.height=Math.round(h)+'px';}
// One cut-view's assets -> cutAssets. Split out of init() so the side/back views can be added
// later from a second bundle (see ensureViews) instead of all 15 loading up front.
async function addCut(c){
  if(cutAssets[c.id])return;
  {const [b,d,m,nimg,pimg]=await Promise.all([load(c.base),load(c.drape),load(c.mask),load(c.normal),load(c.panel)]);
    if(!W){W=b.naturalWidth;H=b.naturalHeight;hero.width=W;hero.height=H;sizeHero();addEventListener('resize',sizeHero);
      // the stage can change size without a window resize (rail clamp, Shopify container,
      // the expand toggle) — observe the element itself, not just the window.
      if(window.ResizeObserver&&hero.parentElement){try{new ResizeObserver(sizeHero).observe(hero.parentElement);}catch(e){}}
      off=document.createElement('canvas');off.width=W;off.height=H;ox=off.getContext('2d');}
    const dc=document.createElement('canvas');dc.width=W;dc.height=H;const dx=dc.getContext('2d');
    dx.drawImage(d,0,0,W,H);const di=dx.getImageData(0,0,W,H);
    const mc=document.createElement('canvas');mc.width=W;mc.height=H;const mx=mc.getContext('2d');
    mx.drawImage(m,0,0,W,H);const mi=mx.getImageData(0,0,W,H);
    for(let i=0;i<di.data.length;i+=4)di.data[i+3]=mi.data[i];dx.putImageData(di,0,0);
    const alpha=new Uint8Array(W*H);for(let i=0;i<W*H;i++)alpha[i]=mi.data[i*4];
    const warp=buildWarpNormal(nimg,alpha);
    // per-panel grain, precomputed once per cut-view: cos/sin of the panel's angle and the
    // anchor it turns about (see PANEL_ANG and builder/panels.py's `anchors`)
    const nP=PANEL_ANG.length,pct=new Float32Array(nP),pst=new Float32Array(nP),
          pax=new Float32Array(nP),pay=new Float32Array(nP);
    for(let p=0;p<nP;p++){const t=PANEL_ANG[p]*Math.PI/180;pct[p]=Math.cos(t);pst[p]=Math.sin(t);
      const a=(c.anchor&&c.anchor[p])||[0,0];pax[p]=a[0];pay[p]=a[1];}
    cutAssets[c.id]={base:b,drapeLA:dc,warp,pct,pst,pax,pay,
      panel:buildPanels(pimg),
      seam:c.openFront?buildSeamPhase(warp.alpha):new Uint8Array(W*H)};}}
// LAZY SIDE/BACK. 10 of the 15 cut-views are side/back and most visitors never leave the front,
// so the Shopify build ships them as a second bundle that is fetched on the first Side/Back
// click. The self-contained local build has all 15 in CUTS and GCC_MORE_URL unset, so this is a
// no-op there and the two builds stay one code path.
let morePromise=null;
function ensureViews(){
  if(morePromise)return morePromise;
  if(!window.GCC_MORE_URL)return Promise.resolve();
  morePromise=new Promise((res,rej)=>{const s=document.createElement('script');
      s.src=window.GCC_MORE_URL;s.onload=res;s.onerror=()=>rej(new Error('side/back bundle failed'));
      document.head.appendChild(s);})
    .then(async()=>{for(const c of (window.GCC_MORE_CUTS||[]))await addCut(c);})
    .catch(e=>{morePromise=null;throw e;});   // let a failed load be retried on the next click
  return morePromise;}
async function init(){
  for(const c of CUTS)await addCut(c);
  await Promise.all(FABRICS.map(async f=>{const t=await load(f.tile);pat[f.code]=ox.createPattern(t,'repeat');
    if(f.micro){const mi=await load(f.micro);const mc=document.createElement('canvas');mc.width=mi.naturalWidth;mc.height=mi.naturalHeight;
      const mxx=mc.getContext('2d');mxx.drawImage(mi,0,0);microPix[f.code]=mxx.getImageData(0,0,mc.width,mc.height).data;}
    const tc=document.createElement('canvas');tc.width=t.naturalWidth;tc.height=t.naturalHeight;tc.getContext('2d').drawImage(t,0,0);
    fabPix[f.code]={d:tc.getContext('2d').getImageData(0,0,tc.width,tc.height).data,w:tc.width,h:tc.height};}));
  buildDock();render();sizeHero();}
let clothC,clothX;
let sheenBuf=null;
function warpedCloth(cutId,code){const A=cutAssets[cutId],{dispX,dispY,alpha,graze}=A.warp,
  seam=A.seam,panel=A.panel,pct=A.pct,pst=A.pst,pax=A.pax,pay=A.pay,
  T=fabPix[code],tw=T.w,th=T.h,td=T.d;
  const MN=microPix[code]||null,fdef=FABRICS.find(f=>f.code===code)||{},sheenAmt=(fdef.sheen!=null?fdef.sheen:0.14),sheenLum=(fdef.meanLum!=null?fdef.meanLum:0.18);
  if(!sheenBuf||sheenBuf.length!==W*H)sheenBuf=new Float32Array(W*H);
  const dens=(FABRICS.find(f=>f.code===code)||{}).density||PAT_DENSITY;const pox=SEAM_PHASE*tw,poy=SEAM_PHASE*th;
  if(!clothC){clothC=document.createElement('canvas');clothC.width=W;clothC.height=H;clothX=clothC.getContext('2d');}
  const out=clothX.createImageData(W,H),od=out.data;
  for(let y=0;y<H;y++)for(let x=0;x<W;x++){const i=y*W+x;if(!alpha[i]){od[i*4+3]=0;continue;}
    const oxx=seam[i]?pox:0,oyy=seam[i]?poy:0;
    // PATH A — per-panel grain. The torso and trousers are angle 0 and take the original path
    // verbatim (not just numerically equal: the same expression), so the panel with the measured
    // Suitsupply parity cannot regress. Lapel and collar rotate the sampling coordinate rigidly
    // about the panel's anchor, which is what makes the pattern sit still AT the anchor and turn
    // around it — that anchor is therefore also the panel's phase reference (the sleeve's sits on
    // the armhole at chest height, the one line the spec says a sleeve must match the body on).
    // A rigid coordinate rotation carries whatever is in the tile, so a check's two axes turn
    // together automatically; no separate 2D-pattern path is needed.
    const p=panel[i],wx=x+dispX[i],wy=y+dispY[i];let cx,cy;
    if(PANEL_ANG[p]===0){cx=wx*dens+oxx;cy=wy*dens+oyy;}
    else{const ax=pax[p],ay=pay[p],rx=wx-ax,ry=wy-ay,ct=pct[p],st=pst[p];
      cx=(ax+rx*ct+ry*st)*dens+oxx;cy=(ay-rx*st+ry*ct)*dens+oyy;}
    // gx/gy must only look at neighbours that are ALSO garment: buildWarpNormal writes disp
    // only inside the mask, so an ungated read at the silhouette treats the full displacement
    // as a gradient. Measured: edge pixels are 1.3-1.8% of the garment but their footprint ran
    // to 37.7 texels (18.8 canvas px = 70% of a stripe pitch) against an interior max of 3.31,
    // and 100% of all fp>4 pixels on every view were edge pixels — a faint ghosted rim.
    const gx=(i%W<W-1&&alpha[i+1])?Math.abs(dispX[i+1]-dispX[i]):0,
          gy=(i>=W&&alpha[i-W])?Math.abs(dispY[i]-dispY[i-W]):0;const fp=dens*FOOT*(1+2*(gx+gy));
    let rl=0,gl=0,bl=0;
    for(let sj=0;sj<SS;sj++)for(let si=0;si<SS;si++){const sx=cx+((si+0.5)/SS-0.5)*fp,sy=cy+((sj+0.5)/SS-0.5)*fp;
      let fx=sx%tw;if(fx<0)fx+=tw;let fy=sy%th;if(fy<0)fy+=th;
      const x0=fx|0,y0=fy|0,x1=(x0+1)%tw,y1=(y0+1)%th,ax=fx-x0,ay=fy-y0;
      const p00=(y0*tw+x0)*4,p10=(y0*tw+x1)*4,p01=(y1*tw+x0)*4,p11=(y1*tw+x1)*4;let t,b2;
      t=TO_LIN[td[p00]]*(1-ax)+TO_LIN[td[p10]]*ax;b2=TO_LIN[td[p01]]*(1-ax)+TO_LIN[td[p11]]*ax;rl+=t*(1-ay)+b2*ay;
      t=TO_LIN[td[p00+1]]*(1-ax)+TO_LIN[td[p10+1]]*ax;b2=TO_LIN[td[p01+1]]*(1-ax)+TO_LIN[td[p11+1]]*ax;gl+=t*(1-ay)+b2*ay;
      t=TO_LIN[td[p00+2]]*(1-ax)+TO_LIN[td[p10+2]]*ax;b2=TO_LIN[td[p01+2]]*(1-ax)+TO_LIN[td[p11+2]]*ax;bl+=t*(1-ay)+b2*ay;}
    const n=SS*SS;const R=rl/n,G=gl/n,B=bl/n;
    od[i*4]=lin2srgb(R);od[i*4+1]=lin2srgb(G);od[i*4+2]=lin2srgb(B);od[i*4+3]=255;
    // --- sheen: luminance of the cloth, weighted to grazing angles, modulated by weave micro-normal ---
    let gz=graze[i];
    if(MN){let mx=cx%tw;if(mx<0)mx+=tw;let my=cy%th;if(my<0)my+=th;
      const mp=((my|0)*tw+(mx|0))*4;const tilt=(MN[mp]/127.5-1)*0.5+(MN[mp+1]/127.5-1)*0.5;
      gz*=(1+GLINT*tilt);}
    sheenBuf[i]=sheenLum*gz*sheenAmt;}   // FLAT tint: per-pixel luminance would amplify stripes/checks
  clothX.putImageData(out,0,0);return clothC;}
let sheenC,sheenX;
function sheenLayer(){ // additive pass — multiply can only darken, sheen is what makes cloth read as cloth
  if(!sheenC){sheenC=document.createElement('canvas');sheenC.width=W;sheenC.height=H;sheenX=sheenC.getContext('2d');}
  const im=sheenX.createImageData(W,H),d=im.data;
  for(let i=0;i<W*H;i++){const v=sheenBuf?sheenBuf[i]:0;const s=lin2srgb(v);
    d[i*4]=s;d[i*4+1]=s;d[i*4+2]=s;d[i*4+3]=255;}
  sheenX.putImageData(im,0,0);return sheenC;}
function resolveCut(){const s=CUTMAP[state.style]||CUTMAP["2-button"];const cut=s[state.lapel]||s["_"];return {cut,approx:!s[state.lapel]};}
function render(){const {cut,approx}=resolveCut();
  const vv=(CUTVIEWS[cut]&&CUTVIEWS[cut].includes(curView))?curView:'front';
  const ck=cutAssets[cut+'__'+vv]?cut+'__'+vv:cut+'__front';   // asset key: cut x view
  const A=cutAssets[ck];hx.clearRect(0,0,W,H);hx.drawImage(A.base,0,0);
  const f=FABRICS.find(x=>x.code===state.fabric);
  ox.setTransform(1,0,0,1,0,0);ox.clearRect(0,0,W,H);ox.globalCompositeOperation='source-over';
  ox.drawImage(warpedCloth(ck,state.fabric),0,0);   // tiled at true scale for every cloth
  ox.globalCompositeOperation='destination-in';ox.drawImage(A.drapeLA,0,0);
  ox.globalCompositeOperation='overlay';ox.drawImage(A.drapeLA,0,0);ox.globalCompositeOperation='source-over';
  hx.drawImage(off,0,0);
  // additive sheen, masked to the suit
  ox.globalCompositeOperation='source-over';ox.clearRect(0,0,W,H);
  ox.drawImage(sheenLayer(),0,0);
  ox.globalCompositeOperation='destination-in';ox.drawImage(A.drapeLA,0,0);
  ox.globalCompositeOperation='source-over';
  hx.globalCompositeOperation='lighter';hx.drawImage(off,0,0);hx.globalCompositeOperation='source-over';
  const ap=document.getElementById('approx');if(ap)ap.textContent=approx?('Preview shows the nearest rendered lapel — made with your '+state.lapel+' lapel.'):'';
  updateChrome();}
// ---- UI: stage + right rail. Three tabs; every option group lives under Style. ----
const SECTIONS=[{key:'fabric',label:'Fabric'},{key:'style',label:'Style'},{key:'measure',label:'Measurements'}];
let activeSection='fabric';
let fabFilter='all';   // all | solid | pattern
const el=(t,c,h)=>{const n=document.createElement(t);if(c)n.className=c;if(h!=null)n.innerHTML=h;return n;};
function chip(img,on,cb){const b=el('button','chip'+(on?' on':''));if(img)b.style.backgroundImage='url("'+img+'")';b.onclick=cb;return b;}
function tile(img,label,on,cb){const b=el('button','tile'+(on?' on':''),(img?'<img src="'+img+'" alt="">':'')+'<span>'+label+'</span>');b.onclick=cb;return b;}
function pill(label,on,cb){const b=el('button','pill'+(on?' on':''));b.textContent=label;b.onclick=cb;return b;}
function group(label,nodes,cls){const w=el('div','grp');w.appendChild(el('span','lbl',label));
  const r=el('div',cls||'row');nodes.forEach(n=>r.appendChild(n));w.appendChild(r);return w;}
function pick(setter){setter();render();renderPanel();}
function filteredFabrics(){return FABRICS.filter(f=>fabFilter==='all'||(f.kind||'solid')===fabFilter);}
function renderPanel(){const p=document.getElementById('panel');if(!p)return;p.innerHTML='';
  if(activeSection==='fabric'){
    const head=el('div','phead');head.appendChild(el('span','lbl','Select fabric'));
    const FILT=[['all','All fabrics'],['solid','Solids'],['pattern','Patterns']];
    const fb=el('button','filter','<span>'+(FILT.find(x=>x[0]===fabFilter)[1])+'</span><svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg>');
    fb.onclick=()=>{const i=FILT.findIndex(x=>x[0]===fabFilter);fabFilter=FILT[(i+1)%FILT.length][0];renderPanel();};
    head.appendChild(fb);p.appendChild(head);
    const g=el('div','grid');
    filteredFabrics().forEach(f=>{const b=el('button','sw'+(state.fabric===f.code?' on':''),
        '<span class="tick"><svg viewBox="0 0 24 24"><path d="M20 6L9 17l-5-5"/></svg></span>');
      b.style.backgroundImage='url("'+(f.tile||f.img)+'")';b.title=f.name;
      b.onclick=()=>pick(()=>state.fabric=f.code);g.appendChild(b);});
    p.appendChild(g);
    if(!filteredFabrics().length)p.appendChild(el('p','note','No cloths in this group yet.'));
  }
  else if(activeSection==='style'){
    p.appendChild(group('Cut',STYLES.map(st=>pill(st.label,state.style===st.label,()=>pick(()=>state.style=st.label)))));
    p.appendChild(group('Lapel',OPTS.lapel.map(l=>tile(l.img,l.label,state.lapel===l.label,()=>pick(()=>state.lapel=l.label)))));
    p.appendChild(group('Chest pocket',OPTS.chestPocket.map(o=>tile(o.img,o.label,state.chest===o.code,()=>pick(()=>state.chest=o.code)))));
    p.appendChild(group('Lower pockets',OPTS.lowerPocket.map(o=>tile(o.img,o.label,state.lower===o.code,()=>pick(()=>state.lower=o.code)))));
    p.appendChild(group('Vents',OPTS.vent.map(o=>pill(o.label,state.vent===o.code,()=>pick(()=>state.vent=o.code)))));
    p.appendChild(group('Buttons',OPTS.buttons.map(o=>chip(o.img||o.tile,state.button===o.code,()=>pick(()=>state.button=o.code)))));
    p.appendChild(group('Lining',OPTS.linings.map(o=>chip(o.img||o.tile,state.lining===o.code,()=>pick(()=>state.lining=o.code)))));
    p.appendChild(renderMono());
  }
  else if(activeSection==='measure'){
    p.appendChild(el('p','note','<b>Your measurements are taken in person.</b> Every Gage Court suit is made to measure and fitted at your appointment in Pikesville or Central Jersey — there is nothing to enter here.'));
    p.appendChild(el('p','note','The preview is drawn on our house model at a standard size so you can judge the cloth and the styling. Your own measurements replace it once you are fitted.'));
    const g=el('div','grp');g.appendChild(el('span','lbl','Preview shown at'));
    [['Jacket','38R'],['Trousers','32R'],['Model height','5′11″ / 180cm']].forEach(r=>{
      const k=el('div','kv');k.appendChild(el('b',null,r[0]));k.appendChild(el('span',null,r[1]));g.appendChild(k);});
    p.appendChild(g);
  }
  updateChrome();}
function renderMono(){const g=el('div','grp');g.appendChild(el('span','lbl','Monogram'));
  const row=el('div','mono-row');
  const tog=el('div','toggle'+(state.mono.on?' on':''),'<span class="sw2"></span><span>Add a monogram</span>');
  tog.onclick=()=>pick(()=>state.mono.on=!state.mono.on);row.appendChild(tog);
  g.appendChild(row);
  if(state.mono.on){const r2=el('div','mono-row');r2.style.marginTop='11px';
    const inp=el('input');inp.type='text';inp.maxLength=4;inp.placeholder='Initials';inp.value=state.mono.initials||'';
    inp.oninput=e=>{state.mono.initials=e.target.value;updateChrome();};r2.appendChild(inp);
    OPTS.monogram.thread.slice(0,6).forEach(t=>r2.appendChild(pill(t.name,state.mono.thread===t.code,()=>pick(()=>state.mono.thread=t.code))));
    g.appendChild(r2);}
  return g;}
function renderTabs(){const t=document.getElementById('tabs');if(!t)return;t.innerHTML='';
  SECTIONS.forEach(sec=>{const b=el('button','tab'+(sec.key===activeSection?' on':''));b.textContent=sec.label;
    b.onclick=()=>{activeSection=sec.key;renderTabs();renderPanel();render();};t.appendChild(b);});}
// back-compat: older call sites (and the Shopify bootstrap) still say renderStrip()
function renderStrip(){renderPanel();}
// The rail footer always describes the CLOTH — that is the thing a customer wants named.
// Only facts we actually hold: the Shopify name and the mill code. No weight/season here;
// we do not carry that data and must not invent it.
function selInfo(){const f=FABRICS.find(x=>x.code===state.fabric)||{};
  const kind=(f.kind==='pattern')?'Patterned':'Solid';
  return [f.name||'—','Elite Wool · '+kind+(f.code?' · '+f.code:'')];}
function updateChrome(){const a=selInfo();const sn=document.getElementById('selName'),sm=document.getElementById('selMeta'),tv=document.getElementById('totVal');
  if(sn)sn.textContent=a[0];if(sm)sm.textContent=a[1];if(tv)tv.textContent='$'+price().toLocaleString();
  updateStill();}
// ---- per-fabric baked still (Suitsupply fabric-step architecture) ----
// At the Fabric step, fabrics that have an approved catalog still show it instead of the
// live composite; the compositor takes over on the Style step. Back enables when the
// fabric has a back still.
// Front/Side/Back drive curView for the live compositor. When a fabric still is showing
// (Fabric tab), views instead follow the still's availability (front + optional back).
function updateViewButtons(){
  const {cut}=resolveCut();const avail=CUTVIEWS[cut]||['front'];
  const f=FABRICS.find(x=>x.code===state.fabric)||{};
  const stillOn=activeSection==='fabric'&&!!f.still;
  const has={front:true,
             side: !stillOn && avail.includes('side'),
             back: stillOn ? !!f.stillBack : avail.includes('back')};
  if(!has[curView])curView='front';
  [['viewFront','front'],['viewSide','side'],['viewBack','back']].forEach(([id,v])=>{
    const b=document.getElementById(id);if(!b)return;
    b.disabled=!has[v];b.title=has[v]?'':(v+' view not available yet');
    b.classList.toggle('on',curView===v);});}
function updateStill(){
  const f=FABRICS.find(x=>x.code===state.fabric)||{};
  const img=document.getElementById('still');if(!img)return;
  const use=activeSection==='fabric'&&!!f.still;
  if(use){
    const src=(curView==='back'&&f.stillBack)?f.stillBack:f.still;
    if(img.getAttribute('src')!==src){img.classList.remove('show');img.onload=()=>img.classList.add('show');img.src=src;}
    else img.classList.add('show');
  }else{img.classList.remove('show');}
  updateViewButtons();}
function buildDock(){renderTabs();renderPanel();
  const ac=document.getElementById('addCart');if(ac)ac.onclick=addToCart;
  const sl=document.getElementById('specLink');if(sl)sl.onclick=openTicket;
  const ex=document.getElementById('expand');
  if(ex)ex.onclick=()=>{document.getElementById('app').classList.toggle('zen');sizeHero();};
  [['viewFront','front'],['viewSide','side'],['viewBack','back']].forEach(([id,v])=>{
    const b=document.getElementById(id);if(b)b.onclick=async()=>{if(b.disabled)return;
      if(v!=='front'&&window.GCC_MORE_URL&&!cutAssets[resolveCut().cut+'__'+v]){
        b.classList.add('busy');
        try{await ensureViews();}catch(e){b.classList.remove('busy');return;}
        b.classList.remove('busy');}
      curView=v;render();};});}
function nameOf(list,code,field){const o=(list||[]).find(x=>x.code===code);return o?(o.name||o.label||o[field]||code):code;}
// Price = the fabric's own 2-piece price (+ its vest price for 3-piece) + monogram. Per-fabric prices come from the Shopify product; demo falls back to 575/200.
function price(){const f=FABRICS.find(x=>x.code===state.fabric)||{};const base=(f.price2pc!=null?f.price2pc:575);const vest=(f.priceVest!=null?f.priceVest:200);return base+(curStyle().pieces===3?vest:0)+(state.mono.on?25:0);}
function curStyle(){return STYLES.find(s=>s.label===state.style)||STYLES[0];}
function ticket(){const f=FABRICS.find(x=>x.code===state.fabric);const st=curStyle();
  const lap=OPTS.lapel.find(l=>l.label===state.lapel)||{};
  const jrows=[['Front & buttons',st.desc,st.front],['Lapel',state.lapel,lap.code||''],
    ['Chest pocket',nameOf(OPTS.chestPocket,state.chest),state.chest],['Lower pockets',nameOf(OPTS.lowerPocket,state.lower),state.lower],
    ['Vents',nameOf(OPTS.vent,state.vent),state.vent],['Lining',nameOf(OPTS.linings,state.lining),state.lining],
    ['Buttons',nameOf(OPTS.buttons,state.button),state.button]];
  if(state.mono.on)jrows.push(['Monogram',(state.mono.initials||'—')+' · '+nameOf(OPTS.monogram.thread,state.mono.thread,'name')+' · '+nameOf(OPTS.monogram.fonts,state.mono.font,'name'),[state.mono.pos,state.mono.thread,state.mono.font].filter(Boolean).join(',')]);
  const sections=[
    {title:'Cloth',pc:'',kind:'cloth',rows:[[f.name,'',f.code]]},
    {title:'Jacket',pc:'1 of '+st.pieces,kind:'garment',rows:jrows},
    {title:'Trousers',pc:'2 of '+st.pieces,kind:'garment',rows:PANTS_DEF.slice()}];
  if(st.pieces===3)sections.push({title:'Waistcoat',pc:'3 of 3',kind:'garment',
    note:'Matching cloth. Waistcoat construction finalised at your fitting.',rows:VEST_DEF.slice()});
  sections.push({title:'Jacket construction — house standard',pc:'',kind:'default',rows:JKT_DEF.slice()});
  return {fabric:{name:f.name,code:f.code},price:price(),pieces:st.pieces,sections};}
function ticketText(){const t=ticket();let o='GAGE COURT CLOTHIERS — MAKE TICKET ('+t.pieces+'-piece)\n';
  t.sections.forEach(s=>{o+='\n'+s.title.toUpperCase()+'\n';if(s.note)o+='  ('+s.note+')\n';
    s.rows.forEach(r=>{o+='  '+r[0]+(r[1]?': '+r[1]:'')+(r[2]&&r[2]!=='—'?'  ['+r[2]+']':'')+'\n';});});
  o+='\nIndicative price: $'+t.price.toLocaleString()+'\n';return o;}
// Real KuteTailor POST /order/saveOrder body (submit:false = saves to CART, unpaid). crafts = comma-joined ecode / ecode:content.
// jacket=MXF pants=MXK vest=MMJ; 2pc category "T", 3pc category "S". Button=0638/3454/4240:<code>, lining=0714/4714:<code>.
// Standard size = jacket/vest 38R, pants 32R (inches); measuresType 10002 (finished); positionEcode = blEcode (XF/XK/MJ).
const STD_SIZE={
  MXF:[["XF01",41.7],["XF02",37.0],["XF03",40.9],["XF08",17.7],["XF05",24.4],["XF06",24.4],["XF07",29.5],["XF04",15.4]],
  MXK:[["XK01",33.9],["XK02",40.9],["XK03",25.6],["XK04",26.8],["XK05",42.1],["XK06",42.1],["XK07",15.4]],
  MMJ:[["MJ01",39.8],["MJ02",37.0],["MJ04",23.2]]};
function stdSizes(cc){return STD_SIZE[cc].map(function(x){return {positionEcode:x[0],size:x[1]};});}
function orderPayload(){const st=curStyle();const three=st.pieces===3;
  const lap=(OPTS.lapel.find(l=>l.label===state.lapel)||{}).code||'';
  const jc=[st.front,lap,state.chest,state.lower,state.vent,'00C1','AAQL','0701','0714:'+state.lining,'0638:'+state.button,'0601','AAAC','0801','027H'].filter(Boolean).join(',');
  const pc=['302L','3104','3201','360H','3440','344A','3412','3400','3420','372K','3501','3454:'+state.button].join(',');
  const details=[
    {categoryCode:'MXF',styleCode:'',crafts:jc,sizeNames:'38R',orderSizes:stdSizes('MXF'),
     orderEmbs:(state.mono.on?[{embPositionCode:state.mono.pos,fontCode:state.mono.font,colorCode:state.mono.thread,content:state.mono.initials||''}]:[])},
    {categoryCode:'MXK',styleCode:'',crafts:pc,sizeNames:'32R',orderSizes:stdSizes('MXK')}];
  if(three)details.push({categoryCode:'MMJ',styleCode:'',crafts:['401G','401J','4000','4X06','4300','4210','4200','4714:'+state.lining,'4240:'+state.button].join(','),sizeNames:'38R',orderSizes:stdSizes('MMJ')});
  return {orderNo:'',submit:false,customerNo:'',addProduct:true,amount:1,isSample:0,
    category:three?'S':'T',measuresType:10002,fabric:state.fabric,
    customer:{nickname:'',firstname:'',lastname:'',gender:'1002',height:178,heightUnit:1019,weight:80,weightUnit:1017},
    orderDetails:details};}
// ---- Shopify order capture: one container product; design travels as line-item properties ----
const SHOPIFY={containerId:8484001677499,
  variantByPrice:{550:48117852012731,575:48117852045499,600:48117852078267,625:48117852111035,650:48117852143803,675:48117852176571,700:48117852209339,725:48117852242107,750:48117852274875,775:48117852307643,800:48117852340411,825:48117852373179,850:48117852405947,875:48117852438715,900:48117852471483,950:48117852504251,1000:48117852537019}};
function pickVariant(total){const tiers=Object.keys(SHOPIFY.variantByPrice).map(Number).sort((a,b)=>a-b);let t=tiers.find(x=>x>=total);if(t==null)t=tiers[tiers.length-1];return SHOPIFY.variantByPrice[t];}
// Neutral, supplier-agnostic order the backend receives; KuteTailor saveOrder body is one mapping inside supplierSpecs.
function orderEnvelope(){const f=FABRICS.find(x=>x.code===state.fabric)||{};const st=curStyle();
  return {schema:'gcc.order/v1',price:price(),customer:{},
    design:{fabricCode:state.fabric,fabricName:f.name,pieces:st.pieces,cut:state.style,lapel:state.lapel,
      chestPocket:state.chest,lowerPocket:state.lower,vent:state.vent,lining:state.lining,buttons:state.button,
      monogram:state.mono.on?{initials:state.mono.initials,thread:state.mono.thread,font:state.mono.font,position:state.mono.pos}:null,
      size:'jacket 38R / pants 32R (standard — confirmed at fitting)'},
    supplierSpecs:{kutetailor:orderPayload()}};}
function onShopify(){return !!(window.Shopify&&window.Shopify.routes);}
function addToCart(){const env=orderEnvelope();const vid=pickVariant(env.price);const f=FABRICS.find(x=>x.code===state.fabric)||{};
  const props={'_config':JSON.stringify(env),'Cloth':(f.name||'')+' ('+state.fabric+')','Cut':state.style+' · '+state.lapel+' lapel',
    'Lining':nameOf(OPTS.linings,state.lining),'Buttons':nameOf(OPTS.buttons,state.button)};
  if(state.mono.on)props['Monogram']=(state.mono.initials||'(initials)');
  if(!onShopify()){openTicket();return;}   // standalone preview: show the make ticket instead of hitting a live cart
  const btn=document.getElementById('addCart');if(btn){btn.disabled=true;btn.textContent='Adding…';}
  const root=(window.Shopify&&Shopify.routes&&Shopify.routes.root)||'/';
  fetch(root+'cart/add.js',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({items:[{id:vid,quantity:1,properties:props}]})})
   .then(r=>r.json()).then(()=>{window.location.href=root+'cart';})
   .catch(e=>{if(btn){btn.disabled=false;btn.textContent='Add to cart — $'+price().toLocaleString();}alert('Could not add to cart: '+e);});}
function openTicket(){const t=ticket();const el=document.getElementById('codes');
  let h=t.sections.map(sec=>{let s=`<div class="sec ${sec.kind}"><div class="sech"><span>${sec.title}</span>${sec.pc?`<span class="pc">${sec.pc}</span>`:''}</div>`;
    if(sec.note)s+=`<div class="secn">${sec.note}</div>`;
    s+=sec.rows.map(r=>`<div class="r"><span>${r[0]}${r[1]?': <b>'+r[1]+'</b>':''}</span><span class="c">${r[2]&&r[2]!=='—'?r[2]:''}</span></div>`).join('');
    return s+`</div>`;}).join('');
  h+=`<div class="r tot"><span>Indicative price</span><span class="c">$${t.price.toLocaleString()}</span></div>`;
  el.innerHTML=h;document.getElementById('dlg').showModal();}
document.getElementById('closeDlg').onclick=()=>document.getElementById('dlg').close();
function copyTo(id,txt,done){try{navigator.clipboard&&navigator.clipboard.writeText(txt);}catch(e){}const b=document.getElementById(id);const o=b.textContent;b.textContent=done;setTimeout(()=>b.textContent=o,1400);}
document.getElementById('copyCodes').onclick=()=>copyTo('copyCodes',ticketText(),'Copied ✓');
document.getElementById('copyJson').onclick=()=>copyTo('copyJson',JSON.stringify(orderPayload(),null,2),'Copied ✓');
// When embedded on Shopify, pull the fabric list from the live collection (published products only; drafts → empty → keep demo).
async function loadShopifyFabrics(){
  try{
    const r=await fetch('/collections/'+FABRIC_COLLECTION+'/products.json?limit=250',{headers:{'Accept':'application/json'}});
    if(!r.ok)return null;const j=await r.json();
    const fabs=(j.products||[]).map(p=>{
      const two=(p.variants||[]).find(v=>/two piece/i.test(v.title))||p.variants[0]||{};
      const vest=(p.variants||[]).find(v=>/vest/i.test(v.title));
      const code=(two.sku)||(p.variants[0]&&p.variants[0].sku)||'';
      const img=(p.images&&p.images[0]&&(p.images[0].src))||'';
      const pat=/check|plaid|windowpane|glen|prince of wales|stripe|herringbone|houndstooth/i.test(p.title);
      return {code,name:(p.title||'').replace(/\s*\([^)]*\)\s*$/,'').replace(/^Elite Wool\s*[-–]\s*/i,''),
        kind:pat?'pattern':'solid',tile:img,
        price2pc:Math.round(parseFloat(two.price||'575')),priceVest:vest?Math.round(parseFloat(vest.price)):200};
    }).filter(f=>f.code&&f.tile);
    return fabs.length?fabs:null;
  }catch(e){return null;}
}
(async function(){ if(onShopify()){const sf=await loadShopifyFabrics(); if(sf){FABRICS=sf; state.fabric=sf[0].code;}} init(); })();
</script>
"""
html = (HTML.replace("__CUTVIEWS__", json.dumps(cutviews))
            .replace("__CUTS__", json.dumps(cuts))
            .replace("__FABRICS__", json.dumps(fabs))
            .replace("__OPTS__", json.dumps(OPTS))
            .replace("__PAT_DENSITY__", str(OVERSAMPLE))
            .replace("__FOOT__", f"{FOOTPRINT:.2f}")
            .replace("__SIL_WRAP__", f"{SIL_WRAP:.2f}")
            .replace("__PANEL_ANG__", json.dumps(PANEL_ANGLES))
            .replace("__STAGE__", "#%02x%02x%02x" % STAGE_RGB)
            .replace("__WARP_AMP__", f"{WARP_AMP_MULT * RSCALE:.2f}")
            .replace("__NSMOOTH__", str(max(1, round(12 * RSCALE))))
            # cap 16->6.5 (2026-07-21): at 16 the displacement saturated (~30 canvas px, more
            # than a whole stripe pitch) in strong concave creases — crotch, hem curls — and
            # visibly S-bent the stripes there (user-flagged on DBT6860). 6.5 (=12 canvas px)
            # straightens them while keeping the gentle silhouette bow; only 7.4% of garment
            # px were above 12, all in those crease zones.
            .replace("__WARP_CAP__", f"{6.5 * RSCALE:.2f}"))


def _fill(s, cuts_json):
    """Apply every placeholder except __CUTS__, which differs between the two builds."""
    return (s.replace("__CUTVIEWS__", json.dumps(cutviews))
             .replace("__CUTS__", cuts_json)
             .replace("__FABRICS__", json.dumps(fabs))
             .replace("__OPTS__", json.dumps(OPTS))
             .replace("__PAT_DENSITY__", str(OVERSAMPLE))
             .replace("__FOOT__", f"{FOOTPRINT:.2f}")
             .replace("__SIL_WRAP__", f"{SIL_WRAP:.2f}")
             .replace("__PANEL_ANG__", json.dumps(PANEL_ANGLES))
             .replace("__STAGE__", "#%02x%02x%02x" % STAGE_RGB)
             .replace("__WARP_AMP__", f"{WARP_AMP_MULT * RSCALE:.2f}")
             .replace("__NSMOOTH__", str(max(1, round(12 * RSCALE))))
             .replace("__WARP_CAP__", f"{6.5 * RSCALE:.2f}"))


open(OUT, "w").write(html)
print(f"canvas {W}x{H} (full frame {W}x{H_FULL}, cropped to top {CROP_FRAC:.0%}); "
      f"px-scale constants x{RSCALE:.3f}; {os.path.getsize(OUT)/1048576:.2f} MB")
print("wrote", OUT, f"({os.path.getsize(OUT)/1024/1024:.2f} MB)")

# ---------------------------------------------------------------- SPLIT BUILD (Shopify embed)
# Same code, three files instead of one. Shopify's CDN re-encodes anything it sniffs as an image
# — in Files AND in theme assets, whatever the extension (measured 2026-07-23; a lossless normal
# map came back as a 46 KB JPEG with 20 levels of pixel error). It serves .js byte-exact and
# gzipped. So the data-URIs stay exactly as they are and ride inside a JS bundle.
#   core.js  = the compositor + the 5 FRONT cut-views  (the initial load)
#   views.js = the 10 side/back cut-views              (fetched on the first Side/Back click)
#   .liquid  = the markup + CSS, as a page template
if os.environ.get("GCC_SPLIT") == "1":
    DIST = f"{HM}/dist"
    os.makedirs(DIST, exist_ok=True)
    front = [c for c in cuts if c["id"].endswith("__front")]
    rest = [c for c in cuts if not c["id"].endswith("__front")]

    i_style, i_script = HTML.index("<style>"), HTML.index("<script>")
    i_end = HTML.rindex("</script>")
    markup = _fill(HTML[i_style:i_script], "[]")                       # <style>..</style> + body
    script = _fill(HTML[i_script + len("<script>"):i_end], json.dumps(front))

    core = f"{DIST}/gcc-configurator-core.js"
    views = f"{DIST}/gcc-configurator-views.js"
    liquid = f"{DIST}/page.configurator.liquid"

    # The CSS and markup go INSIDE core.js and are injected before the compositor runs, so the
    # Liquid template stays a ~10-line shell. That is deliberate: themeFilesUpsert will not take
    # a URL body for templates/*.liquid (only TEXT), and the only way to send TEXT is to retype
    # it into a tool call — which is exactly how a 6.6 KB asset got truncated to 3.5 KB earlier
    # today. A file small enough to type by hand safely is worth the indirection.
    css, body = markup.split("</style>", 1)
    css = css.replace("<style>", "", 1)
    boot = ("(function(){var s=document.createElement('style');s.textContent=" + json.dumps(css) +
            ";document.head.appendChild(s);"
            "var w=document.createElement('div');w.innerHTML=" + json.dumps(body.strip()) +
            ";while(w.firstChild)document.body.appendChild(w.firstChild);})();\n")
    open(core, "w").write(boot + script)
    open(views, "w").write("window.GCC_MORE_CUTS=" + json.dumps(rest) + ";\n")
    # layout none: the configurator carries its own chrome and its CSS uses generic class names
    # (.app/.main/.rail/.grid/.row) that would collide both ways with the theme's stylesheet.
    # Rendering without the theme layout guarantees the look that was verified locally.
    open(liquid, "w").write(
        "{% layout none %}<!doctype html>\n<html lang=\"en\"><head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
        "<title>Design your suit | Gage Court Clothiers</title>\n"
        "</head><body>\n"
        "<script>window.GCC_MORE_URL=\"__VIEWS_URL__\";</script>\n"
        "<script src=\"__CORE_URL__\"></script>\n"
        "</body></html>\n")
    for p in (core, views, liquid):
        print(f"  {os.path.basename(p):32s} {os.path.getsize(p)/1048576:6.2f} MB")
    print(f"split build in {DIST}/ — {len(front)} front cut-views in core, {len(rest)} lazy")
