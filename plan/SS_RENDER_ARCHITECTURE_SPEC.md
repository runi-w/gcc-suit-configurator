# Suitsupply render-architecture teardown — R2/S1-S5 findings

_Companion to `plan/PATH_A_GRAIN_SPEC.md`. That doc covers pattern ANGLES per panel; this one
covers the render ENGINEERING — layer inventory, dimensions, and what's fixed vs. what varies —
gathered by directly driving Suitsupply's live `custom-made` configurator and its CDN. Scope
agreed with the user: rendering architecture only, not customer-facing sizing/UI design; nothing
downloaded here is reused as content in GCC's product, only as measurement data (same boundary
`plan/PATH_A_RESEARCH_PLAN.md` already operated under)._

## TL;DR — what this confirms about GCC's own approach

**Suitsupply's architecture is exactly what GCC's compositor already does, just executed at much
larger scale: one fixed geometry mask per style, fabric swapped in as a texture.** S3 proved this
with an exact number (99.9%+ pixel-identical alpha masks across two completely different
fabrics). There is no live per-panel pattern rotation anywhere in their system to reverse-engineer
— every component is a pre-baked PNG, one offline render per fabric SKU. GCC's Path A (live,
client-side per-panel rotation) is not replicating anything Suitsupply does; it's solving a
problem their architecture doesn't attempt to solve at runtime at all.

## S1 — full layer inventory

### Jacket: 11 layers, stable
`baselayer` (torso shell, no sleeves) + 10 `otherlayer_N`, confirmed identical in count and role
across three closures tested (1-button, 2-button, 6-button DB):

| layer | CDN path | content |
|---|---|---|
| baselayer | `Jacket/model/{style}` | torso shell only |
| otherlayer_0 | `Jacket/shoulder/{style}` | sleeves |
| otherlayer_1 | `shared/lining/{style}` | inner lining (visible in the V-opening) |
| otherlayer_2 | `Jacket/chest-pocket/{style}` | chest welt |
| otherlayer_3 | `Jacket/lapel/{style}` | both lapels + collar band, one cutout |
| otherlayer_4 | `Jacket/pocket/{style}` | side pocket flaps |
| otherlayer_5,6,7 | `shared/buttons/{style}` | three button-layer variants (see S4 — the 3rd is a conditional layer keyed `undefined` when not applicable to the current pocket style) |
| otherlayer_8,9 | `Jacket/stitching/{style}` | topstitching, keyed off the lapel code |

An earlier capture this session appeared to show only 8 layers for one fabric — confirmed to be
a **race condition** (DOM read before full hydration), not a real style-driven difference: a
second, settled read of the identical state returned all 11. Lesson for any future automated
capture of this site: always re-read after an explicit wait, don't trust the first read.

### Trousers: 11 layer types × 3 rotation views = 33 images
Every trouser layer comes in three angle variants (`_R00`, `_R01`, `_R02`) baked directly into
separate CDN assets — not a client-side rotation, three independently pre-rendered views:

`waistband`, `pocket` (×4 distinct components — front slant, a second front variant, a welt/cap
variant, back jetted), `details` (waistband strap/lining), `turnup` (hem style), `buttons` (×3,
one per relevant component), `drawstring` (the inner waistband adjuster — matches GCC's own
"snugtex" terminology already in `PANTS_DEF`). This is a much heavier asset set than the jacket's
single-view 11.

