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

### ⭐⭐⭐ Session 5 (2026-07-23) — PATH A IMPLEMENTED AND SHIPPING. Per-panel grain is live.

`plan/PATH_A_GRAIN_SPEC.md`'s implementation sequencing is **done, all five steps**. The
compositor now gives each tailoring panel its own cloth grain, on all 15 cut-views.

- **New `builder/panels.py`** — the segmenter. One flat render + its coverage mask →
  a 9-value panel map (torso-L/R, lapel-L/R, sleeve-L/R, collar, trouser). It also owns
  **`PANEL_ANGLES`, the single place the grain is tuned**, with the provenance of every number
  in a comment. Run it directly (`python3 builder/panels.py`) to print landmarks and write a
  15-view QA contact sheet — the segmentation was built by looking at that sheet, per the
  playbook's "always look" rule, and it caught three things a metric would not have (lapel bands
  crossing into an X below the button; a skin-keyed collar detector selecting a box with no
  garment in it; side-view "sleeves" landing on the front and back edges of the profile).
- **Segmentation is BUILD-TIME, not runtime JS.** The panel map is *geometry*, and geometry in
  this codebase is already a per-cut-view build asset (mask/drape/normal) — the same split
  `plan/SS_RENDER_ARCHITECTURE_SPEC.md` S3 proved Suitsupply makes. Rides along as a greyscale
  PNG: **+130 KB on the deliverable, ~1.2%.** Measured against the
  alternatives: packing it into the mask PNG's spare channels would have cost +201 KB.
- **Mechanism = rigid rotation of the sampling coordinate about a per-panel anchor**
  (`u=(x·cosθ+y·sinθ)·dens, v=(−x·sinθ+y·cosθ)·dens`), exactly as the spec called for. The anchor
  matters: the pattern is unmoved *at* the anchor and turns around it, so it doubles as the
  panel's phase reference — the sleeve's sits on the armhole at chest height, which is the one
  line the spec says a sleeve must match the body on.
- **NO TORSO REGRESSION, proven not asserted.** Angle 0 takes the original expression verbatim,
  so it is bit-identical by construction. Verified anyway by rendering every cut-view twice (with
  the table live, and with it zeroed) and pixel-diffing: across 4 cut-views, **0 pixels changed
  outside the rotated panels.** `audit/panel_angles.py` agrees — torso −0.7°/+0.3° front,
  +1.1°/−1.1° back, unmoved.
- **Shipped angles (user-chosen by eye from a rendered 0/11/16/22/28 sweep): lapel ±16, sleeve
  ±5, collar 87.** Measured on the finished composite: lapel-L **−17.3°** (sd 6.8), collar
  **+86.8°** (sd 7.7, against −0.8° before), sleeves now mirrored where they were not.
- **⚠ CALIBRATION — the table value is not the angle you see.** The rotation composes with the
  existing normal-driven warp, which already leans the lapel ~4° on its own (lapel-L measures
  −7.5° with the table zeroed). **Rendered ≈ table + 4° on the lapel**; the collar has no such
  offset. Re-measure with `audit/panel_angles.py`, don't trust the table, if the warp changes.
- **The spec's open question 1 is ANSWERED: the sleeve needs its own rotation.** The spec said to
  verify the existing normal-driven warp against the ±5° target before writing new code, since
  Marigold's normal map is a real capture of the sleeve's geometry. Measured: it delivers
  **0.0° to −2.5° and is not mirrored L/R** — so it does not get there on its own. Explicit
  rotation added.
- **Seam rules, all four:** front opening — `SEAM_PHASE` deliberately untouched (R1 tested and
  refuted the claims on *both* sides of that question, so there is no grounded reason to move it);
  it stays a per-PIXEL rule so today's look is preserved exactly, and the JS function that
  computes it is renamed `buildSeamPhase` while `buildPanels` now means the panel map. Center-back
  collar-continuity — **already satisfied, no code needed**: `openFront` is false on back views,
  so there is no phase break at center back and the pattern runs continuously through the collar,
  which is what the rule asks for (panels "one repeat apart" is visually continuous for a periodic
  tile). Sleeve one-line match — the anchor, above. Pockets — inherit their panel, as specified.
