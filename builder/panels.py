#!/usr/bin/env python3
"""Path A — per-panel garment segmentation (build time).

Turns one flat render + its coverage mask into a PANEL-ID map so the runtime compositor can give
each tailoring panel its own cloth grain, per `plan/PATH_A_GRAIN_SPEC.md`:

    torso      existing normal-driven warp, angle 0      (at Suitsupply parity — must not regress)
    lapel      fixed-angle rotation, mirrored L/R        (shipped +-16, see THE GRAIN TABLE below)
    sleeve     fixed-angle rotation, mirrored L/R        (shipped +-5)
    collar     fixed-angle rotation, near-horizontal     (shipped 87 — true-bias convention)
    trouser    same as torso

Why build time and not runtime JS: the panel map is GEOMETRY, and geometry in this codebase is
already a build-time, per-cut-view asset (mask, drape, normal) — Suitsupply's teardown
(plan/SS_RENDER_ARCHITECTURE_SPEC.md S3) makes the same split, geometry fixed per style with the
cloth swapped in on top. Segmenting here also means the hard perception steps (finding the shirt
V, the collar, the armhole) run in numpy where they can be rendered as an overlay and LOOKED at
instead of being debugged blind in the browser.

The map is emitted as a single-channel PNG (large flat regions => tiny after PNG compression) and
decoded by `buildPanels` in the compositor.

Run this file directly to print the landmarks and write a 15-cut-view QA contact sheet — every
defect the first drafts had was caught by looking at that sheet, never by a number:

    OUT=/tmp python3 builder/panels.py            # -> /tmp/panels_qa.png
"""
import numpy as np
from PIL import Image

# ---------------------------------------------------------------- panel ids
# 0 = not garment. Dense and small: the runtime uses these to index per-panel angle/anchor
# tables, and the PNG that carries them is single-channel.
NONE, TORSO_L, TORSO_R, LAPEL_L, LAPEL_R, SLEEVE_L, SLEEVE_R, COLLAR, TROUSER = range(9)
N_PANELS = 9
NAMES = {NONE: "none", TORSO_L: "torso-L", TORSO_R: "torso-R", LAPEL_L: "lapel-L",
         LAPEL_R: "lapel-R", SLEEVE_L: "sleeve-L", SLEEVE_R: "sleeve-R",
         COLLAR: "collar", TROUSER: "trouser"}
# L/R here are SCREEN sides, not the wearer's — every angle table below is written in screen
# space because that is the space the compositor samples in.
VIZ = {TORSO_L: (70, 110, 200), TORSO_R: (90, 170, 230), LAPEL_L: (235, 110, 50),
       LAPEL_R: (245, 175, 60), SLEEVE_L: (120, 200, 120), SLEEVE_R: (70, 175, 110),
       COLLAR: (225, 70, 140), TROUSER: (150, 110, 190)}

