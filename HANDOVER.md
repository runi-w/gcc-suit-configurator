# Gage Court Suit Configurator — Handover

_Last updated 2026-07-23 (Session 5). Everything needed to pick this up cold._

---

## 1. What this is

A self-serve custom-suit configurator for **gcclothiers.com** (Shopify, standard plan — no Plus).

Customer picks cloth + style → sees it rendered on a house model → pays on Shopify → an
`orders/paid` webhook hands a **supplier-agnostic order envelope** to a backend intermediary →
backend submits to **KuteTailor**.

Business context: small MTM tailor, Pikesville MD + Central Jersey, roughly **1–3 online custom
sales/month**. That volume is why real-time 3D and per-fabric photography are out of scope.

---

## 2. Current state
_Rewritten 2026-07-23. This section describes what IS true, not what changed when. Five sessions
of append-only notes had accumulated real contradictions — several constants were documented at
values they no longer hold, and one long-standing "known residual" turned out not to reproduce.
A compressed history is at the end of this section._

### The compositor, end to end

One fixed AI render per cut-view (15 = 5 cuts × front/side/back), plus a coverage mask, a drape
map and a Marigold normal map. At runtime the chosen cloth is tiled into the mask and shaded:

1. **Panel segmentation** (`builder/panels.py`, build time) → a 9-value panel map per cut-view:
   torso-L/R, lapel-L/R, sleeve-L/R, collar, trouser. Emitted as a greyscale PNG.
2. **Arc-length unwrap** — the cloth coordinate advances by arc length along a per-panel cylinder,
   so the pattern compresses toward each panel's silhouette exactly as it does in real suit
   photography. `dU/dx = 1/max(sqrt(1-((x-C)/R)²), NZ_FLOOR)`.
3. **Per-panel grain rotation** (Path A) — lapel ±16°, sleeve ±5°, collar 87°, torso/trouser 0.
   Applied AFTER the unwrap, about an anchor mapped through the same unwrap.
4. **Seam phase** — the front-opening break (`SEAM_PHASE`), unchanged and research-locked.
5. **Sampling** — SS=3 supersample with an anisotropic footprint (`fpx = fp·dU/dx`).
6. **Drape overlay** then an **additive sheen** pass. All of the garment's three-dimensionality
   lives in these two, not in the pattern's geometry.

**There is no normal-driven pattern warp.** It was removed: derived from a lighting-correlated
normal, it expanded where foreshortening must compress on 86.6% of torso pixels, was worse than a
flat pattern on 24 of 24 panel-cases against a cylinder ideal, and dilated stripe spacing +9.6%,
silently breaking the true-scale calibration. `WARP_AMP_MULT = 0.0` and it stays there.

### What the renders and maps are

- **Renders** — the 5 FRONT renders are **retouched** (`builder/fix_gorge.py`). The generator
  invented a key light from screen-right and never drew the lapel gorge on that side, in 10/10
  generations ever including `renders/_superseded/`. The left gorge's structure is mirrored onto
  the right (high-frequency only, so the right keeps its own lighting), registered on each
  lapel's inner edge because the fronts overlap and the gorges are NOT symmetric about the neck.
  Pristine originals are kept as `renders/*.orig.png`.
- **Masks** (`builder/make_mask.py`) — the shoulder under-coverage is fixed (missed px −42%,
  side-view run width 37-52 px → 10-12). ⚠ Still fills over **buttons and pocket welts** as if
  they were pinholes, so cloth is painted on top of them — §6 item 1.