- **Checks confirmed free, as predicted.** A coordinate rotation carries whatever is in the tile,
  so a check's two axes turn together with no check-specific code. No separate 2D path was needed.
- **Deliberately NOT segmented: the side view's sleeve.** Seen in profile the arm hangs in front
  of the torso in depth, so it occupies the middle of the silhouette, not its edges — the corridor
  rule that is right on front and back marks the front and back edges instead, which is simply
  wrong. Left as torso rather than encoding a wrong segmentation. This is the one place the shipped
  grain is knowingly incomplete (side views get lapel + collar, no sleeve lean).

### ⭐⭐⭐ Session 5 (same day) — SHOPIFY EMBED BUILT (draft page, Prestige theme)

`/pages/design-your-suit` exists as a **DRAFT** page (`gid://shopify/Page/117734375611`,
templateSuffix `configurator`) on the **Prestige theme "Updated copy of Prestige New 1"**
(`149240774843`, serves at `t/59`). **You publish it** — the connector blocks both live-theme
writes and theme publishing, by design.

- **⚠ THE LOAD-BEARING FINDING: Shopify's CDN silently RE-ENCODES anything it sniffs as an
  image — in Files AND in theme assets, whatever the extension.** Measured on the same lossless
  normal map: `.webp` in Files → served `image/jpeg`, 149,308 → 46,417 bytes, **max pixel diff
  20**; renamed `.txt` with `text/plain` → *identical* transcode (it sniffs content, the
  extension is irrelevant); as a theme asset → stored fine but **served** re-encoded too. That
  would have quietly corrupted the normal maps and, far worse, the PANEL MAP, where a value of 3
  becoming 4 puts the wrong grain on pixels. **Never host this project's data maps as images on
  Shopify.** Full detail in the `gcc-shopify-cdn-asset-fidelity` memory.
- **But `.js` is served BYTE-EXACT and gzipped**, so the answer was to keep the data-URIs exactly
  as they are and ship them inside JS bundles. Shopify minifies the JS (strips whitespace,
  unquotes keys) — verified that **all 150 embedded data-URI payloads stay byte-identical**,
  because minifiers don't touch string contents.
- **Three files, built by `GCC_SPLIT=1 python3 builder/build_configurator_v0.py` → `dist/`:**
  - `gcc-configurator-core-v2.js` — 2.79 MB, **1.99 MB over the wire**. Compositor + CSS + markup
    (it injects its own DOM) + the 5 FRONT cut-views. This is the initial load.
  - `gcc-configurator-views-v1.js` — 4.13 MB, fetched on the first Side/Back click.
  - `templates/page.configurator.liquid` — 488 bytes, `{% layout none %}` + two script tags.
- **`{% layout none %}` is deliberate**: the configurator's CSS uses generic class names
  (`.app`/`.main`/`.rail`/`.grid`/`.row`) that would collide both ways with a theme stylesheet,
  and it carries its own topbar and Add-to-cart. Rendering outside the theme layout guarantees
  the look that was verified locally. Trade-off: **no site header/nav on that page.**
- **Verified against the REAL CDN URLs in a browser** (not just locally): minified core loads,
  injects markup, renders; Side click lazy-loads the views bundle; pinstripe side view renders
  with the Path A grain intact; zero console errors. Lazy load took ~12 s on this machine — most
  of it building 10 cut-views' warp fields, not download — behind a progress indicator.
- **Upload mechanics that work** (see also §7): `stagedUploadsCreate` → **`curl -F` from local
  disk** → `fileCreate`. Bytes must NEVER go through a tool-call payload — a hand-transcribed
  base64 got truncated 6,616 → 3,519 bytes today, the same failure as the handover's existing
  "retype→403" gotcha. `themeFilesUpsert` accepts a `URL` body for **assets** (verified
  byte-exact) but **not for `templates/*.liquid`** — that silently no-ops, hence the tiny
  hand-typeable template.