# ---------------------------------------------------------------- THE GRAIN TABLE
# Degrees of rigid rotation applied to the cloth SAMPLING COORDINATE for each panel, indexed by
# panel id. Emitted into the compositor, so this list is the single place the grain is tuned.
#
# Sign: the sampler rotates by (u,v) = (x.cos+y.sin, -x.sin+y.cos), so a texture-vertical stripe
# lands on screen with slope dx/dy = -tan(theta). The screen-left lapel's roll line runs down and
# to the RIGHT (dx/dy > 0), so it takes a NEGATIVE angle, and the right lapel mirrors it.
#
# Provenance (plan/PATH_A_GRAIN_SPEC.md):
#   torso/trouser 0   — the existing normal-driven warp is already at Suitsupply parity. Leaving
#                       these at 0 makes the compositor's output bit-identical to before for every
#                       solid and every non-lapel pixel, which is the no-regression guarantee.
#   lapel +-16        — the spec's measured number was 11 (Suitsupply's photographic hero still),
#                       but Addendum 2 downgraded that to a FLOOR after finding 15-30 deg on real
#                       bespoke photography, and asked for a by-eye tune against the render. Done
#                       2026-07-23: 16 here MEASURES ~20 deg on the finished composite (see the
#                       calibration note below) — mid of that real-photo range. User-chosen from
#                       a rendered 0/11/16/22/28 sweep.
#   sleeve +-5        — the spec's step 3 said verify the EXISTING normal-driven warp against the
#                       +-5 target before writing new code, since Marigold's normal map is a real
#                       capture of the sleeve's own geometry and might already produce it.
#                       Verified 2026-07-23 with audit/panel_angles.py: it does not. The existing
#                       mechanism reads 0.0 to -2.5 deg and is NOT mirrored L/R, so an explicit
#                       rotation is required to reach the target.
#   collar 87         — near-horizontal. The undercollar is conventionally cut on the true bias
#                       for structural reasons (R1: 3-0 vote, 4+ independent tailoring sources);
#                       our own measurement of an isolated CDN collar sliver read -85 to -90.
#                       Verified on the finished composite: back-view collar measures +86.8 (sd
#                       7.7) against 0 before, so the table value lands essentially untouched.
#
# CALIBRATION — the table value is NOT the angle you see: the lapel measures about 4 deg steeper
# on the finished composite than the number here (lapel-L -19.9 against a table -16.0).
#
# ⚠ CORRECTED 2026-07-23. This note used to attribute that offset to the normal-driven pattern
# warp. That was wrong: with the warp amplitude set to ZERO the lapel still measures -19.9, so
# the warp contributes ~0 of it. The offset is the measurement itself — a structure-tensor angle
# over a tapered band picks up the lapel's own edges and the shading gradient along the roll
# line, not purely the cloth grain. Treat it as an estimator bias, not a compositor term.
# Re-measure with audit/panel_angles.py; never quote this table as the rendered result.
PANEL_ANGLES = [0.0] * N_PANELS
PANEL_ANGLES[LAPEL_L] = -16.0
PANEL_ANGLES[LAPEL_R] = +16.0
PANEL_ANGLES[SLEEVE_L] = -5.0
PANEL_ANGLES[SLEEVE_R] = +5.0
PANEL_ANGLES[COLLAR] = 87.0

# ---------------------------------------------------------------- tunables (garment-real units)
# Everything that is a real garment dimension is expressed in CM and scaled by px_per_cm, so the
# segmentation survives a change of render width the way the playbook's RSCALE rule requires.
LAPEL_CM      = 8.5    # visible lapel width, fold line to outer edge (notch, chest height)
COLLAR_CM     = 4.2    # collar band height at the neck
COLLAR_SPAN_CM = 21.0  # silhouette span at which the shoulders have taken over from the collar
COLLAR_H_MULT = 2.2    # hard ceiling on collar height, in COLLAR_CM (backstop for the side view,
                       # where the span grows slowly enough that the span rule alone runs long)
TORSO_FRAC    = 0.58   # torso half-width as a fraction of the full silhouette half-width at the
                       # chest (arms hang touching the body in this pose, so the armhole has to
                       # be placed geometrically — there is no gap to find). 13cm torso half vs
                       # ~24cm including the arm.
SHOULDER_FRAC = 0.88   # same fraction at the shoulder line, ramped down to TORSO_FRAC by the
                       # armpit, so the shoulder cap stays with the torso and the arm does not.
ARMPIT_FRAC   = 0.30   # armpit height as a fraction of shoulder->hem
GORGE_FRAC    = 0.45   # lapel width at the gorge, as a fraction of its full chest width


def _smooth(a, r):
    if r <= 0:
        return a.astype(float)
    k = np.ones(2 * r + 1) / (2 * r + 1)
    return np.convolve(np.pad(a.astype(float), r, "edge"), k, "same")[r:-r]


def _profile(b):
    """Per-row silhouette centre, half-width and area."""
    H, W = b.shape
    any_ = b.any(1)
    first = np.where(any_, np.argmax(b, 1), 0)
    last = np.where(any_, W - 1 - np.argmax(b[:, ::-1], 1), 0)
    cen = np.where(any_, (first + last) / 2.0, W / 2.0)
    hw = np.where(any_, (last - first) / 2.0, 0.0)
    return cen, hw, b.sum(1).astype(float)


def _runs(row):
    """[(x0, x1_inclusive), ...] of True runs in a 1-D boolean row."""
    d = np.diff(np.concatenate(([0], row.view(np.int8), [0])))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1))


def _interior(b):
    """Non-garment pixels with garment to their left AND right on the same row.

    A cheap stand-in for a flood fill (no scipy here): it is exactly right for the shirt V, which
    is bounded by the two lapels, and the places where it over-reaches (between the legs) are
    outside every window that uses it.
    """
    left = np.maximum.accumulate(b, axis=1)
    right = np.maximum.accumulate(b[:, ::-1], axis=1)[:, ::-1]
    return (~b) & left & right


