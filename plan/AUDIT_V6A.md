# v6a grain + pattern audit — 2026-07-23

23-agent audit (6 measurement lenses, adversarial verification, my own independent
structure-tensor pass as a third source). 35 axes clean, 4 findings confirmed, 4 refuted as
measurement artifacts. All three confirmed defects were FIXED the same day — see the addendum.

AUDIT VERDICT — front_2button_notch hero (v6a), 10 fabrics, 1300x1733

**1. Verdict**

Yes — every panel is cut in the correct direction. All eight panels measure at their table grain angle within estimator tolerance, on every fabric that carries enough contrast to measure: torso and trousers vertical, lapels leaning -16/+16 and properly mirrored (never parallel), sleeves -5/+5 mirrored, collar near-horizontal. The chest-spill defect you caught is fixed and did not overcorrect — the lapel faces still show leaning stripes, and the chest is dead vertical right up to the lapel-edge crease on all four stripe fabrics and all four checks. The rendering, however, is NOT fully correct: one new defect survived every verification pass — a full-width stripe phase cut across both trouser thighs at the crotch row (y=968), blatant at display size on the bold navy chalk. That, plus two shading-layer blemishes (unrelated to grain), is the complete defect list. Grain: pass. Rendering: one blocker on the trousers.

**2. Panel-by-panel grain results**

| Panel | Table angle | Measured (worst fabric noted) | Mirrored? | Result |
|---|---|---|---|---|
| Torso-L (1) | 0 | -0.4 to +1.1 deg across 4 stripes; checks 0 +/- 1.3 | — | PASS |
| Torso-R (2) | 0 | -0.4 to +2.8 deg (DBS175A +2.8, low-contrast) | — | PASS |
| Lapel-L (3) | -16 | -15.4 to -20.4 (within documented -16..-20 bias envelope) | Yes, vs Lapel-R on all 8 patterned fabrics | PASS |
| Lapel-R (4) | +16 | +15.4 to +21.0 | Yes | PASS |
| Sleeve-L (5) | -5 | -5.2 to -5.9 (DBS175A unreadable, faint chalk) | Yes | PASS |
| Sleeve-R (6) | +5 | +4.4 to +6.0 | Yes | PASS |
| Collar (7) | 87 | Too small for tensor (452 px); visually near-horizontal in 3x crop | — | PASS (visual) |
| Trouser (8), both legs | 0 | -0.4 to +1.8 deg | — | PASS on angle; FAIL on phase continuity at crotch (below) |

Check fabrics: both axes rotate together on the lapel band (rotation 16.5-17.7 deg, matching table), horizontals stay level (worst -1.3 deg) and continuous on the torso, no moire on any of the four. Arc-length compression is smooth and monotone toward every silhouette (stripe period 25-26px at panel centre tightening to 19-21px at edges) — the intended physics, no mid-panel spacing jumps. Front-opening phase break sits exactly at the opening edge (x862-866), nowhere else.

**3. Confirmed defects, ranked**

DEFECT 1 — BLOCKER. Trouser crotch-row phase cut. A straight horizontal line at y=966-968 spanning x~642-1072 severs every stripe across BOTH thigh fronts, on open cloth ~100px below the jacket hem. Left leg restarts shifted -2.5 to -7px, right leg +2 to +3px (opposite-signed per leg), confirmed by row-pair correlation collapse (0.99 baseline to ~0.0 on DBT6860), FFT phase tracking, and stripe-centroid tracking; the solid shows nothing at that row, so it is pure pattern phase. Visible in a 10-second look at 900px display height on DBT6860; present but fainter on the other three stripes. Cause: the unwrap restarts parameterization at the crotch (hip cylinder above, per-leg cylinders below) without phase-matching. Fix: seed each leg's below-crotch arc-length phase per column from the above-crotch value at y=968 (the same continuity constraint already used at the front opening), and add a regression test on the row pair (crotch-1, crotch) — the standard per-leg scan splits at 968 and never tests that pair, which is how this escaped.

DEFECT 2 — VISIBLE (light fabrics only). Dark smear marks baked into the shading layer: hard-edged near-black comma/streak marks on both trouser legs just above the shoes (left y1440-1462 x738-768, right y1445-1499 x930-974; luminance dips to single digits), plus a shoulder tick and two chest hairlines. Identical pixels on all 10 fabrics including the solid, so shading-layer, not grain. Invisible on navy/black; on DBV196A silver glen they read as ink stains at display size. Fix: retouch the base shading layer at those coordinates and clamp the shading multiply so it never drops more than ~50% below local cloth luminance.