- **Left behind, needs manual deletion in the admin** (`themeFilesDelete` is blocked): two
  39-byte stubs in the Prestige theme, `assets/gccfg-test-panel.png` and
  `assets/gccfg-test-serve.webp`.

### ⭐⭐ Session 5 (same day) — deliverable 10.97 → 6.60 MB, from the normal maps' RESOLUTION

The normal maps were **64% of the whole file** (482 KB x 15 = 7.1 MB). They are now emitted at
**half linear resolution**, which cuts the deliverable by 40% with a measured, invisible cost.

- **Codec fidelity and RESOLUTION are different questions.** The playbook's "normal maps must
  stay LOSSLESS" rule came from measuring lossy codecs at 18-20° of angular vector error — that
  rule is untouched, they are still lossless WebP. But the compositor consumes this map in only
  two ways, and both discard high frequencies: `dispX/dispY`, which is **box-blurred at NSMOOTH
  (22 px at W=1300)** and capped at `WARP_CAP`; and `graze`, a broad grazing-angle sheen term.
- **Measured at half scale** on front/side/back: displacement error **p95 0.05–0.12 px, MAX
  0.30 px against a 12 px warp cap**; graze error p95 <0.01. Sub-pixel.
- **Verified on the actual composite**, all 15 cut-views: mean difference **0.043 levels out of
  255**, p99 = 1 level, only 0.16% of pixels differ by more than 2 levels. Visually identical at
  high zoom on a pinstripe chest, which is where a sub-pixel warp shift would show first.
- **No JS change was needed** — `buildWarpNormal` already does `drawImage(nimg,0,0,W,H)`, so the
  browser upsamples whatever it is handed.
- Quarter scale was also measured (max 0.75 px, ~5.4 MB total) and NOT taken: 0.5 is comfortably
  sub-pixel and the extra ~0.9 MB is not worth doubling the error. `NORMAL_SCALE` is a named
  constant in the builder if that trade ever looks different.
- **Remaining breakdown at 6.60 MB:** normal 2.5, base (JPEG q82) 1.74, drape (JPEG q90) 1.16,
  mask 0.49, panel 0.12, fabrics 0.18, options 0.16. The next real lever is no longer compression
  — it is that **10 of the 15 cut-views are side/back**, so externally hosting those would leave a
  front-only initial load of ~2.2 MB. That is architectural and pairs with the Shopify embed.

### ⭐⭐ Session 5 (same day) — the side/back shoulder blotch FIXED, and the diagnosis was wrong twice

Found while verifying Path A on a navy pinstripe: the garment masks were leaving a broad ragged
band of the shoulder and upper arm OUTSIDE the mask, so the compositor left the grey BASE RENDER
showing there. Invisible on the grey house cloth, glaring on any coloured one. Recorded until now
as a "2-3px soft sliver … (natural)" minor defect; measured at **3.2–9.5% of the jacket on side
views, runs up to 31 px** (front/back 0.8–1.7%).

- **The standing diagnosis was wrong, and so was my first one.** Session 3's fix was a BRIGHT-
  highlight reclaim, on the theory the shoulder cloth was too bright for the `V_MAX` ceiling. It
  isn't: measured on `side_2button_notch`, the missing pixels read **V 0.29–0.61 (median 0.42) —
  comfortably dark enough** — but **R−B +5..+13 (median +11)**, just over `BLUE_BIAS`=8. They are
  warm-tinted cloth lit by the warm key, and **82% of them failed the old reclaim's `V >= 0.50`
  floor**, which is why a reclaim aimed at exactly the right region never touched them.
- **Fix: drop the V floor from that reclaim** (now `RECLAIM_*`, not `HILIGHT_*`) so it covers
  mid-dark warm cloth as well as bright highlights. Deliberately NOT done by raising `BLUE_BIAS`,
  which would loosen the classifier over the whole frame including where no garment is near; the
  reclaim is gated to low-saturation pixels adjacent to *confident* garment and outside a 6 px
  background margin. **Saturation is the real discriminator** — cloth 0.11, skin 0.24+, hair
  0.31–0.43 (only ~1% of hair px pass, and the connected-blob step drops those).