def landmarks(render, b, px_per_cm):
    """Row landmarks shared by every view. All in canvas px."""
    H, W = b.shape
    cen, hw, area = _profile(b)
    r = max(3, int(round(0.9 * px_per_cm)))
    cenS, hwS, areaS = _smooth(cen, r), _smooth(hw, r), _smooth(area, r)

    rows = np.flatnonzero(b.any(1))
    top_y = int(rows[0]) if len(rows) else 0
    bot_y = int(rows[-1]) if len(rows) else H - 1

    # shoulder = where the silhouette first reaches most of its chest width
    chest_hw = hwS[top_y:int(H * 0.38)].max() if top_y < int(H * 0.38) else hwS.max()
    sh = np.flatnonzero(hwS[:int(H * 0.40)] >= 0.72 * chest_hw)
    shoulder_y = int(sh[0]) if len(sh) else int(H * 0.13)

    # jacket hem = the biggest drop in ROW AREA, not in half-width: the arms hang past the hem,
    # so the silhouette stays wide there and only the area (the jacket body) actually falls away.
    lo, hi = int(H * 0.30), int(H * 0.66)
    step = np.diff(areaS[lo:hi])
    hem_y = int(lo + int(np.argmin(step)) + 1) if len(step) else int(H * 0.48)

    armpit_y = shoulder_y + int(ARMPIT_FRAC * max(1, hem_y - shoulder_y))
    lm = dict(H=H, W=W, cen=cenS, hw=hwS, area=areaS, top_y=top_y, bot_y=bot_y,
              shoulder_y=shoulder_y, hem_y=hem_y, armpit_y=armpit_y, chest_hw=float(chest_hw))
    lm["collar_y"] = collar_bottom(b, lm, px_per_cm)
    return lm


def _corridor(lm):
    """Per-row half-width of the BODY (torso) corridor; garment outside it is sleeve."""
    H = lm["H"]
    f = np.full(H, TORSO_FRAC)
    sy, ay = lm["shoulder_y"], lm["armpit_y"]
    if ay > sy:
        f[sy:ay] = np.linspace(SHOULDER_FRAC, TORSO_FRAC, ay - sy)
    f[:sy] = SHOULDER_FRAC
    return f * lm["hw"]


def _sleeves(b, lm, panel):
    """Mark sleeve pixels.

    Above the hem the arm touches the body, so the armhole is placed geometrically (the corridor).
    Below the hem the arms are separated from the trousers by background, so the row's RUN
    structure gives it exactly: >=3 runs means the outermost two are arms. Below the wrist the
    runs drop to the two trouser legs and this stops firing on its own.
    """
    H, W = b.shape
    corr = _corridor(lm)
    cen, hw = lm["cen"], lm["hw"]
    yy, xx = np.mgrid[0:H, 0:W]
    c = cen[yy]
    geo = b & (np.abs(xx - c) > corr[yy]) & (yy >= lm["shoulder_y"]) & (yy < lm["hem_y"])
    panel[geo & (xx < c)] = SLEEVE_L
    panel[geo & (xx >= c)] = SLEEVE_R

    for y in range(lm["hem_y"], lm["bot_y"] + 1):
        rr = _runs(b[y])
        if len(rr) < 3:
            continue
        mids = [(x0 + x1) / 2.0 for x0, x1 in rr]
        li, ri = int(np.argmin(mids)), int(np.argmax(mids))
        for i, side in ((li, SLEEVE_L), (ri, SLEEVE_R)):
            x0, x1 = rr[i]
            if abs(mids[i] - cen[y]) > 0.45 * max(hw[y], 1):
                panel[y, x0:x1 + 1] = side


def _skin(render, b, lm):
    """Bare skin above the chest — the neck, jaw and ears. Clipped well above the hands."""
    H, W = b.shape
    a = np.asarray(render).astype(float)
    R, G, B = a[..., 0], a[..., 1], a[..., 2]
    s = (R > B + 16) & (R > G + 6) & (a.max(-1) / 255.0 > 0.33) & (~b)
    s[lm["shoulder_y"] + int(0.25 * max(1, lm["hem_y"] - lm["shoulder_y"])):] = False
    return s


