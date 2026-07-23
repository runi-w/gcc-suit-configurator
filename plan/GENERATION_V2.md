# Generation V2 — the fresh logic

Written 2026-07-23, the day the gorge question was settled. This replaces the accumulated
generation folklore with one document: how base renders are made from now on, why each step
exists, and how fabric swatches are read so the result is accurate to the real cloth.

---

## 1. The settled fact this is built on

**The gorge failure was the prompt, not the generator.** The old prompt said only "NOTCH lapel of
standard width" — it never described the construction — and the generator failed to draw the
right-side gorge in 10 of 10 generations. `PROMPT_03_hero.txt` describes the gorge as a tailor
would (two separate pieces of cloth, a stitched gorge seam, an open V between collar point and
lapel point, required identically on both sides), and the same generator drew it correctly
**3 of 3 times** on 2026-07-23. Same API, same model, same day-class hardware. The prompt was the
whole variable.

Corollary: never again write "a notch lapel" and expect a notch. Name the construction feature,
say where it is, say it appears on both sides.

## 2. The division of labour

Three parties, each doing only what it is good at:

| Party | Owns | Never ask it for |
|---|---|---|
| **The prompt** | construction, pose, cloth colour/finish, tone limits, believable light | exact framing, exact background level |
| **Arithmetic** (`normalize_render.py`) | sweep → neutral 246, figure → exactly 0.898 of frame, centring | anything creative |
| **Your eyes** | the gorge, and final acceptance | nothing — they gate everything |

The generator demonstrably ignores numeric framing/background instructions (asked 246, gave 229;
asked 0.88, gave 0.936 — and again today: asked 90%, gave 0.947–0.959, twice off-centre). That is
why arithmetic owns framing. Do not fight it in the prompt; one brief mention is enough.

## 3. The generation loop, per image

```bash
python3 builder/gen_model.py <name> plan/PROMPT_03_hero.txt      # 2K via the Google API
# auto-runs check_render.py (10 validity checks)
OUT=/tmp python3 builder/check_rebuild.py renders_v2/<name>.png  # 9 quality axes vs baseline + GORGE SHEET
# LOOK at /tmp/rebuild_gorge.png — the gorge is judged only by eye
python3 builder/normalize_render.py renders_v2/<name>.png        # sweep + framing, in place
python3 builder/check_render.py renders_v2/<name>.png            # re-gate after normalise
```

Accept when: both gorges clean **by eye**, and the numeric axes at-or-better than baseline.
The eyeball rule exists because three gorge metrics were tried and one read backwards; no metric
gates the gorge, ever.

## 4. Generator behaviours learned today (v3a/b/c)

- **It draws the lighting rig if you describe it physically.** v3a put two softboxes in frame.
  The prompt now says the studio itself is invisible. Keep that line.
- **Framing drifts every time** (0.947–0.959 height, centre at 0.34 twice). Arithmetic fixes it;
  do not regenerate for framing alone.
- **The sweep is never perfectly flat.** A soft top-of-frame falloff survives the global key
  (top border ~235–240 vs 246, one patch to 207). Open item: if `on_stage()` chokes on it,
  upgrade `normalize_render.py` to a low-order 2D field key instead of a global gain. Note the
  audit found the reference's sweep also carries a gradient — dead-flat is itself a render tell —
  so the bar is "flat enough for the compositor", not "flat".
- **The multiplicative sweep key amplifies L/R asymmetry a little** (garment +26.8 → +33.3 after
  normalise). Asymmetry is not a defect (Suitsupply ships −14 to +23; a key-plus-fill setup does
  this), and the drape's jacket-scoped debias handles what needs handling. Do not select
  candidates for symmetry.
- **~35 s per generation.** Generating 3 and picking beats regenerating 1 until it behaves.

## 5. The set: identity and sequencing

1. **Accept the hero first, alone, generated fresh with NO reference image** — reference-attached
   generation is precisely the mode where instructions get ignored, and it is how the old gorge
   defect propagated into every cut.
2. Derive the other 9 (4 front cuts + 5 backs) as image-to-image **edits of the accepted hero**:
   "keep the exact man, pose, cloth, light and background; change ONLY the jacket to X."
3. **Run the gorge sheet on every front.** The `fix_gorge.py` retouch stays in the pipeline as a
   backstop — it costs nothing when the gorge is already correct.
4. Backs are low-risk (no lapels). Fronts are gated one by one.
5. Then per render: `make_mask.py` → `make_drape.py`; Marigold **once over the whole batch**,
   off-hours, Chrome closed (~18 min/render on the 8 GB M1); then the builder.

The compositor does not change. Renders are an input, not a dependency.

## 6. How fabric swatches are read — the accuracy chain

The customer never sees the render's grey. They see the swatch, re-lit. Accuracy therefore means:
**true scale, true colour, true pattern geometry**, each carried by a different mechanism.