- **Second pass on the residue.** What survived was all *enclosed* interior holes failing only on
  saturation (S 0.15–0.18 vs a 0.15 ceiling). Raised the ENCLOSED-hole fill's ceiling to 0.20
  instead of loosening the edge-adjacent reclaim — enclosure is a far stronger guarantee than
  adjacency, and **zero hair pixels are enclosed on any render** (hair opens to the background
  above the head), so it cannot let hair in.
- **Result, measured on all 15 cut-views:** missed px **122,420 → 71,441 (−42%)**; side views
  **3.98/7.31/12.03/6.49/4.52% → 1.73/2.78/3.42/2.47/2.31%**; and the number that matters most,
  **max run width on side views 37–52 px → 10–12 px** — the wide bands are gone and what remains
  is the intended antialiased silhouette rim. **falseSkin 0 before and after; falseBackground
  2423 → 2427** (noise). Confirmed by eye on all 15, not just by the metric.
- **Also: `make_mask` got ~4x faster.** PIL's `MaxFilter(31)` in the skin-bounce reclaim was 8 s a
  render, ~85% of the whole mask build. Swapped for the file's own separable `_dilate` — verified
  **bit-identical** and ~320x faster on the real image size.
- **Knock-ons checked, both clean.** Drape maps regenerated for all 15 (Marigold normals did NOT
  need it); coverage moved +0.00 to +0.42 pp. Colour re-measured with `audit/calib.py`: **97% of
  the mill scan vs the 98% on record** — unchanged within noise, so `DRAPE_TARGET_MED` was left
  alone rather than chased for a 1.3% suggestion. Path A angles re-measured after the mask change
  (the segmentation reads the mask): lapel −17.3°, collar +86.7°, torso unmoved — no drift.

### ⭐⭐⭐ Session 4 (2026-07-22) — Path A research plan EXECUTED, grain spec delivered

Ran `plan/PATH_A_RESEARCH_PLAN.md`'s R1-R4 to completion. Full result:
**`plan/PATH_A_GRAIN_SPEC.md`** — read that before touching the compositor. Summary:

- **Two mechanisms, not three.** The crux question's silhouette-width-taper option (`SIL_WRAP`)
  is now confirmed absent from *every* reference measured this session (a flat CAD panel sweep on
  a fresh live asset, on top of the already-known torso result) — don't resurrect it per-panel.
- **Lapel: NEW fixed-angle rotation, ±11° from vertical**, mirrored L/R. Measured from
  Suitsupply's photographic hero still, cross-checked against an isolated flat CAD `lapel` layer
  pulled live off their CDN (which reads ~3x steeper, ~30° — that's their stylized configurator
  icon, not physically representative; we target the photo-real number since our renders are
  photographic-quality like their hero shot, not their icon).
- **Sleeve: probably no new mechanism needed** — measured ±5°, but recommend verifying the
  *existing* normal-driven warp against that target (once the sleeve has its own panel mask)
  before writing a new fixed-rotation path, since Marigold's normal map is a real capture of the
  sleeve's own geometry.
- **Collar: NEW fixed-angle rotation, ~85-90°** (near-horizontal) — well-grounded by R1's deep
  research: the undercollar is conventionally cut on the true bias for structural reasons
  (3-0 vote, 4+ independent tailoring sources).