### Waistcoat: 5 layers, captured for the first time this session
`baselayer` is itself named `Waistcoat/lapel/{style}` (no separate "model" torso base the way the
jacket has one — the waistcoat's V-opening IS its base shape) + `pocket` (lower welts) +
`lining` (back lining/strap — matches GCC's own `VEST_DEF` "Back: Matched lining + strap") +
`buttons` ×2 (again, one conditional).

**Asset-identity correction, verified by direct pixel comparison:** the already-mislabeled-twice
`audit/ss/model_*.png` files were re-checked against fresh isolated pulls of both the jacket's
`model` layer and the waistcoat's `lapel` layer this session. The local files are unambiguously
the **jacket** (2-button, same proportions and hem shape as the fresh `Jacket/model/MBN2` pull) —
**not** the waistcoat (5-button, visibly different pointed hem, confirmed on a fresh
`Waistcoat/lapel/CSB5BN2...` pull). This reconfirms the correction already made in
`plan/PATH_A_GRAIN_SPEC.md` / `HANDOVER.md` §2 Session 4 — worth having now checked it twice,
independently, since the two candidate identities looked confusingly similar at a glance.

## S2 — dimensions & canvas conventions

**Delivery (runtime) resolution: 900×1125 for every single layer captured this session** —
jacket, trousers, waistcoat, every style/fabric variant — via an identical Cloudinary transform
(`c_fit,f_auto,h_1125,q_auto:good,w_900`). This is a hard-fixed delivery canvas, not something
that varies per garment or style.

**Native (source) resolution is much higher and differs by garment**, found by fetching the same
CDN paths with the transform segment stripped:

| garment | native canvas | delivery canvas | downscale factor |
|---|---|---|---|
| Jacket (`model`, `lapel`) | 3280×4100 | 900×1125 | ~3.64× linear |
| Trousers (`waistband`) | 2000×2500 | 900×1125 | ~2.22× linear |

Both native canvases share the exact same 4:5 aspect ratio as the 900×1125 delivery canvas — the
downscale is a clean resize, not a re-crop. The jacket's 3280×4100 native size exactly matches
the pre-existing local reference `audit/ss/nat_model.png` from an earlier session, confirming that
file was captured the same way (untransformed CDN pull) and is a legitimate high-fidelity
reference, not a mismatched asset.

**Reading:** Suitsupply's production pipeline renders at a much higher fidelity than it ever
serves to the interactive configurator — the delivered 900×1125 is a deliberate bandwidth/perf
choice, not their actual asset ceiling (likely the "Zoom" feature seen in the UI, or their
static product photography, draws on the higher-res master). GCC's own render pipeline
(1792×2400 source → W=1300 canvas) follows the same shape of decision — serve smaller than the
source for runtime performance — just at different absolute numbers suited to GCC's scale and
budget. No action item here; this is a validation, not a gap.

## S3 — fixed-geometry-per-style test (the load-bearing finding)

Directly tested whether the SAME style code produces the SAME garment geometry regardless of
fabric, by pixel-diffing the alpha channel of five jacket components between two completely
different products (a black solid and a navy chalk stripe), both on the default 2-button/notch
base style:

| layer | style code identical? | exact match | IoU |
|---|---|---|---|
| model | yes | 99.985% | 99.961% |
| shoulder | yes | 99.989% | 99.921% |
| chest-pocket | yes | 99.997% | 99.367% |
| lapel | yes | 99.989% | 99.805% |
| pocket | **no** (`SPJ4` vs `SPF5.5`) | 99.127% | **17.191%** |

Every layer with an identical style code matches at 99.9%+ pixel-exact regardless of fabric — the
residual fraction of a percent is anti-aliasing noise at the silhouette edge, not real geometry
drift. The one outlier (`pocket`) turned out to have a genuinely **different** style code between
the two sampled products (different pocket-flap width, unrelated to fabric) — a clean natural
experiment showing the geometry tracks the style code in both directions, not a coincidence.

**Confirmed: garment geometry is fixed per style, independent of fabric.** This is the same
architecture GCC's own compositor already uses.

## S4 — style-code taxonomy (what changes which layer)

Systematically varied the Closure and Lapel options on one product, capturing the full layer set
after each change (with an explicit wait + re-read after the race-condition lesson from S1).

**Every jacket layer's CDN path is `{leading style code}_{layer-specific suffix}`.** The leading
code (`MBN2` = 2-button, `MBN1` = 1-button, `MBN6DB` = 6-button DB) is **shared across every
single layer** — changing Closure updates that prefix on all 11 layers at once, while each
layer's own suffix (`_SS3` shoulder, `_CPBS1` chest-pocket, `_LN1_NLWS2` lapel, `_SPF5.5_TPN2`
pocket, etc.) stays completely untouched unless you change *that specific* option. This confirms
each visible layer really is an independently-parameterized component; the leading code is best
understood as "which base torso-panel silhouette" (closure count reshapes the whole front, so
every layer that overlays it needs to be drawn against the matching base), not a per-layer style
choice.

**Closure and Lapel are linked but not locked together.** Selecting a Double-Breasted closure
auto-switches the lapel from Notch (`LN1`) to Peak (`LP2`) as a sane default — real tailoring
convention (DB jackets are conventionally always peak). But the lapel choice is **sticky and
independently editable afterward**: reverting Closure back to 2-Button did *not* revert the lapel
back to Notch; it stayed on Peak until explicitly changed. GCC's own `CUTMAP` in
`build_configurator_v0.py:483-484` hard-locks DB to a single "db" cut regardless of lapel
selection — Suitsupply's live default-then-editable behavior is more flexible than that, but
matches the same underlying tailoring fact (DB defaults to peak) that GCC's CUTMAP already
encodes as a constraint. Not a gap to close, just confirms GCC's simplification is grounded in
the same convention SS's own defaulting logic uses.

**Stitching layers are derived from whichever component they stitch** — the two `stitching`
layers' codes always mirror the current `lapel` code exactly (`{prefix}_{lapel-code}_HAMF2mm2`
/ `_BHFUNC1`), confirming they're not an independent style axis, just a rendering of the seams
implied by the current lapel choice.