def facing(render, b, lm):
    """+1 if the model faces screen-right, -1 if screen-left, 0 if square to camera.

    The face is the only reliable cue and it is a big, unambiguous blob of skin: compare its
    centroid against the garment's own centre line. Needed because the side renders do not all
    face the same way (1-button faces right, the rest face left).
    """
    s = _skin(render, b, lm)
    s = s[:lm["shoulder_y"]]                      # head only, not the neck
    if s.sum() < 200:
        return 0
    ys, xs = np.nonzero(s)
    d = xs.mean() - lm["cen"][:lm["shoulder_y"]][lm["hw"][:lm["shoulder_y"]] > 0].mean()
    lim = 0.10 * max(lm["chest_hw"], 1)
    return 0 if abs(d) < lim else (1 if d > 0 else -1)


def collar_bottom(b, lm, px_per_cm):
    """Row where the collar ends and the shoulders take over. See `_collar`."""
    H, W = b.shape
    top = lm["top_y"]
    span_cap = COLLAR_SPAN_CM * px_per_cm
    h_cap = int(round(COLLAR_H_MULT * COLLAR_CM * px_per_cm))
    bot = min(H - 1, top + h_cap)
    for y in range(top, min(H, top + h_cap + 1)):
        xs = np.flatnonzero(b[y])
        if len(xs) and xs[-1] - xs[0] > span_cap:
            return y - 1
    return bot


def _collar(b, lm, panel):
    """The collar band at the neck — the garment ABOVE the point where the shoulders take over.

    Purely geometric, which is what makes it work on all three views at once: in every one of
    them the topmost garment is the collar and it stays narrow until the shoulder line, so the
    row where the silhouette span first exceeds a collar's width is the collar's bottom edge. A
    first attempt keyed this off skin instead (find the neck, take the garment beside it) and it
    failed on exactly the cases you would expect — on the front view the neck is flanked by the
    SHIRT collar, not the jacket, so it selected a box with no garment in it at all.

    Deliberately conservative. A collar that leaked into the shoulder would put a near-horizontal
    grain on the shoulder, which is the one place a wrong grain reads as an obvious mistake.
    """
    top, bot = lm["top_y"], lm["collar_y"]
    if bot <= top:
        return
    sl = panel[top:bot + 1]
    sl[b[top:bot + 1]] = COLLAR