DEFECT 3 — MINOR. Granular speckle on the soft edge of the floor shadow left of the shoes (y1480-1619 x471-699) — dither grain on the shadow gradient, off-garment, faint dust-like texture at 100%. Fix if shipping pixel-clean: 2-3px gaussian on the shadow alpha.

(The two crotch findings from separate lenses are the same defect; counted once above.)

**4. Checked and clean (35 axes)**

Grain angles all 8 panels x 4 stripe fabrics with shading-excluded structure tensor; lapel mirroring and band coverage (no chest spill, no vertical-lapel overcoverage) on stripes and checks; check-fabric axis rotation, horizontal-line levelness, grid continuity, lapel-edge crease sharpness, and moire on all four checks; row-to-row and column continuity across torso, sleeves, thighs (zero mid-cloth breaks — every correlation dip localizes to a real garment feature: pockets, buttons, welts, gorge); front-opening phase break location; unwrap compression profiles (torso, trousers, sleeves); both prior regressions (0.46H seam cut, thigh orphan dashes) stay dead; both prior stage bugs (white smear, cloth patch by shoe) stay dead; no grey base bleed inside the garment mask (0-2 stray px); background flat at 239 +/- 0.23; contact shadow soft; no silhouette halo beyond a 1px sharpening ring; arm-torso gaps clean. Four scary-looking raw readings were run down and refuted as measurement artifacts (DBS175A "unreliability", torso-R ripple, trouser-hem and collar "bleed") — the solid-fabric control and cross-fabric pixel-identity attribute all of them to legitimate base-render shading. One systematic note, not a defect: bias-free phase estimators read all lapels ~3 deg shallower than the 16-deg table, uniformly on every fabric and both sides — a render-path property to be aware of, invisible to the eye.

**5. Go/no-go on deriving the other 9 cut-views**

NO-GO as it stands; GO once one fix lands. The grain system — panel angles, mirroring, lapel band edge detection, unwrap compression, front-opening phase — is verified correct and is exactly the machinery the other 9 views inherit, so there is no reason to rework anything there. But the crotch phase cut lives in the shared trouser unwrap and will replicate into every view that shows trousers, on all 4 stripe fabrics. Conditions for GO: (1) fix the crotch phase continuity and re-verify with the (crotch-1, crotch) row-pair test on DBT6860 — this is the gate; (2) retouch the shading-layer smears in the base renders before deriving, since each view's base layer carries its own retouch and the marks currently ruin light fabrics like DBV196A; (3) the shadow speckle is optional polish. With the crotch fix verified, derive all 9 with confidence — stripes, the hardest class, are otherwise rendering correctly everywhere we could measure and everywhere we looked.

---

## ADDENDUM — all three defects fixed same day (commit follows this file)

1. **Crotch phase cut (BLOCKER)** — root cause: the seat→legs cylinder switch changes C/R, so
   the unwrapped coordinate jumps by a different amount at every column. A constant per-leg
   offset was tried first and left ±2–3 px of residual (gate 0.08 → 0.18 only). The shipped fix
   is the full per-column continuity field: `buildLegDeltas` precomputes
   Δ(x) = U_seat(x) − U_leg(x) at the crotch row once per cut-view, and the sampler adds Δ(x)
   below the crotch. **Gate result: row-pair correlation 0.08 → 0.99** against a 0.97–0.98
   baseline; trouser grain unchanged (−0.03° → −0.04°); stripes visually continuous through
   the crotch on DBT6860.
2. **Ink-stain marks (VISIBLE on light cloths)** — five dark blemishes baked into the v6a
   generation, inpainted from surrounding cloth in the base render (backup kept as
   `renders/front_2button_notch.pre-retouch.png`); drape regenerated. The left-shin mark sat in
   a deep shadow zone and needed a second pass with a local threshold. Both shins now min 41
   (was 1 and 7) and the natural fold shadows survive.
3. **Shadow speckle (MINOR)** — the on_stage near-test dithered at the contact shadow's soft
   edge. Fixed by consolidating the background matte (Max/Min close) and feathering 1.0 → 2.5.

The audit's GO conditions for deriving the other 9 cut-views are all met.