- **Seam rules (R1):** center-back is a **collar-continuity phase match, not a mirror** — the two
  back panels sit one repeat apart at the collar, gap varies down the back; sleeve matches the
  body at **one prominent line at the chest/armhole junction only**, rest is free; pocket
  jett/flap matching is a **genuine, named disagreement between bespoke houses** (no single right
  answer — default to inheriting the panel's grain); checks/windowpane get the same seam
  priorities as stripes, just a stricter 2D (both-axis) match requirement at whichever seams do
  get matched.
- **No prior art anywhere.** Surveyed Proper Cloth, Indochino, Black Lapel, Threekit, Unspun,
  MTailor, Son of a Tailor — nobody publicly does live per-panel pattern wrap. Targets had to come
  from measurement + tailoring convention, not from copying a competitor.
- **Asset-identity correction:** `audit/ss/model_*.png` were mis-identified as waistcoat layers
  in earlier sessions — live teardown confirms they're actually Suitsupply's `Jacket/model`
  component (the torso shell with sleeves/lapel/pockets removed, composited separately). Doesn't
  change any prior conclusion (Session 2's torso-parity measurement was comparing the right thing
  either way) but worth knowing if you go back to those files.
- **Tooling:** `audit/panel_angles.py` rewritten (was buggy — the coherence ratio it inherited
  from `pattern_map.py` blows up on flat/uniform regions, background or a cutout's own silhouette
  edge, and reads as false "pattern"; fixed with a real subject mask + energy floor + optional
  erosion). Use this, not `pattern_map.py` directly, for any future per-panel angle work —
  including the sleeve/back verification the spec above calls for as still-open.
- **Not done this session (deliberately — research-first per the approved plan):** no compositor
  code changed. `plan/PATH_A_GRAIN_SPEC.md`'s "Implementation sequencing" section is the next
  session's starting point.
- **Addendum (same day): checks/windowpane, not just stripes.** The R2 measurement above is
  stripe-only. Went back and visually confirmed (isolated native-res check-fabric layers pulled
  live) that a check's grid rotates as ONE RIGID UNIT on the lapel — both axes tilt together,
  staying perpendicular — same qualitative behavior as a stripe. **This means Path A's planned
  fixed-angle rotation needs no separate 2D-pattern code path** — it's a coordinate rotation, so it
  rotates whatever's in the tile automatically. A hard quantitative angle number for checks
  specifically wasn't obtained (the stripe measurement method doesn't transfer — see the addendum
  in the spec for the real technical reason) but isn't needed given the mechanism finding.
- **Addendum 2 (same day): cross-checked against real, non-Suitsupply suit photography —
  ±11°/±5° are now FLOOR estimates, not final targets.** Every number so far came from one source
  family (Suitsupply). Pulled two independent real photos from Permanent Style (a checked jacket,
  a chalk-stripe DB) and re-measured. The mechanism held up (lapel tilts, torso doesn't); the
  **magnitude didn't** — the real checked jacket's lapel visually read as 15-30°, well above the
  11° the single Suitsupply photo gave. Sleeve re-measurement hit its own catch: an automated
  reading that "converged" cleanly to +11-12° turned out, on inspecting a diagnostic overlay, to
  be measuring the sleeve's own silhouette edge against the background, not the pinstripes at
  all — once corrected, the real signal was too noisy in that particular photo to get a clean
  number. **Implement Path A with 11°/5° as starting points, then tune by eye against the render**
  — don't treat them as fixed. Full detail + the methodological lesson (automated angle
  measurement is reliable on studio photography and CDN layers, not on casual/editorial real
  photos) is in `plan/PATH_A_GRAIN_SPEC.md`'s "Addendum 2".
- **Addendum 3 (same day): confirmed directly with KuteTailor that their factory actually does
  this.** The render only matters if the delivered garment can reflect it — checked
  `platform.kutetailor.com` (logged in as the ARUAP account) and found a real, orderable house
  product (`26AWM2P203`/`DBV9300`, a check DB jacket) whose own 18 product photos show the exact
  same pattern-matching behavior as everything else this session: lapel tilts, body stays
  orthogonal. **Their cutters can and do produce this** — strongest possible evidence, since it's
  KuteTailor's own manufactured sample, not a competitor's marketing photo. Caveat: the order
  platform's preview is a fixed hero photo per style (doesn't regenerate per fabric swatch), and
  there's no pattern-matching field anywhere in their craft-code catalog to explicitly request or
  verify it per order — so this is strong evidence of *capability*, not a per-order guarantee.
  Detail in `plan/PATH_A_GRAIN_SPEC.md`'s "Addendum 3".

### ⭐⭐ Session 4 (same day) — Suitsupply render-architecture teardown