def _lapels(render, b, lm, panel, px_per_cm):
    """Front-view lapels, anchored on the shirt opening.

    The inner edge of a lapel is the roll line, which is very close to straight from the gorge to
    the break point — so fit a LINE to each side of the shirt opening and extrapolate. That keeps
    working where the opening is short or filled: the 3-piece (waistcoat behind the V, so only the
    top of the opening is bare shirt) and the double-breasted (small, high opening).
    """
    H, W = b.shape
    a = np.asarray(render).astype(float)
    mx, mn = a.max(-1), a.min(-1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    bright = (mx / 255.0 > 0.78) & (sat < 0.14)
    shirt = bright & _interior(b)
    # keep it to the opening: central band only, so the pocket square (also bright and enclosed)
    # and anything below the break point stay out
    yy, xx = np.mgrid[0:H, 0:W]
    shirt &= np.abs(xx - lm["cen"][yy]) < 0.32 * np.maximum(lm["hw"][yy], 1)
    shirt[:lm["top_y"]] = False
    shirt[int(H * 0.55):] = False
    ys = np.flatnonzero(shirt.any(1))
    if len(ys) < 8:
        return

    gorge_y, open_y = int(ys[0]), int(ys[-1])
    sy = np.arange(gorge_y, open_y + 1)
    lx = np.array([np.flatnonzero(shirt[y])[0] if shirt[y].any() else np.nan for y in sy], float)
    rx = np.array([np.flatnonzero(shirt[y])[-1] if shirt[y].any() else np.nan for y in sy], float)
    ok = ~np.isnan(lx)
    if ok.sum() < 8:
        return
    # fit the roll line over the lower 2/3 of the opening — the top few rows are the collar
    # notch, which is not on the roll line
    fit = ok & (sy >= gorge_y + 0.30 * (open_y - gorge_y))
    if fit.sum() < 6:
        fit = ok
    pl = np.polyfit(sy[fit], lx[fit], 1)
    pr = np.polyfit(sy[fit], rx[fit], 1)

    # The lapel runs from the gorge down to the BREAK POINT, which is where the two roll lines
    # converge on the top button. Stopping there is what keeps the two bands from crossing over
    # into an X below the button — extrapolating them any further is meaningless.
    wide = int(round(LAPEL_CM * px_per_cm))
    y_cap = lm["shoulder_y"] + int(0.75 * max(1, lm["hem_y"] - lm["shoulder_y"]))
    for y in range(gorge_y, min(H, y_cap + 1)):
        lxi, rxi = np.polyval(pl, y), np.polyval(pr, y)
        if rxi - lxi < 0.10 * wide:            # roll lines have met: past the break point
            break
        # A real lapel is narrow at the gorge and reaches full width by the chest. Without the
        # taper the top of the band squares off across the shoulder beside the collar.
        t = (y - gorge_y) / max(1.0, 0.35 * (y_cap - gorge_y))
        wide_y = int(round(wide * min(1.0, GORGE_FRAC + (1 - GORGE_FRAC) * t)))
        a0, a1 = int(round(lxi - wide_y)), int(round(lxi))
        if a1 > a0:
            seg = np.zeros(W, bool); seg[max(0, a0):max(0, a1)] = True
            panel[y, seg & b[y]] = LAPEL_L
        c0, c1 = int(round(rxi)), int(round(rxi + wide_y))
        if c1 > c0:
            seg = np.zeros(W, bool); seg[max(0, c0):min(W, c1)] = True
            panel[y, seg & b[y]] = LAPEL_R


def _side_lapel(b, lm, panel, px_per_cm, face):
    """Side view: the lapel is the strip at the FRONT silhouette edge of the chest.

    Foreshortened to roughly half its face-on width. Deliberately conservative — leaving a strip
    as torso (grain 0) is a much smaller error than tilting a strip of chest that is not lapel.
    """
    if face == 0:
        return
    H, W = b.shape
    y0 = lm["collar_y"]
    y1 = lm["shoulder_y"] + int(0.62 * max(1, lm["hem_y"] - lm["shoulder_y"]))
    wide = int(round(LAPEL_CM * 0.45 * px_per_cm))
    pid = LAPEL_R if face > 0 else LAPEL_L
    for y in range(max(0, y0), min(H, y1 + 1)):
        xs = np.flatnonzero(b[y])
        if not len(xs):
            continue
        if face > 0:
            a0, a1 = int(xs[-1]) - wide, int(xs[-1])
        else:
            a0, a1 = int(xs[0]), int(xs[0]) + wide
        seg = np.zeros(W, bool); seg[max(0, a0):min(W, a1 + 1)] = True
        panel[y, seg & b[y]] = pid


def segment(render, mask_L, view, px_per_cm):
    """render: RGB PIL at canvas size. mask_L: 'L' coverage mask, same size.
    Returns (panel uint8 HxW, landmarks dict)."""
    b = np.asarray(mask_L.convert("L")) > 127
    lm = landmarks(render, b, px_per_cm)
    H, W = b.shape
    panel = np.zeros((H, W), np.uint8)

    yy, xx = np.mgrid[0:H, 0:W]
    c = lm["cen"][yy]
    jacket = b & (yy < lm["hem_y"])
    panel[jacket & (xx < c)] = TORSO_L
    panel[jacket & (xx >= c)] = TORSO_R
    panel[b & (yy >= lm["hem_y"])] = TROUSER

    # The side view gets no sleeve. Seen in profile the arm hangs in FRONT of the torso in depth,
    # so it occupies the middle of the silhouette, not its edges — the corridor rule that is right
    # on the front and back marks the front and back edges instead, which is simply wrong. Since
    # the sleeve's own grain is still 0 pending the spec's verify-first step, leaving it as torso
    # costs nothing today and is honest about what has actually been segmented.
    if view != "side":
        _sleeves(b, lm, panel)
    face = facing(render, b, lm)
    if view == "front":
        _lapels(render, b, lm, panel, px_per_cm)
    elif view == "side":
        _side_lapel(b, lm, panel, px_per_cm, face)
    _collar(b, lm, panel)                      # last: the collar is small and well located, and
                                               # its near-horizontal grain must not be overwritten
    lm["facing"] = face
    return panel, lm


def anchors(panel, lm):
    """Rotation anchor per panel, in canvas px.

    A rigid rotation of the sampling coordinate has to turn about SOMETHING, and the choice is
    not cosmetic: the pattern is unmoved at the anchor and rotates around it, so the anchor is
    also the panel's phase anchor. Per the grain spec's seam rules:
      lapel  -> its own centroid (no seam rule to satisfy; keeps the pattern registered where the
                lapel actually is instead of translating it by an arbitrary amount)
      sleeve -> the armhole at chest height, which is the ONE line the spec says a sleeve must
                match the body on ("non-negotiable in quality construction", free elsewhere)
      collar -> its own centroid
    """
    H, W = panel.shape
    out = {}
    for pid in range(1, N_PANELS):
        m = panel == pid
        if not m.any():
            out[pid] = (W / 2.0, H / 2.0)
            continue
        ys, xs = np.nonzero(m)
        out[pid] = (float(xs.mean()), float(ys.mean()))
    for pid in (SLEEVE_L, SLEEVE_R):
        m = panel == pid
        if not m.any():
            continue
        y = min(H - 1, lm["armpit_y"])
        row = np.flatnonzero(m[y])
        if len(row):
            x = row[-1] if pid == SLEEVE_L else row[0]   # the edge that meets the body
            out[pid] = (float(x), float(y))
    return out


def overlay(render, panel, alpha=0.62):
    a = np.asarray(render).astype(float).copy()
    for pid, col in VIZ.items():
        m = panel == pid
        if m.any():
            a[m] = a[m] * (1 - alpha) + np.array(col, float) * alpha
    return Image.fromarray(np.clip(a, 0, 255).astype("uint8"))


if __name__ == "__main__":
    import os, sys
    HM = "/Users/runiwillner/Desktop/GCC_House_Model"
    sys.path.insert(0, f"{HM}/builder")
    OUT = os.environ.get("OUT", "/tmp")
    W = 1300
    CUTS = ["2button_notch", "2button_peak", "1button_peak", "doublebreasted", "3piece_vest"]
    tiles = []
    for base in CUTS:
        for view in ("front", "side", "back"):
            fn = f"{view}_{base}"
            rp, dp = f"{HM}/renders/{fn}.png", f"{HM}/drape_maps/{fn}_drape.png"
            if not (os.path.exists(rp) and os.path.exists(dp)):
                continue
            la = Image.open(dp)
            H_FULL = int(W * la.height / la.width)
            px_per_cm = (0.93 * H_FULL) / 183.0
            render = Image.open(rp).convert("RGB").resize((W, H_FULL), Image.LANCZOS)
            mask = la.split()[1].resize((W, H_FULL), Image.LANCZOS)
            panel, lm = segment(render, mask, view, px_per_cm)
            counts = {NAMES[p]: int((panel == p).sum()) for p in range(1, N_PANELS)}
            print(f"{fn:26s} shoulder={lm['shoulder_y']:4d} armpit={lm['armpit_y']:4d} "
                  f"hem={lm['hem_y']:4d} face={lm['facing']:+d}  " +
                  " ".join(f"{k}={v//1000}k" for k, v in counts.items() if v))
            tiles.append((fn, overlay(render, panel)))
    h = 660
    tiles = [(n, im.resize((int(im.width * h / im.height), h), Image.LANCZOS)) for n, im in tiles]
    per = 5
    rows = [tiles[i:i + per] for i in range(0, len(tiles), per)]
    Wt = max(sum(im.width for _, im in r) for r in rows)
    sheet = Image.new("RGB", (Wt, h * len(rows)), (20, 20, 22))
    for j, r in enumerate(rows):
        x = 0
        for _, im in r:
            sheet.paste(im, (x, j * h)); x += im.width
    sheet.save(f"{OUT}/panels_qa.png")
    print(f"wrote {OUT}/panels_qa.png")


# ==================================================================== CYLINDRICAL UNWRAP
# Real suit photography does NOT show ruled-straight stripes: the pattern compresses toward each
# panel's silhouette as the cloth turns away from camera. Measured on a Suitsupply chalk-stripe
# photo, local stripe pitch falls monotonically to ~0.70 of its centre value by |d|/R = 0.75 and
# then FLOORS (it does not go to zero at the edge, because the visible garment edge is a draped
# panel edge, not the tangent point of a smooth body).
#
# So the cloth coordinate advances by ARC LENGTH along the surface, not by screen distance:
#     dU/dx = 1 / max( sqrt(1 - ((x-C)/R)^2), F )
# whose exact integral is asin() out to t = sqrt(1-F^2) and LINEAR beyond. F floors |nz|, which
# bounds dU/dx at 1/F and removes the singularity at the silhouette.
#
# ⚠ NEVER CLIP t TO ±1. That is the obvious defensive move and it is a trap: it makes U CONSTANT
# wherever a panel reaches past its own cylinder radius, i.e. dU/dx = 0 — the tile gets sampled at
# a single column and the shoulder caps render as a horizontal smeared band. The linear branch
# already bounds dU/dx, so letting |t| exceed 1 is both safe and the only monotone choice.
#
# This is the idea the disabled SIL_WRAP was reaching for. SIL_WRAP was rejected because it used
# the WHOLE-ROW silhouette, so the sleeves — separate tubes with no background gap to the body in
# this pose — were sheared as if they were the torso. Its own comment said it "needs per-panel
# centre/width before it can be enabled". That is exactly what the panel map above now provides,
# and SIL_WRAP was additionally only an affine taper, which can reproduce splay but never
# intra-row compression.
NZ_FLOOR      = 0.70   # floor on |nz| -> max compression 1/F = 1.43x
TORSO_R_FRAC  = 0.70   # torso cylinder radius as a fraction of the FULL silhouette half-width.
                       # NOT the torso panel's own half-width: the body continues behind the arms.
                       # Three independent estimates cluster here — the arm/body drape crease
                       # reads 0.644-0.730, a normal-map cylinder fit 0.69, and matching the
                       # reference jacket's physical body half-width 0.64-0.67.
TORSO_R_FRAC_SIDE = 1.00   # in profile BOTH torso edges are true silhouettes
SLEEVE_RHO    = 1.00   # a sleeve's outer edge IS a silhouette on 100% of rows
LEG_RHO       = 1.00
DEG_CEN, DEG_R = 3, 3  # polynomial order for C(y) / R(y)
TRIM_TOP, TRIM_BOT = 40, 25   # rows dropped from the FIT (still evaluated) at each panel end
MIN_LEG_PX    = 18     # a trouser run narrower than this is an occluded sliver
MIN_LEG_FRAC  = 0.28   # ...or narrower than this fraction of the row's whole trouser span
LEG_PERSIST   = 12     # ...or not persisting this many rows. All three kill the side view's
                       # far-leg ankle sliver, which otherwise extrapolates a 40-row support
                       # over 600 rows and folds the map.


def arc(t, F=NZ_FLOOR):
    """Clamped arc length in units of R. Strictly increasing for ALL t — see the note above."""
    tc = np.sqrt(max(1e-9, 1.0 - F * F))
    a = np.abs(t)
    return np.sign(t) * np.where(a <= tc, np.arcsin(np.minimum(a, tc)),
                                 np.arcsin(tc) + (a - tc) / F)


def _fit(rows, vals, deg):
    ok = np.isfinite(vals)
    if ok.sum() < deg + 2:
        return None
    return (np.polyfit(rows[ok], vals[ok], deg), float(rows[ok].min()), float(rows[ok].max()))


def _ev(fit, yy, H):
    """Evaluate with the row argument CLAMPED to the fit interval. Extrapolating a cubic past the
    shoulder was measured as the single biggest source of injected tilt (3.9-4.2% of front-torso
    pixels over 10 deg before this clamp, ~0 after)."""
    if fit is None:
        return np.full(H, np.nan)
    p, y0, y1 = fit
    return np.polyval(p, np.clip(yy, y0, y1))


def _runs_row(row, minpx):
    d = np.diff(np.concatenate(([0], row.view(np.int8), [0])))
    return [(a, b) for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1) - 1)
            if b - a >= minpx]