**Layer count never changed across any tested combination** — 1-button, 2-button, and 6-button DB
all produced exactly the same 11-layer set (just different codes within it). No evidence of
layers being added/removed for more complex closures; DB is achieved within the same `model` and
`lapel` layers redrawn for that silhouette, not an extra overlay layer.

## S5 — cross-view consistency

**The jacket has no side/back rotation set in this tool — front only.** Confirmed by DOM
inspection: the jacket's image container has plain `otherlayer_N` alts (no `_rotation` suffix),
while the trousers container's images are *only* `_rotation`-suffixed (×3 each). Waistcoat is
also front-only, same as the jacket. This matches the already-known finding in the
`gcc-pattern-render-playbook` memory ("Back view is DISABLED — only front renders exist" for
Suitsupply) — now confirmed directly rather than inferred. **Suitsupply invests the 3-angle
asset cost only where it matters most for fit confidence (trousers), not everywhere.**

## What this means for GCC's `build_configurator_v0.py`

Grounded against the actual functions (all line numbers current as of this session):

- **`SIL_WRAP` (line 494, applied inside `buildWarpNormal` at 507-538) stays disabled.** S3's
  exact-match numbers are one more independent confirmation — on top of Session 2's torso
  measurement and the Path A grain-spec's own CAD-layer sweep — that no competitor, including the
  one with by far the largest render budget, does anything resembling a silhouette-width-driven
  pattern taper. Nothing in this teardown reopens that question.
- **`buildPanels` (line 539) is GCC's analogue of Suitsupply's per-component layer split**, just
  achieved differently: SS gets independent panels for free because each is a separately-rendered
  PNG; GCC has one flat render and needs to *segment* it into equivalent regions. S1's confirmed
  jacket component list (model/shoulder/lining/chest-pocket/lapel/pocket/buttons/stitching) is a
  useful checklist for what `buildPanels` should eventually distinguish, beyond the lapel/sleeve/
  collar split `plan/PATH_A_GRAIN_SPEC.md` already scoped — chest-pocket and lower-pocket flaps
  are separate components in SS's system too, consistent with that doc's "inherit the panel
  they're cut from" recommendation (SS doesn't give them independent grain either, per the S3
  pocket-code-driven geometry change being about flap *shape*, not pattern rotation).
- **`warpedCloth` (line 568)'s per-cut, per-fabric-swap design is validated, not something to
  change.** GCC composites cloth into one fixed mask at runtime (fabric-independent asset count,
  per `HANDOVER.md` §8); Suitsupply reaches the same visual outcome by pre-rendering the fabric
  into the mask once per SKU offline instead. Different economics (SS can afford ~25,000 renders;
  GCC's own count is fabric-independent by design, per that same section) but the same underlying
  model: geometry and cloth are separate concerns, cloth doesn't touch geometry.
- **No change indicated for `CUTVIEWS`/multi-view logic** (`build_configurator_v0.py:603,698`) —
  GCC already renders front/side/back for every cut, which is *more* multi-view coverage on the
  jacket than Suitsupply's own live tool provides (S5). Nothing to catch up to there.
- **Dimension/canvas choices (S2) don't suggest a change either** — GCC's 1792×2400-source →
  W=1300-canvas relationship already reflects the same "serve smaller than the render source"
  logic Suitsupply's 3280×4100-native → 900×1125-delivery ratio does, just scaled to GCC's own
  cost/RAM constraints (`HANDOVER.md`'s 8GB M1 notes).

## Open items / not covered here
- Chest-pocket and pocket-flap style codes weren't swept as exhaustively as Closure/Lapel (S4) —
  the taxonomy pattern (shared prefix + independent suffix) is well-established enough from what
  was tested that a full sweep of every remaining option is unlikely to change the picture, but
  wasn't verified line-by-line.
- Vent style (single/double/none) wasn't captured — not visible in the options scrolled to this
  session; low priority given the taxonomy mechanism is already clear.
- Waistcoat's Style/Lapel sub-options weren't swept (only the default state was captured) — the
  5-layer inventory is confirmed, but whether closure/lapel changes behave the same way there as
  on the jacket (shared-prefix mechanism) is inferred, not directly tested.