Follow-on to the grain-spec work: a full technical audit of Suitsupply's live configurator's
rendering engineering (layers/dimensions/style-code taxonomy, explicitly NOT sizing/UI). Full
result: **`plan/SS_RENDER_ARCHITECTURE_SPEC.md`**. Headline: **it validates GCC's own
architecture rather than changing it.**

- **Exact-percentage proof that Suitsupply's geometry is fixed per style, fabric-independent**
  (99.9%+ pixel-identical alpha masks across two different fabrics, same style) — the same
  architecture GCC's compositor already uses (one mask per cut, cloth swapped at runtime).
- **Confirmed their jacket has NO live per-panel pattern rotation to reverse-engineer** — it's 11
  pre-baked PNG layers per fabric SKU (model/shoulder/lining/chest-pocket/lapel/pocket/buttons×3/
  stitching×2), offline-rendered, not computed client-side. Trousers get 3 rotation angles (33
  images total); waistcoat is 5 layers, captured for the first time this session. Jacket itself
  has NO side/back view in their tool at all (front only) — confirms the existing
  `gcc-pattern-render-playbook` memory note on this rather than adding anything new.
- **Delivered canvas is a fixed 900×1125 for every layer**; native/source resolution is much
  higher and differs by garment (jacket 3280×4100, trousers 2000×2500) — same aspect ratio as
  delivery, clean downscale. Confirms GCC's own 1792×2400→W=1300 relationship is the same shape
  of decision, just scaled to GCC's budget.