def cylinders(panel, b, view):
    """Per-cylinder projected axis C(y) and radius R(y), in canvas px, one entry per row.

    Returns {name: (C, R)} plus PANEL_CYL mapping panel ids onto those names. Profiles come from
    a low-order FIT over the panel interior, never from per-row extents: a per-row min/max is
    invalid the moment a panel is multi-run (true on ~10% of torso rows and most trouser rows),
    where one stray pixel swings the measured centre by tens of px and injects a huge false tilt.
    Boxcar smoothing does not fix that — it turns a one-row tear into a multi-row S-bend.
    """
    H, W = panel.shape
    yy = np.arange(H, dtype=np.float64)
    out = {}

    # ---- TORSO: both halves plus the lapels ride ONE body cylinder. The front-opening phase
    # break is SEAM_PHASE's job, not the geometry's.
    mt = np.isin(panel, [TORSO_L, TORSO_R, LAPEL_L, LAPEL_R])
    rows = np.flatnonzero(mt.sum(1) > 25).astype(float)
    if len(rows) > 80:
        cen = np.array([np.flatnonzero(mt[int(y)]).mean() for y in rows])
        shw = np.array([(lambda z: (z[-1] - z[0]) / 2.0 if len(z) > 4 else np.nan)
                        (np.flatnonzero(b[int(y)])) for y in rows])
        inn = (rows > rows[0] + TRIM_TOP) & (rows < rows[-1] - TRIM_BOT)
        if inn.sum() > DEG_R + 2:
            frac = TORSO_R_FRAC_SIDE if view == "side" else TORSO_R_FRAC
            C = _ev(_fit(rows[inn], cen[inn], DEG_CEN), yy, H)
            R = np.maximum(_ev(_fit(rows[inn], shw[inn] * frac, DEG_R), yy, H), 20.0)
            out["torso"] = (C, R)

    # ---- SLEEVES: each anchored on its OWN outer silhouette edge. This is the whole reason
    # SIL_WRAP failed; with per-sleeve geometry the sleeve displacement p95 drops from 52.5 px
    # (197% of a stripe period) to 7.0 px (26%).
    for pid, side, name in ((SLEEVE_L, "L", "sleeveL"), (SLEEVE_R, "R", "sleeveR")):
        m = panel == pid
        rws = np.flatnonzero(m.sum(1) > 25).astype(float)
        if len(rws) < 60:
            continue
        edge, half = [], []
        for y in rws:
            rr = _runs_row(m[int(y)], 6)
            if not rr:
                edge.append(np.nan); half.append(np.nan); continue
            a, c = max(rr, key=lambda r: r[1] - r[0])          # largest run, never min/max
            edge.append(a if side == "L" else c); half.append((c - a) / 2.0)
        edge = np.array(edge, float); half = np.array(half, float)
        inn = (rws > rws[0] + 30) & (rws < rws[-1] - 30)
        if inn.sum() < 8:
            continue
        Xo = _ev(_fit(rws[inn], edge[inn], 4), yy, H)
        Rs = np.maximum(_ev(_fit(rws[inn], half[inn], 4), yy, H), 8.0) * SLEEVE_RHO
        out[name] = (Xo + (Rs if side == "L" else -Rs), Rs)

    # ---- TROUSER: one seat cylinder above the crotch, two leg cylinders below. HARD switch at
    # the crotch, never a cross-fade — a convex blend of two different cylinder fields is
    # non-monotone by construction (measured: 108 folded pixels, a 178.9 deg lean). The residual
    # is a phase break on the fly line, which is where a real trouser has a seam anyway.
    mtr = panel == TROUSER
    if mtr.any():
        legs, seat, run2 = {0: [], 1: []}, [], 0
        crotch = None
        for y in range(H):
            if not mtr[y].any():
                continue
            span = np.flatnonzero(mtr[y])
            total = span[-1] - span[0]
            rr = [r for r in _runs_row(mtr[y], MIN_LEG_PX)
                  if (r[1] - r[0]) >= MIN_LEG_FRAC * max(total, 1)]
            if len(rr) >= 2:
                run2 += 1
                if crotch is None and run2 >= LEG_PERSIST:
                    crotch = y - LEG_PERSIST + 1
                rr = sorted(sorted(rr, key=lambda r: r[1] - r[0])[-2:])
                for k, (a, c) in enumerate(rr):
                    legs[k].append((y, (a + c) / 2.0, (c - a) / 2.0))
            else:
                run2 = 0
                if rr:
                    a, c = rr[0]
                    seat.append((y, (a + c) / 2.0, (c - a) / 2.0))
        for k in (0, 1):
            v = np.array(legs[k], float)
            if len(v) < 40:
                continue
            r = v[:, 0]
            inn = (r > r[0] + 12) & (r < r[-1] - 12)
            if inn.sum() < 20:
                inn = np.ones(len(r), bool)
            out[f"leg{k}"] = (_ev(_fit(r[inn], v[inn, 1], 2), yy, H),
                              np.maximum(_ev(_fit(r[inn], v[inn, 2], 2), yy, H), 8.0) * LEG_RHO)
        if len(seat) >= 20:
            v = np.array(seat, float)
            out["seat"] = (_ev(_fit(v[:, 0], v[:, 1], 2), yy, H),
                           np.maximum(_ev(_fit(v[:, 0], v[:, 2], 2), yy, H), 8.0) * LEG_RHO)
        out["_crotch"] = float(crotch if crotch is not None else H)
    return out


# panel id -> cylinder name. COLLAR is identity: it is tiny, near the neck, and already carries a
# near-perpendicular Path A rotation.
PANEL_CYL = {TORSO_L: "torso", TORSO_R: "torso", LAPEL_L: "torso", LAPEL_R: "torso",
             SLEEVE_L: "sleeveL", SLEEVE_R: "sleeveR", TROUSER: "trouser", COLLAR: None}
