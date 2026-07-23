        # NO AUTOMATED GORGE CHECK — and that is a deliberate, tested decision, not an omission.
        # Three metrics were tried against a known-broken render (right gorge entirely missing)
        # and its retouched twin: total edge energy in the gorge band read 0.89-1.00 on BOTH;
        # largest-connected-component with a per-side percentile threshold read 0.99 on the
        # broken one and 0.61 on the FIXED one (backwards); with a shared absolute threshold,
        # 0.68 vs 0.68 (no signal). Every variant locks onto the lapel's outer edge and the
        # shoulder line, which are present whether or not the gorge was drawn.
        # A check that reports PASS on a render with no right gorge is worse than no check, so
        # there isn't one. The gorge is verified BY EYE — see builder/fix_gorge.py, which writes
        # a before/after sheet, and crop the collar of any new front render at 3x and look.

#!/usr/bin/env python3
"""Acceptance check for a newly generated house-model render.

Run this the moment a render comes out of Gemini, BEFORE spending time on masks, drape maps
or Marigold. Every check below corresponds to something that silently breaks the compositor
downstream if it drifts.

    python3 check_render.py <render.png> [more.png ...]

Exit code 0 = all pass. Anything else = regenerate.
"""
import sys
import numpy as np
from PIL import Image

# --- the spec, derived from the approved reference render -------------------
ASPECT        = 3 / 4          # portrait 3:4
ASPECT_TOL    = 0.01
MIN_WIDTH     = 1600
FIGURE_FRAC   = 0.898          # head to sole, firm threshold, of frame height
FIGURE_TOL    = 0.02           # PX_PER_CM depends on this — 2% is already 2% of cloth scale
CENTRE_TOL    = 0.03           # figure centre vs frame centre, as a fraction of width
BG_MIN_V      = 0.93           # near-white sweep
BG_MAX_S      = 0.05
BG_MAX_STD    = 4.0            # levels; the sweep must be flat, not gradient-lit
GARMENT_MAX_S = 0.12           # mid-grey, not a coloured suit
GARMENT_RANGE = 90             # p1..p99 spread in the garment; this becomes the drape map
CLIP_MAX      = 0.002          # fraction of garment pixels crushed to black
SHOE_WARMTH   = 12             # mean (R-B) in the shoe region; brown fails, black passes


# SYMMETRY thresholds (2026-07-23). Deliberately loose and WARN-only for now — see the note at
# the checks themselves. Baselines measured across the 15 shipped cut-views.
LR_LUM_MAX     = 8.0    # max |right - left| garment mean luminance, sRGB levels