- **Drape maps** (`builder/make_drape.py`) — carry a left/right lighting debias, scoped to the
  **jacket only** and to **front/back only**. Both scopes are load-bearing: a whole-garment fit
  injected the jacket's bias into clean trousers, and debiasing a *profile* removes the body
  turning away from the light (23% of the side view's tonal range).
- **Normal maps** — half linear resolution, still lossless WebP. They feed only the sheen's
  grazing term now that the pattern warp is gone.

### Measured against Suitsupply

Compared at **matched cloth density** (8.81 px/cm). Their reference is a chest-up phone shot at
23.05 px/cm — comparing raw makes ours look soft when it is merely showing more of the man.

| | Ours | SS | |
|---|---|---|---|
| Colour vs mill scan | 98% | 105% | ✅ |
| Pattern scale | 0.99× true | true | ✅ |
| Moiré | none | none | ✅ |
| Specular (p99/med) | 3.08 | 3.30 | ✅ |
| On-screen cloth density | 9.95 px/cm @1448×1086 | 10.3 | ✅ |
| Crease depth (p1/med) | 0.073 | 0.031 | ✅ |
| Lapel grain (front, measured) | −17.3° | −12.1° photo | ✅ |
| Collar grain (back, measured) | +86.8° | −85 to −90° (CDN) | ✅ |
| Ramp-free shading residual | **0.398** | 0.372 | ✅ we carry *more* form |
| Cloth band-limiting (lag-1 autocorr) | 0.45–0.66 → **~0.89** | 0.96 | ✅ after FOOTPRINT 1.15 |

**A long-standing entry has been deleted, not moved:** "shadow depth p5/med ~0.40 vs SS 0.19".
It does not reproduce at any density — reference 0.541 native / 0.556 matched, ours 0.588, a 5.8%
gap rather than 2×. Do not re-open it.

### Shipping state

- **`configurator-v0.html`** — self-contained, ~7 MB, all 15 cut-views, zero external refs.
- **Split build** for Shopify: `GCC_SPLIT=1 python3 builder/build_configurator_v0.py` → `dist/`
  (core = compositor + CSS + markup + 5 front cut-views; views = the 10 side/back, lazily
  fetched on the first Side/Back click; a 488-byte `{% layout none %}` page template).
- **`/pages/design-your-suit`** — a **DRAFT** page (`gid://shopify/Page/117734375611`) on the
  **Prestige** theme `149240774843` (serves at `t/59`). Publishing the theme and the page are
  both the user's steps; the connector blocks live-theme writes and theme publishing.
- ⚠ **The deployed Shopify bundles are STALE.** `gcc-configurator-core-v5.js` /
  `gcc-configurator-views-v2.js` are the state at commit `cf7b59f`. Everything after that — the
  gorge retouch, the drape debias, FOOTPRINT 1.15, the neutral stage and contact shadow — is in
  the repo but NOT deployed. Re-upload before publishing.
- **17 cloths**; add-to-cart → Shopify container product; "View details" → a real KuteTailor
  `saveOrder` spec.

### How it got here (compressed)

| Session | What it established |
|---|---|
| 2 | Crease depth's lever is the COMPOSITOR, not the render. `SIL_WRAP` rejected in its original whole-row affine form. Stripe scans deskewed + period-snapped. |
| 3 | All 5 cuts became the same man; front/side/back generated (15 cut-views); mask hair/shoe/shoulder fixes. |
| 4 | Path A research → `plan/PATH_A_GRAIN_SPEC.md`; Suitsupply render-architecture teardown → `plan/SS_RENDER_ARCHITECTURE_SPEC.md`. |
| 5 | Path A implemented; Shopify embed built; deliverable trimmed; shoulder mask fixed; pattern warp removed; arc-length unwrap added; renders retouched; visual-parity pass. |

## 3. Layout

```
~/Desktop/GCC_House_Model/
├── configurator-v0.html        ← the deliverable
├── builder/                    ← SOURCE OF TRUTH
│   ├── build_configurator_v0.py    main builder (paths absolute)
│   ├── gen_model.py                Gemini API render at 2K
│   ├── normalize_render.py         sweep colour + framing
│   ├── check_render.py             10 acceptance checks
│   ├── make_mask.py                garment segmenter (coverage ramp)
│   ├── make_drape.py               drape map from render + mask
│   ├── panels.py                   ⭐ Path A: panel segmentation + PANEL_ANGLES + cylinder profiles
│   ├── fix_gorge.py                ⭐ retouches the missing RIGHT gorge on the 5 front renders
│   └── (prep_fabrics.py lives at the REPO ROOT, not here — the builder copy was a
│        stale fossil without deskew/period-snap/line-floor and is now a hard-exit stub)
│   └── recolor_shoes.py            SUPERSEDED (generate black directly)
├── audit/                      ← measurement toolchain
│   ├── calib.py                    colour vs mill scan
│   ├── ss_profile.py               shading shape vs Suitsupply
│   ├── pattern_map.py              stripe orientation / wrap / wobble
│   ├── period.py                   ⚠ UNRELIABLE — see §7
│   ├── ss/                         Suitsupply reference layers + swatches
│   └── out/                        comparison images
├── plan/
│   ├── MODEL_BIBLE.md              ⭐ the 15-render regeneration spec
│   ├── AI_PROMPT_PACK.md           prompts + the 5-step pipeline
│   ├── RENDER_MANIFEST.md          every option, what each costs
│   ├── STUDIO_BRIEF.md             CAD pilot brief (not commissioned)
│   └── PROMPT_01_hero.txt          paste-ready hero prompt
├── prep_fabrics.py             ⭐ THE LIVE fabric prep: scans → tiles + params
├── renders/                    ← base renders (+ _superseded/)
├── drape_maps/                 ← drape (LA) + normal maps (+ _superseded/)
├── fabric_build/               ← tiles, micro-normals, fabrics.json
└── hires_swatches/2501-117/    ← 117 mill scans @300 DPI
```

### Rebuild
```bash
cd ~/Desktop/GCC_House_Model/builder
python3 build_configurator_v0.py     # writes ../configurator-v0.html
```
Byte-identical across rebuilds. Preview over `http://` (not `file://`).

---

## 4. Locked constants — and why

In `builder/build_configurator_v0.py`. **Every one has a measured reason; read the comment before
changing it.**

| Constant | Value | Why |
|---|---|---|
| `W` | 1300 | canvas width; sources are 1792×2400 |
| `CROP_FRAC` | 1.0 | full figure incl. shoes (the approved design) |
| `RSCALE` | W/700 | **all px-tuned constants scale by this** |
| `OVERSAMPLE` | **2** | samples/texel = SS/OVERSAMPLE. At 4 it was 0.75 (sub-Nyquist) → heavy moiré on checks |
| `FOOTPRINT` | **1.15** | runtime filter width — see the note below |
| `WARP_AMP_MULT` | **0.0** | the normal-driven pattern warp, removed. Do not revive it (§8) |
| `UNWRAP_AMP` | **1.0** | per-panel arc-length cylindrical unwrap. This is what makes the pattern hug the body |
| `CYL_STEP` | 8 | rows between sampled cylinder profiles; interpolated between |
| `DRAPE_TARGET_MED` | **111.4** | drape median = an exposure term. Calibrated so garment = ~100% of cloth |
| `STAGE_RGB` | **(239,239,239)** | neutral studio grey; must equal `--stage` in the CSS; injected |
| `SHADOW_*` | 1.55 / 0.16 / 13.0 / 0.16 | the elliptical contact shadow under the shoes (w, h, blur, strength) |
| `PAT_DENSITY` | = OVERSAMPLE | emitted from it — cannot drift |

In `builder/panels.py`:

| Constant | Value | Why |
|---|---|---|
| `PANEL_ANGLES` | 0,0,0,−16,+16,−5,+5,87,0 | the grain table — **the single tuning point for Path A** |
| `NZ_FLOOR` | 0.70 | clamps the unwrap's 1/sqrt(1−t²) at the silhouette. Lower = more compression, and past ~0.55 the edge smears |
| `TORSO_R_FRAC` | 0.70 front/back, 1.00 side | torso cylinder radius as a fraction of half-width |
| `SLEEVE_RHO` | 1.00 | sleeves are nearly circular in section, so no flattening |

**`FOOTPRINT` was 0.55 for four sessions and that was wrong.** The 0.55 justification ("1.0
double-filters and costs 29% sharpness") measured our own output against itself, so it could only
ever prefer *less* filtering. Measured against the actual reference instead — lag-1
autocorrelation, i.e. how band-limited real photographed cloth is — Suitsupply reads 0.96 and we
read 0.45–0.66. Ours was *sharper than a photograph*, which is what produced the fine per-pixel
beading on stripes. 1.15 lands at ~0.89. A camera's MTF is not a bug to be minimised.

**Two invariants that are easy to break:**
1. `PX_PER_CM` derives from the **uncropped** `H_FULL`.
2. `FIGURE_FRAC` (0.93) and `FIGURE_CM` (183) are individually soft — **only their product
   matters** (`PX_PER_CM = 8.85`), and that product is validated by pattern pitch measuring 0.99×.
   Never "correct" `FIGURE_FRAC` alone.

---

## 5. The render pipeline

Generation is step 1 of 5. **Marigold is step 4, not step 2.**

```bash
cd ~/Desktop/GCC_House_Model
python3 builder/gen_model.py <name> <prompt.txt> [refs...]   # 1. Gemini API @2K
python3 builder/normalize_render.py renders_v2/<name>.png    # 2. sweep + framing
python3 builder/check_render.py renders_v2/<name>.png        # 3. accept or reject
python3 builder/make_mask.py  <render> /tmp/m.png            # 4a. garment mask
python3 builder/make_drape.py <render> /tmp/m.png drape_maps/<name>_drape.png   # 4b.
~/gcc_normals_venv/bin/python gen_normals_all.py             # 4c. Marigold (SLOW, batch it)
python3 builder/build_configurator_v0.py                     # 5. build
```

- **API key**: `~/Desktop/GCC_Fabric_Handoff/keys/gemini_key.txt`, model `gemini-3-pro-image`.
  **`generationConfig.imageConfig.imageSize:"2K"` is the whole point** — the web UI caps at
  896×1200 and adds a sparkle watermark; the API does neither.
- **Do steps 1–4b for every render, then run Marigold once over the batch.** ~18 min per render
  with Chrome open on the 8 GB M1. Quit Chrome. Add new names to `CUTS` inside the script first.
- **The generator ignores framing/lighting instructions when a reference image is attached** —
  asked for bg 246, got 229; asked figure 0.88, got 0.936. Don't fight it with prompts;
  `normalize_render.py` computes both.

---

## 6. Next actions, in priority order (rewritten 2026-07-23)

The four items below came out of a visual parity audit against the Suitsupply reference. They are
ordered by how much a shopper would notice them.

1. **The mask paints cloth over buttons and pocket welts.** `builder/make_mask.py:109-113` fills
   "pinholes" morphologically, and a button is a pinhole to that test. So the chosen cloth is
   composited straight over every button, buttonhole and welt — the garment reads as a smooth
   shell. Fix: detect them (they are dark, round, and consistent across all 15 cut-views) and
   punch them back out of the coverage mask so the render's own buttons show through.
2. **The tile blend prints a faint grid.** Weave contrast dips 39–53% in the blend band, once per
   tile, so on a plain cloth a regular grid is faintly visible. Fix in `prep_fabrics.py`: blend
   in a contrast-preserving space, or hide the seam inside a stripe repeat as the horizontal
   snap already does.
3. **`stripe_period` mis-detects DBS175A** (`prep_fabrics.py:153`): d=61 where the true repeat is
   201, so that cloth renders at ~3× its real stripe pitch. `audit/period.py` is unreliable in
   general (§7) — verify by eye against the scan.
4. **Whites clip.** 45% of shirt-placket pixels sit at ≥250 where the reference ceilings at 240.
   Costs the shirt its texture next to the suit. A ceiling in `normalize_render.py`.

Then:

5. **Re-upload the Shopify bundles** — the deployed `core-v5` / `views-v2` predate the gorge
   retouch, the drape debias and FOOTPRINT 1.15 (§2). Rebuild with `GCC_SPLIT=1` and re-upload
   before anyone sees the page.
6. **Publish the embed.** Publish the Prestige theme `149240774843`, then set page
   `gid://shopify/Page/117734375611` to published. Both blocked for the connector — yours. Decide
   too whether `{% layout none %}` (no site header/nav on that page) is what you want.
7. **Tune `PANEL_ANGLES` by eye on more cloths.** Only the two Elite pinstripes (DBT6860,
   DBU081A) have really been judged. Worth a look on a check or windowpane, where the prediction
   is that both grid axes rotate together with no extra code.
8. **Batch all 117 fabrics** — unblocked (anchors frozen); spot-check outliers.
9. **Register `orders/paid` webhook** + wire the backend.

**Known and deliberate, not defects:** the side view has no sleeve panel (in profile the arm sits
mid-silhouette, so there is nothing to key off); a thin antialiased rim at the shoulder silhouette
on side/back, which is the coverage ramp working as designed; and the ~7 MB deliverable, which the
split build already solves for the web.

**Dropped from this list:** the "shadow depth 0.40 vs SS 0.19" item — it does not reproduce (§2).

**Difficulty-routing bake fallback** (`plan/RESEARCH_FINDINGS.md`) stays on the shelf: AI-baking
the ~27–29 bold directional fabrics onto the standing render is only worth it if Path A quality is
judged insufficient, and Path A is now built and shipping.

---

## 7. Gotchas that have already cost time

- **Measuring composites: hard-mask `alpha>200`, and erode 3px on a variance mask.** The
  anti-aliased edge band lets the mid-grey base bleed through and inflated specular from 3.3 to
  **10.9** — looked like blown highlights, wasn't.
- **Compare at matched px/cm.** Raw orientation spread read 49° vs SS's 23° — apparently twice as
  wobbly. Resampled to a common density, we're at parity. Same trap as comparing a render to a
  full-resolution scan.
- **Use Suitsupply's `ai-generated/ai-model` layer as reference, never their flat `Jacket/model`
  layers.** A garment with no body inside has neckline-cavity darks (p1 0.092 vs 0.032 worn).
  Tuning to it means inventing shadows they never show.
- **`audit/period.py` is unreliable** — locks onto harmonics, 1/10 fabrics stable. Settle scale
  questions by rendering cloth-at-garment-scale next to the composite and *looking*.
- **Metrics can miss what your eye catches.** An edge-roughness metric rated a broken mask and a
  good one identically; only a 6× visual comparison found the ragged sleeves. Always look.
- **Marigold: fp32 only** (fp16 on MPS → NaN). **Normal maps must stay lossless** — WebP lossless
  is bit-exact and 27% smaller than PNG; lossy WebP/JPEG hit 18–20° of vector error.
- Browser console: top-level `let`/`const` are **not** on `window` — probe with bare identifiers.
- MCP blocks live-theme writes and `themeFilesDelete`.
- **Never move file bytes through a tool payload.** Hand-transcribing base64 corrupted an upload
  at 3,519 of 6,616 bytes. Stage the file and `curl` it. Same failure as the handover's
  "retype→403" note — one rule: bytes go over the wire, never through the model.
- **`themeFilesUpsert` with a URL body silently no-ops for `templates/*.liquid`** (it works fine
  for `assets/*`). Returns success, writes nothing. Keep templates small enough to send as TEXT —
  ours is 488 bytes because the markup and CSS live in the JS bundle.
- **A metric that can't see the defect is worse than no metric.** Three gorge-symmetry metrics
  were tried against a known-broken render and its fixed twin; one read *backwards* (0.99 broken
  vs 0.61 fixed). None shipped — see the comment at the top of `builder/check_render.py`.
- **Debias what is a lighting artifact, never what is the modelling.** A left/right luminance ramp
  is an artifact on a front or back view and the actual form on a profile; trousers are already
  clean, so a whole-garment fit injects the jacket's bias into them. Both scopes are in
  `make_drape.py` and both were found by breaking something.
- 8 GB M1 — heavy compute off-hours, Chrome quit.

---

## 8. Settled — do not relitigate

- **2D compositing, not real-time 3D.** Proven by inspecting live production assets: Suitsupply
  and Hockerty are both pre-rendered 2D layer stacks. Hockerty's "3D" branding is marketing
  (it loads Fabric.js).
- **Our asset count is fabric-independent** — we composite cloth at runtime, so **126 renders**
  covers every visible option across all 117 cloths (87 if house-standard options stay fixed).
  Suitsupply need ~25,000 because they bake cloth into every layer. Do **not** copy their approach.
- **AI cannot do the garment CAD** (researched July 2026): Marvelous Designer's AI Pattern Drafter
  is t-shirts only; Tripo's "simulation ready" is unverified marketing; the promising work
  (Dress-1-to-3, ReWeaver) is papers, not products.
- Rejected renderer changes: **AO/crevice darkening in folds** · fold-scale warp wiggle ·
  per-pixel sheen tint · mirror tiles · guessed pattern densities · lossy normal maps ·
  anchoring the drape median at 128.
- **The normal-driven pattern warp is dead** (Session 5, `WARP_AMP_MULT = 0.0`). It was derived
  from a lighting-correlated normal map, so it expanded the pattern where foreshortening must
  compress it on 86.6% of torso pixels; it lost to a flat pattern on 24 of 24 panel-cases against
  a cylinder ideal; and it dilated stripe spacing +9.6%, silently breaking the true-scale
  calibration that is one of this project's few hard wins. Do not revive it in any form that
  reads geometry out of a lighting-derived map.
- **`SIL_WRAP` was rejected in Session 2 and its IDEA was later proven right** — this is the one
  entry on this list that moved. What was rejected is the *implementation*: a global whole-row
  affine that sheared sleeves and regressed orientation spread. Cloth genuinely does compress
  toward a silhouette, and Session 5 shipped it correctly as a **per-panel arc-length unwrap**
  (§2) once panel geometry existed to scope it. Rejecting the 2026-07-22 version was right;
  "cloth should not wrap" was never the finding.
- **Crease depth's lever is the COMPOSITOR (`soften_drape`), not the base render** (Session 2,
  measured stage-by-stage). Do not re-propose a hero-prompt crease change; the render is already
  SS-deep.
- **SS's "clean pinstripes" are drawn ~2× physical line-width** — a display idealisation, not
  fidelity or per-panel wrap. Adopted as a gated line-width floor; don't chase it as a wrap fix.
- Fabric names come from **Shopify**, never guessed from colour (5 of 10 were mislabelled that way).
- Copy rule: suits are **made-to-measure, never "handcrafted"/"hand-tailored"**.

---

## 9. Related memory

`gcc-pattern-render-playbook` (**THE STANDARD** — read before touching rendering) ·
`gcc-shopify-configurator-order-capture` · `gcc-suit-configurator` · `gcc-ai-model-decision` ·
`gcc-two-product-lines` · `gcc-shopify-update-protocol`

Published artifacts: Suitsupply audit report · parity plan · live configurator preview.
