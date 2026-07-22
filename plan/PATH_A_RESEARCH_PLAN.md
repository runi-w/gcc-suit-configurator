# Deep research → Path A per-panel suit-pattern wrap

## Context

We're building **Path A**: live, per-panel pattern wrap in the runtime compositor so directional
patterns (pinstripe, chalk stripe, windowpane, glen/Prince-of-Wales, houndstooth) run in the
*correct direction on each garment panel* — vertical on the torso, correct on the lapel, following
each sleeve, breaking at seams — the thing Suitsupply gets by baking one photo per fabric.

A **prototype** this session (Python, on the notch-front render) proved the mechanism is feasible:
segment the garment into panels and give each its own stripe grain → lapels came out diagonal,
torso vertical. But the **angles were guessed** (lapel 20°, sleeve 6°) and, more fundamentally, the
**model of *why* each panel tilts is unresolved**. Before spending ~2 weeks polishing, we want a
deep, suit-specific research pass to pin down the *correct* target, so we build the right thing.

**User decisions:** run the research **in-thread now** (not a separate session); cover **all
directional patterns** (stripes + checks/windowpane/glen/houndstooth), not just pinstripes.

## What's already settled (do NOT re-open — from HANDOVER §8 + RESEARCH_FINDINGS)

- **Torso wrap is already at Suitsupply parity** (spread 22.2 vs 23.1, at matched px/cm). Do not
  touch the torso. The open panels are **lapel, sleeves, back, collar, pockets**.
- **`SIL_WRAP` (silhouette-width wrap) is rejected *as a global effect*** — it validated on the
  torso but sheared the sleeves because `hw[y]` spans the whole row with no per-panel segmentation.
  Path A is precisely the missing piece (per-panel), so this is re-enabling it correctly, not
  relitigating it.
- SS's "clean pins" are drawn ~2× physical line-width — a display idealisation, **not** wrap; don't
  conflate. Crease depth is solved. Measurement rules: compare at **matched px/cm**, use SS's
  `ai-generated/ai-model` layer (never flat garment layers), settle by **looking**, not `period.py`.

## The crux question the research must resolve (per panel)

For each panel, **what drives the apparent stripe tilt?** Three candidate mechanisms, each of which
maps to different existing code:
1. **3D surface** (the panel's own curvature) → drive it from the **Marigold normal per-panel**
   (run `buildWarpNormal`'s parallax warp on each panel independently instead of globally-smoothed).
2. **Silhouette-width taper** (the "panel effect" the in-code comment at
   `build_configurator_v0.py:513-516` claims) → the **`SIL_WRAP` machinery** (per-row `cen`/`hw`,
   lines 520-533), applied **per-panel** (each panel's own centre/half-width).
3. **Cut grain** (the tailor deliberately cuts the panel's stripe at an angle — e.g. collar on the
   bias) → an explicit **grain rotation** per panel (the prototype's approach).

Reality is likely a mix (on-grain cut + 3D form for most panels; deliberate angle for collar; seam
breaks between separately-cut pieces). The research + measurement decides **which mechanism per
panel**, so we implement the correct one instead of arbitrarily rotating tiles.

## Research plan (in-thread, all directional patterns)

**R1 — Tailoring reality (domain research via the deep-research harness).** How a striped/checked
suit is cut & matched per panel: which panels are cut strictly on-grain vs off-grain (collar/
undercollar bias); whether the **lapel** stripe stays vertical or follows the roll (the money-shot);
how the **sleeve** stripe runs (front-vertical + wrap vs sleeve-pitch); **pattern-matching**
conventions — where tailors match across seams (centre-back, sleeve-head, pocket flaps, chest
pocket, trouser side seam) vs deliberately break. Suit-specific sources (bespoke/pattern-cutting
references, garment-CAD UV docs), adversarially verified, not generic.

**R2 — Ground-truth measurement (I do this in-thread).** Measure the EXACT stripe angle on each
panel (chest, each lapel, each sleeve, back, trouser) from high-res Suitsupply pinstripe/check
stills (`audit/ss/` + live CDN) and 2-3 other clean references, with `audit/pattern_map.py` at
matched px/cm. Output = a **per-panel target-angle table** — the numbers our fields must hit — plus
the same for one check and one windowpane (2D patterns have a horizontal component too).

**R3 — Competitor teardown, deeper than before.** Does ANY live configurator do per-panel pattern
wrap without baking? Inspect SS, Hockerty, Proper Cloth, Indochino, Black Lapel, and 3D/WebGL
builders (Threekit demos, Unspun, MTailor, Son of a Tailor, any live WebGL suit). For any live
compositor: how is the pattern oriented per panel (UV maps / per-panel texture regions / pre-
oriented panel PNGs)? For 3D/UV ones: the **UV layout convention** that makes a stripe run correctly
per panel — this tells us the correct per-panel grain even though we have no mesh.

**R4 — Synthesis → the per-panel grain SPEC.** Combine R1-R3 into:
`{panel → mechanism (normal-driven | silhouette-width | fixed-angle), target angle/range, seam
behaviour (match | break | phase-offset)}` for both 1D (stripes) and 2D (checks/windowpane)
patterns. This spec is the deliverable that makes Path A buildable without guessing.

## Path A implementation (AFTER research, driven by the spec)

Critical file: `builder/build_configurator_v0.py` (warp/composite JS lives in the template string).
1. **Panel segmentation** — refine the prototype's geometric segmenter (torso L/R, lapels via
   shirt-V adjacency, sleeves, collar, pockets, trousers); one-time, fabric-independent, across the
   15 renders. (Prototype already does a solid first pass; SAM2 as a fallback if geometry is
   insufficient.)
2. **Per-panel warp** — extend `buildWarpNormal` (lines 507-538) / `warpedCloth` (lines 568-593) to
   apply the spec's mechanism **per panel**: reuse the disabled `SIL_WRAP` per-row `cen`/`hw`
   machinery (now per-panel) where the spec says silhouette-width; run the normal parallax
   per-panel where it says surface; add a fixed rotation only where the spec says cut-grain.
3. **Seam breaks** — generalise the existing `buildPanels`/`SEAM_PHASE` phase-break (lines 539-542,
   575) to every panel boundary per the spec's match/break rule.
4. Roll across all 15 renders; hold on side/back.

## Verification

- **Research is done** when it yields: a per-panel **target-angle table** matched to measured SS
  ground-truth, an explicit **mechanism verdict per panel** (surface / width / cut-grain), and a
  **seam-behaviour rule** — for 1D and 2D patterns.
- **Path A is verified** by rendering a pinstripe (and a check) on the notch front, measuring each
  panel's stripe angle against the researched targets with `audit/pattern_map.py` at matched px/cm,
  and a 6× visual check per the standing rule — then confirming it holds on side/back.
- Guardrail: the torso must stay at its current parity (don't regress the solved panel).