def analyse(path):
    img = Image.open(path).convert("RGB")
    a = np.asarray(img).astype(np.float32)
    h, w, _ = a.shape
    R, B = a[..., 0], a[..., 2]
    mx, mn = a.max(-1), a.min(-1)
    V = mx / 255.0
    S = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    lum = a.mean(-1)

    out = []
    ok = lambda name, cond, detail: out.append((cond, name, detail))

    def warn(name, good, detail):
        out.append((True, ("WARN " if not good else "") + name,
                    detail + ("   <-- LOOK AT THIS" if not good else "")))

    ok("resolution", w >= MIN_WIDTH, f"{w}x{h} (min width {MIN_WIDTH})")
    ok("aspect 3:4", abs(w / h - ASPECT) < ASPECT_TOL, f"{w/h:.4f} vs {ASPECT:.4f}")

    # figure geometry — firm threshold so the floor shadow is excluded
    fg = (255 - a).sum(-1) > 150
    rows = np.where(fg.sum(1) > 3)[0]
    cols = np.where(fg.sum(0) > 3)[0]
    if len(rows) < 10:
        ok("figure found", False, "no figure detected")
        return img, out
    frac = (rows[-1] - rows[0]) / h
    # centre from rows ABOVE the shoe/shadow band — a long floor shadow fooled this into
    # passing an off-centre figure (2026-07-23)
    body = fg[: rows[0] + int(0.86 * (rows[-1] - rows[0])), :]
    bc = np.where(body.sum(0) > 3)[0]
    ctr = (((bc[0] + bc[-1]) / 2) / w) if len(bc) > 10 else ((cols[0] + cols[-1]) / 2) / w
    ok("figure height", abs(frac - FIGURE_FRAC) <= FIGURE_TOL,
       f"{frac:.3f} (target {FIGURE_FRAC} +/- {FIGURE_TOL})")
    ok("figure centred", abs(ctr - 0.5) <= CENTRE_TOL, f"centre at {ctr:.3f}")

    # background sweep
    bg = (V > BG_MIN_V) & (S < BG_MAX_S)
    edge = np.zeros_like(bg); edge[:40] = edge[-40:] = True; edge[:, :40] = edge[:, -40:] = True
    ok("background is a clean sweep", bg[edge].mean() > 0.90,
       f"{bg[edge].mean():.1%} of the frame border is clean white")
    ok("sweep is flat", lum[bg].std() < BG_MAX_STD if bg.sum() else False,
       f"std {lum[bg].std():.2f} levels (max {BG_MAX_STD})")

    # garment: dark-ish, neutral, in the middle of the figure
    g = (V < 0.55) & (B >= R - 8) & ~bg
    g[: int(h * 0.12), :] = False
    g[int(h * 0.86):, :] = False
    if g.sum() < 5000:
        ok("garment found", False, f"only {g.sum()} px")
        return img, out
    p1, p99 = np.percentile(lum[g], [1, 99])
    ok("garment is neutral (not a coloured suit)", S[g].mean() < GARMENT_MAX_S,
       f"mean saturation {S[g].mean():.3f} (max {GARMENT_MAX_S})")
    ok("garment tonal range", (p99 - p1) >= GARMENT_RANGE,
       f"p1..p99 = {p1:.0f}..{p99:.0f} = {p99-p1:.0f} levels (min {GARMENT_RANGE})")
    ok("garment not crushed", np.mean(lum[g] <= 1) < CLIP_MAX,
       f"{np.mean(lum[g] <= 1):.4%} of garment at pure black")

    # shoes must read black, not brown
    sh = (R > a[..., 1] + 8) & (a[..., 1] >= B) & (S > 0.18) & (mx > 25)
    sh[: int(h * 0.86), :] = False
    warmth = float((R[sh] - B[sh]).mean()) if sh.sum() > 500 else 0.0
    ok("shoes are black, not brown", sh.sum() < 500 or warmth < SHOE_WARMTH,
       f"{sh.sum():,} warm px, mean R-B {warmth:.1f} (max {SHOE_WARMTH})")

    # ---- SYMMETRY (added 2026-07-23) --------------------------------------------------------
    # These exist because the generator shipped a defect through ten straight generations and not
    # one of the checks above could see it: it invented a key light from screen-right (+20.6 to
    # +24.4 sRGB levels on every front) and then never drew the lapel's gorge cut on that side
    # (a 535 px connected seam on the left against 203 px of scatter on the right). A garment is
    # very nearly left/right symmetric; nothing above tested that.
    #
    # Shipped as WARN, not FAIL: every existing render fails a naive symmetry bar because the
    # bias is universal, and the pocket square + the left-over-right front overlap are REAL
    # asymmetries. Tighten to a hard gate once a clean generation sets a baseline.
    gl = g[:, : w // 2]
    gr = g[:, w // 2:]
    if gl.sum() > 1000 and gr.sum() > 1000:
        dl = float(lum[:, : w // 2][gl].mean())   # lum is already 0..255
        dr = float(lum[:, w // 2:][gr].mean())
        warn("garment lighting is left/right balanced", abs(dr - dl) <= LR_LUM_MAX,
             f"right minus left = {dr - dl:+.1f} levels (max {LR_LUM_MAX})")

    return img, out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    failed = 0
    for p in sys.argv[1:]:
        print(f"\n=== {p} ===")
        try:
            _, res = analyse(p)
        except Exception as e:
            print(f"  ERROR {e}"); failed += 1; continue
        for good, name, detail in res:
            print(f"  {'PASS' if good else 'FAIL'}  {name:38s} {detail}")
            if not good:
                failed += 1
    print(f"\n{'ALL CHECKS PASSED' if not failed else str(failed) + ' CHECK(S) FAILED — regenerate'}")
    sys.exit(0 if not failed else 1)
