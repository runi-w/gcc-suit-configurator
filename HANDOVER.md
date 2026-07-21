# Gage Court Suit Configurator — Handover

_Last updated 2026-07-21 (late). Everything needed to pick this up cold._

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

- **`configurator-v0.html`** — self-contained, **3.52 MB**, data-URIs, zero external refs.
- **Right-rail UI** (user-approved design): full-length model on a cream stage; rail with 3 tabs
  (Fabric / Style / Measurements), 3-up swatch grid + cloth filter, pinned cloth footer.
  Expand + Front/Back card bottom-left. Collapses to stacked layout under 900px.
- **New house model** — regenerated 2026-07-21, black shoes, tieless. **Only the `notch` cut has
  the new model**; the other four cuts still use the old renders, so the man changes when you
  change cut. Expected — fixed by generating the remaining 14.
- **10 Elite Wool cloths** of 117, named from Shopify.
- Add-to-cart → Shopify container product; "View details" → real KuteTailor `saveOrder` spec.

### Measured against Suitsupply (their **photographic model** layer)

| | Ours | SS | |
|---|---|---|---|
| Colour vs mill scan | 98% | 105% | ✅ |
| Pattern scale | 0.99× true | true | ✅ |
| Pattern sharpness | 95% of true cloth | — | ✅ |
| Moiré | none | none | ✅ |
| Specular (p99/med) | 3.08 | 3.30 | ✅ |
| On-screen cloth density | 9.95 px/cm @1448×1086 | 10.3 | ✅ |
| **Crease depth (p1/med)** | **0.24** | **0.032** | ❌ ~7× lighter |
| **Pattern wrap (swing)** | **5.4° noise** | **22.7° monotonic** | ❌ |

---

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
│   ├── prep_fabrics.py             scans → tiles + micro-normals + params
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
| `FOOTPRINT` | **0.55** | runtime filter width. 1.0 double-filters the already-prefiltered tile and cost 29% sharpness |
| `SIL_WRAP` | **0.00** | silhouette wrap — implemented, validated on torso, disabled (see §6) |
| `DRAPE_TARGET_MED` | **111.4** | drape median = an exposure term. Calibrated so garment = ~100% of cloth |
| `STAGE_RGB` | (245,242,236) | must equal `--stage` in the CSS; injected |
| `PAT_DENSITY` | = OVERSAMPLE | emitted from it — cannot drift |

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

## 6. Next actions, in priority order

1. **Pattern wrap (`SIL_WRAP`)** — biggest visual gap. Implemented in `buildWarpNormal` and
   **validated on the torso** (central bands ordered −7.2 → −4.5 → −0.2 → +3.7 at 0.70, vs noise
   before), but disabled: `hw[y]` spans the whole row, so the **sleeves** — separate tubes with no
   background gap to the body in this pose — get sheared as if they were the torso. Outer bands
   invert and wobble rises 19°→24°. **Needs per-panel centre/width (torso vs each sleeve)**;
   likely segmentable from the arm/body crease in the normal map. Target: swing 22.7°, spread
   16.7°, monotonic. Measure with `python3 audit/pattern_map.py`.
2. **Crease depth** — ours 0.24 of median vs SS 0.032. The lever is the base render's own crease
   depth (a hero prompt change), not the compositor. Decide before generating the other 14.
3. **Generate the remaining 14 renders** — `plan/MODEL_BIBLE.md` has the full spec, order
   (hero → 4 fronts → sides/backs) and all prompts. Until then the man changes when the cut changes.
4. **Wire the view dimension** — `CUTS` maps one filename per cut; needs cut × view, and the
   Front/Back control needs connecting (styled but disabled).
5. **Fix `prep_fabrics.py` param normalisation** — sheen/relief normalise across the *current
   batch*, so processing all 117 shifts every value. Needs absolute anchors. **Blocks the 117 batch.**
6. **Batch all 117 fabrics**, spot-check outliers.
7. **Shopify embed** — upload remaining 29 assets → `themeFilesUpsert` onto theme 149240774843 →
   `pageCreate`. ⚠ deliverable is 3.52 MB; check the page budget.
8. **Register `orders/paid` webhook** + wire the backend.

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
- Fabric names come from **Shopify**, never guessed from colour (5 of 10 were mislabelled that way).
- Copy rule: suits are **made-to-measure, never "handcrafted"/"hand-tailored"**.

---

## 9. Related memory

`gcc-pattern-render-playbook` (**THE STANDARD** — read before touching rendering) ·
`gcc-shopify-configurator-order-capture` · `gcc-suit-configurator` · `gcc-ai-model-decision` ·
`gcc-two-product-lines` · `gcc-shopify-update-protocol`

Published artifacts: Suitsupply audit report · parity plan · live configurator preview.