### Scale — from DPI, never guessed
- Elite mill scans are 300 DPI ⇒ **118.11 px/cm exactly**; every scan is exactly 10.0 × 7.0 cm of
  cloth. The tile records its own `cmPerTile`.
- The canvas knows its scale as `PX_PER_CM = FIGURE_FRAC × H_FULL / FIGURE_CM ≈ 8.85` — derived
  from the **uncropped** frame height. `FIGURE_FRAC` (0.93) and `FIGURE_CM` (183) are individually
  soft; **only their product matters**, and the product is validated end-to-end: a rendered chalk
  stripe measures 1.42 cm against 1.44 cm on the physical cloth (0.99×). Never "correct" one
  factor alone.
- Prestige swatches are vendor 1200 px images at a **calibrated 172.01 px/cm**. ⚠ Open item: the
  audit could not reproduce that calibration from files in the repo — re-derive it against the
  DBQ791A ruler truth and write the derivation down next to the number.

### Colour — trusted as-shot, exposure calibrated separately
- The scans were verified colour-trustworthy before anything was built on them: jet-black DBT572A
  measures a\*=+0.1 b\*=+0.1 (dead neutral), 0.00% blown highlights, vignetting ≤2%. So the swatch
  colour is used **as shot — no colour correction**, which is why renders measure 98% of the mill
  scan's colour.
- Luminance on the body is a separate, calibrated term: the drape's masked median is pinned to
  `DRAPE_TARGET_MED = 111.4`, putting the garment at ~98–105% of the cloth's true luminance
  (canvas `overlay` makes the drape median an exposure control; 128 — the "neutral" value theory
  suggests — overshoots to 151%).
- **Fabric names come from Shopify by SKU** (`products(query:"sku:<CODE>")`), never guessed from
  colour — 5 of 10 were once mislabelled that way.

### Pattern geometry — the tile must repeat like the cloth does
- Seamless tiles are **wrap-blend cross-fades (BLEND 0.22), never 4-way mirrors** (mirror gives
  chevrons and flips twill handedness).
- **Deskew**: stripe scans lean up to 1.3° on the platen; `stripe_angle()` measures and rotates
  it out (residual 0.09°).
- **Motif-period snap**: the tile width is snapped to a whole pattern repeat — using the HIGHEST
  autocorrelation peak, not the first, because chalk stripes alternate strong/faint companions —
  so the blend lands in phase instead of ghosting.

### Known accuracy bugs — the fresh logic must fix these, in this order
1. **Stripe WEIGHT is wrong on the finest cloths.** Half-maximum line width, source → tile:
   DBT6860 0.45 mm → 1.97 mm (**4.4× too bold**); DBU080A 0.97 → 0.54 mm; DBU081A 0.61 → 0.17 mm
   (too fine). Pitch is correct on all of them — the spacing is right, the line weight is not.
   Cause: the `widen_lines()` display floor, added when the renderer was over-sharp. Now that
   `FOOTPRINT = 1.15` band-limits properly, re-calibrate the floor against the **measured mm
   width of the source stripe**, per cloth, instead of a blanket 2.2 px minimum. This is a
   customer-fidelity issue: a shopper who orders the navy chalk stripe receives a visibly quieter
   cloth than the preview showed.
2. **`stripe_period()` mis-detects DBS175A** (locks a weave harmonic; the true repeat is ~289 px
   at 172 px/cm ≈ 1.68 cm). Constrain the search band by the physically plausible menswear range
   (0.6–3 cm) and verify by eye against the scan — `audit/period.py`-style detectors lock onto
   harmonics 9 times out of 10.
3. **Checks and windowpanes get no period snap at all** (8 cloths) — only stripe-classified
   cloths are snapped, and only horizontally. Snap both axes for periodic patterns.
4. **Per-swatch illumination flattening**: fit and divide a low-order 2D field on each scan
   before tiling, so baked-in scan lighting cannot print a faint tile-pitch banding (measured
   ~2 levels pk-pk on DBP665A/DBQ791A trousers — small, but free to remove at prep time).

### What keeps it honest
- Settle every scale question by rendering the cloth at garment scale **next to** the composite
  and looking — the project's period detectors are unreliable and one symmetry metric read
  backwards. Numbers second, eyes first.
- Frozen normalisation anchors (`WEAVE_LO/HI = 9.32/61.04`, `PAT_THRESH = 0.9375`) mean adding a
  fabric never shifts the sheen/relief of existing ones — the 117-cloth batch stays stable.

## 7. Status

- **hero_v3b is the accepted hero candidate** (2026-07-23): both gorges clean by eye, 9/9 quality
  axes, construction detail 20.9% vs the old hero's 17.3%, normalised to 0.898/centred/246.
  Awaiting the user's own eye before the other 9 are derived from it.
- v3a (softboxes in frame) and v3c (second-best numbers) retained in `renders_v2/` as evidence
  and fallback.
- Open: the top-border sweep gradient (watch `on_stage()`); Marigold batch off-hours; the four
  swatch-accuracy bugs above.