- **Style-code taxonomy decoded:** every layer's path is `{shared prefix}_{layer-specific
  suffix}` — changing Closure updates the prefix on all 11 layers at once; each layer's own
  suffix only changes when that specific option changes. DB closures auto-default the lapel to
  Peak (sticky, independently editable after) — matches GCC's own `CUTMAP` constraint
  (`build_configurator_v0.py:483-484`) at the underlying-convention level.
- **Re-verified the Session 3/4 asset-identity question a second, independent way** (direct pixel
  comparison of fresh isolated jacket vs. waistcoat pulls against the local `model_*.png` files)
  — confirms the correction already made above; `model_*.png` really is the jacket, not the
  waistcoat.
- **No action items for the compositor** — this was a validation pass, not a gap-finder. See the
  spec's "What this means for GCC" section for the point-by-point mapping to `buildPanels`/
  `buildWarpNormal`/`warpedCloth`.

- **`configurator-v0.html`** — self-contained, **6.60 MB** (15 cut-views incl. side/back),
  data-URIs, zero external refs. ⚠ **Still heavy for a Shopify embed** — compression is done
  (§2); externally host the 10 side/back cut-views before embedding (§6 item 2).
- **Right-rail UI** (user-approved). Stage + rail (Fabric / Style / Measurements). Bottom-left card
  now has a working **Front / Side / Back** view toggle.
- **17 cloths** — 10 Elite + 2 Elite pinstripes (DBT6860, DBU081A) + 5 Prestige test.
- Add-to-cart → Shopify container product; "View details" → real KuteTailor `saveOrder` spec.

### ⭐⭐ Session 3 (2026-07-22) — consistent man, front/side/back, Path A prototype (commits `a4bb539`→`6666b3f`)

- **ALL 5 CUTS now the SAME man, and FRONT/SIDE/BACK all exist.** Regenerated the 4 non-notch
  fronts off the notch hero (identity held) + generated 10 side/back renders → 15 total. The "man
  changes when you switch cut" problem is GONE. Pipeline: `gen_model.py` (hero as ref) →
  `normalize_render.py` → shoe-neutralise → `make_mask` → `make_drape` → Marigold → build. Marigold
  ran at **N_RES=448** (~5 min/render, Chrome closed to free RAM — the 8GB M1 swap-thrashes at
  768/apps-open; `finish_renders.sh` is the one-shot). `gen_normals_all.py` now takes cut names as
  args.
- **View dimension WIRED** in the builder: assets keyed `"<cut>__<view>"`; `CUTVIEWS` per-cut
  availability; Front/Side/Back control drives `curView`; `render()` uses `cutAssets[cut+'__'+vv]`.
  All 15 cut-views load, 0 console errors.
- **Mask fixes** (`make_mask.py`): **connected-component keep** (drops the hair blob the classifier
  catches on cooler side/back); **shoulder-highlight reclaim** (grey shoulder patches on side/back
  were mid-tone cloth in the ramp's partial-alpha zone — full alpha to neutral interior cloth V
  0.50-0.85, silhouette edge kept soft); **found + fixed** `ImageDraw.floodfill` being a silent
  no-op on 'L' images in Pillow 11.3 (RGB now). Added fast separable `_dilate`.
- **PATH A prototype BUILT** (`builder/pathA_prototype.py`) — proved live per-panel pinstripe wrap
  is feasible: segment garment into panels, grain per panel → lapels diagonal, torso vertical.
  Angles were GUESSED; seams ragged. **Next step is the approved research plan
  `plan/PATH_A_RESEARCH_PLAN.md`** (measure SS per-panel angles + tailoring convention + resolve
  the grain-rotation-vs-surface-vs-taper question), THEN port into the compositor. User chose Path A
  (live per-panel) over AI-baking the pinstripes.

### ⭐ Session 2 (2026-07-22) — what changed since the table below was written (commit `0e66499`)

- **Crease depth FIXED — and the lever was the COMPOSITOR, not the base render.** The old §6.2
  claim ("lever is a hero prompt change") was measured and **overturned**: the render already had
  SS-deep creases (p1/med 0.060), the drape file 0.045; `soften_drape` + the overlay were
  flattening them to 0.25. Fixed with a structural-crease restore in `soften_drape` (+drape JPEG
  q90) → **composite 0.073**. Fabric-independent, applies to every cloth. Residual: shadow p5
  still ~0.40 vs SS 0.19 (deliberate stop — deeper needs touching the locked fold look).
- **Pattern wrap RESOLVED as a non-issue.** Measured at matched px/cm: torso is already at SS
  parity (spread 22.2 vs 23.1; swing 5.6 vs their 2.8). `SIL_WRAP` measurably *regresses* both and
  shears sleeves → **tried-and-rejected** (§8). The "22.7° swing" was the full-silhouette splay
  incl. sleeves, a per-tube effect, never a torso property.
- **Stripe source fixes** (`prep_fabrics.py`): scans were leaning up to 1.3° → **deskew** +
  motif-period-snap; **SS-style line-width floor** (2.2 canvas px, gated to thin-line/wide-pitch)
  — SS's "clean lines" are drawn ~2× physical width, a display idealisation, not fidelity;
  contrast **B (0.85)** locked for stripes.
- **Mask fixes** (`make_mask.py`, recall 1.000 on all 5 cuts): skin-bounce reclaim (hand smudges),
  hull-based shoe cut (stripes no longer composite across black leather), enclosed-hole fill
  (sleeve blotches). `WARP_CAP` 16→6.5 (stripes were S-bending in crotch/hem creases).
- **`prep_fabrics.py` normalisation anchors FROZEN** → the 117-batch blocker (old §6.5) is
  resolved; existing 9 fabrics' params verified byte-identical.
- **All 5 cuts re-piped** (masks + drapes regenerated to this pipeline).
- **Baked-still experiment** (SS fabric-step architecture) added then **disabled** — the catalog
  still is a different model/pose than the compositor's house model, so switching tabs swapped the
  man (user rejected). Code path retained in the builder (`STILLS` dict) for when stills are baked
  on the house model.
- **Research done** → `plan/RESEARCH_FINDINGS.md` (adversarially reviewed). Conclusion:
  **difficulty-routing** — keep the compositor for the ~85% easy majority (at parity), AI-bake only
  the ~27–29 bold directional patterns, after a validation gate (bake a pinstripe+windowpane onto
  the *standing* house render, compare vs compositor) and after the 14 renders land.

### Measured against Suitsupply (their **photographic model** layer)

| | Ours | SS | |
|---|---|---|---|
| Colour vs mill scan | 98% | 105% | ✅ |
| Pattern scale | 0.99× true | true | ✅ |
| Pattern sharpness | 95% of true cloth | — | ✅ |
| Moiré | none | none | ✅ |
| Specular (p99/med) | 3.08 | 3.30 | ✅ |
| On-screen cloth density | 9.95 px/cm @1448×1086 | 10.3 | ✅ |
| Pattern wrap (torso, matched px/cm) | spread 22.2 / swing 5.6 | 23.1 / 2.8 | ✅ parity (Session 2) |
| **Crease depth (p1/med)** | ~~0.24~~ → **0.073** | **0.031** | ✅ fixed in compositor (Session 2) |
| **Shadow depth (p5/med)** | **~0.40** | **0.19** | 🟡 residual, deliberate stop |
| **Lapel grain** (front, measured) | ~~−7.5°~~ → **−17.3°** | −12.1° photo / −30.6° CAD | ✅ live (Session 5) |
| **Collar grain** (back, measured) | ~~−0.8°~~ → **+86.8°** | −85 to −90° (CDN layer) | ✅ live (Session 5) |

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
│   ├── panels.py                   ⭐ Path A: panel segmentation + PANEL_ANGLES (the grain table)
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

## 6. Next actions, in priority order (revised Session 5, 2026-07-23)

1. **Tune the grain by eye on more cloths, if it wants it.** Path A is DONE and shipping (§2);
   `PANEL_ANGLES` in `builder/panels.py` is the one place to change it, and the calibration note
   there explains why rendered ≈ table + 4° on the lapel. Only the two Elite pinstripes
   (DBT6860, DBU081A) have really been judged — worth a look on a check/windowpane, where the
   prediction is that both grid axes rotate together with no extra code.
2. **Publish the embed.** Built and verified (§2) but DRAFT. To go live: publish the Prestige
   theme `149240774843`, then set the page `gid://shopify/Page/117734375611` to published. Both
   steps are blocked for the connector, so they are yours. Preview first via the theme preview —
   the page is a draft, so you need to be signed in as staff to see it. Decide too whether
   `{% layout none %}` (no site header/nav on that page) is what you want.
3. **Difficulty-routing bake fallback (`plan/RESEARCH_FINDINGS.md`)** — only if Path A quality is
   judged insufficient: AI-bake the ~27–29 bold directional fabrics onto the STANDING render (run
   the validation gate first). Path A is preferred (one-time, all-fabrics, live) and is now built.
4. **Batch all 117 fabrics** — UNBLOCKED (anchors frozen); spot-check outliers.
5. **Register `orders/paid` webhook** + wire the backend.

**Minor known defects (noted, non-blocking):** deliverable size (6.60 MB, #2 above); the side
view has no sleeve panel, so it gets lapel + collar grain but no sleeve lean (§2, deliberate);
a thin antialiased rim at the shoulder silhouette on side/back, which is the coverage ramp
working as designed (the broad blotch that used to be filed here was real and is now fixed, §2).

**DONE Session 5:** Path A implemented end-to-end — `builder/panels.py` segmenter + per-panel
rotation in the compositor, shipped at lapel ±16 / sleeve ±5 / collar 87, no torso regression
(0 leaked pixels); side/back shoulder mask blotch diagnosed and FIXED (missed px −42%, side-view
run width 37-52px → 10-12px), make_mask ~4x faster; deliverable 10.87 → 6.60 MB via
half-resolution normal maps. **DONE Session 4:** Path A research plan (R1-R4) executed — `plan/PATH_A_GRAIN_SPEC.md` delivered;
`audit/panel_angles.py` fixed (was silently wrong on flat/uniform regions). **DONE Session 3:** 14
renders + consistent man across cuts, front/side/back views wired, mask hair/shoe/shoulder fixes,
Path A prototype. **DONE Session 2:** pattern wrap (rejected as global), crease depth (compositor
fix), prep normalisation (anchors frozen), stripe deskew + line floor.

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
  anchoring the drape median at 128 · **silhouette pattern wrap `SIL_WRAP` (Session 2 — torso is
  already at SS parity; it regresses spread + swing and shears the sleeves)**.
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
