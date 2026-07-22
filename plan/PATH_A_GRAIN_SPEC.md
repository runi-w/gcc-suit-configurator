# Path A per-panel grain spec — R4 synthesis

_Deliverable of `plan/PATH_A_RESEARCH_PLAN.md`'s R1-R4. Written 2026-07-22. This is what makes
Path A buildable without guessing — read this before touching `buildWarpNormal`/`warpedCloth`/
`buildPanels` in `builder/build_configurator_v0.py`._

## TL;DR

Two mechanisms cover every panel, not three. The crux question's option 2 (silhouette-width
taper / `SIL_WRAP`) is **empirically absent from every reference measured** — torso, a flat
waistcoat-style panel sweep, and a flat CAD jacket layer all show zero correlation between local
panel width and stripe angle. Don't resurrect it, even per-panel.

| Panel | Mechanism | Target | Confidence |
|---|---|---|---|
| Torso (L/R) | existing normal-driven warp, **unchanged** | already at SS parity | solved (Session 2) |
| Lapel (L/R) | **NEW: fixed-angle rotation**, mirrored | **±11°** from vertical, floor estimate — see Addendum 2, real examples ran 15-30° | medium (revised down from "high" after cross-checking against real photography) |
| Sleeve (L/R) | verify existing mechanism first; small fixed rotation if needed | **±5°** from vertical, floor estimate — see Addendum 2 | medium (same revision) |
| Collar | **NEW: fixed-angle rotation** | **~85-90°** (near-horizontal) | medium |
| Back | same as torso, unverified | — | none (no asset) |
| Pockets/welts | inherit the panel they're cut from, no independent rotation | n/a | low sample, but low stakes |

**Read Addendum 2 before treating the lapel/sleeve numbers as fixed** — they held up as the right
*floor* and the right *mechanism*, but a cross-check against real (non-Suitsupply) suit
photography found real examples running noticeably higher, especially on the lapel. Implement
with these as a starting point, tune by eye against the render.

Seam rule for stripes/checks: **one-line phase match at the collar (not mirror-symmetry) for the
back seam; one-line phase match at the chest/armhole junction for the sleeve; everything else is
either genuinely disputed between tailoring houses (pocket jett) or not something our fixed
render geometry can act on (dart/seam restructuring).** Detail below.

---

## How we got here

- **R2** (in-thread): measured Suitsupply's photographic `ai-generated/ai-model` still
  (`audit/ss/aimodel_midgrey_stripe.png`) panel-by-panel with a fixed/extended
  `audit/panel_angles.py`. A first pass was contaminated by a real bug — the coherence ratio in
  `pattern_map.py`'s structure tensor blows up on flat/uniform regions (background, shirt, skin)
  because it divides by near-zero gradient energy — caught by rendering a diagnostic overlay and
  seeing the whole background light up as false "pattern," not just the garment. Fixed with a
  real background mask + a raw-energy floor in addition to the coherence threshold.
- **R2c/R3** (live teardown): Suitsupply's `custom-made` configurator composites the jacket from
  **11 separate transparent PNGs per fabric** — `model` (torso shell, no sleeves), `shoulder`
  (sleeves), `lapel` (both lapels + collar band as one cutout), `chest-pocket`, `pocket`,
  `buttons`×3, `stitching`×2 — fetched directly off `cdn.suitsupply.com/.../suitconfig/{FABRIC}/
  Jacket/{component}/{style}`. **This is not a live pattern-wrap system at all** — every
  component is pre-baked offline per fabric SKU. Downloaded the `lapel`/`shoulder`/`model` PNGs
  for a striped fabric (188.1038/1) and measured each component in isolation — the cleanest data
  in this whole pass, no photo noise. (A first pass here was also contaminated — this time by the
  silhouette outline itself, not the interior weave — caught the same way, by rendering an
  overlay and looking, then fixed with a 14px interior erosion of the alpha mask before
  measuring.)
- **A competitor survey** (Proper Cloth, Indochino, Black Lapel, Threekit, Unspun, MTailor, Son of
  a Tailor) found **no publicly documented live configurator does per-panel pattern
  orientation** — Threekit is the only true 3D/UV platform among them and has zero public
  documentation of solving this. **There is no prior art to copy; targets come from measurement
  and tailoring convention, not from reverse-engineering a competitor's live code.**
- **R1** (deep-research workflow, 93 sub-agents, 13 sources fetched, 25 claims adversarially
  voted, 9 confirmed / 16 refuted): answered the *seam-matching* half of the question well from
  grounded tailoring sources (Permanent Style / Simon Crompton's interviews with Savile Row
  cutters, corroborated by Westwood Hart and Threads Magazine). It did **not** find a documented
  degree-value for lapel or sleeve stripe angle in any source that survived verification — every
  forum explanation that would have supplied one was tested and refuted. **Our measured 9-12° and
  4-6° are empirical observations from real reference photography, not a named bespoke rule** —
  that's fine for a rendering target (we need "looks right," not "is a textbook rule"), but don't
  cite them as tailoring convention if this doc gets quoted elsewhere.

---

## Per-panel detail

### Torso — unchanged
Already at Suitsupply parity (spread 22.2° vs 23.1°, swing 5.6° vs 2.8°, matched px/cm — Session
2). The existing `buildWarpNormal` normal-driven displacement is correct here. Do not touch.

### Lapel — NEW fixed-angle rotation, ±11°
**Measurement:**
- Photographic still (`aimodel_midgrey_stripe.png`): L -12.1°, R +9.5°, each stable within ~1.7°
  across 4 vertical bands from gorge notch to breakpoint (i.e. genuinely flat, not a continuous
  roll-following curve).
- Isolated flat CAD `lapel` layer (fresh striped fabric, downloaded live): L -30.6°, R +35.8°,
  same mirrored sign pattern, ~3x the magnitude.
- The asymmetry (12.1 vs 9.5 on one asset, 30.6 vs 35.8 on the other, in **opposite** directions)
  is measurement noise from crop-box placement in a tapered/pointed region, not a real L/R
  tailoring difference — use a **symmetric** target.

**Which magnitude to use — 11°, not 30°:** the flat CAD layer is Suitsupply's stylized
configurator icon (only has to read as "a lapel" in a thumbnail); the photographic still is their
physically-real hero shot. Our compositor renders onto a photographic-quality house-model render
— the same category of asset as their hero shot, not their flat icon — so **target the
photo-measured ~11°, not the CAD layer's ~30°.**

**Why (R1):** no source gives a degree value. The closest grounded explanation: the roll/break
line is cut on the bias of the main cloth (reinforced with a straight-grain lining strip
specifically to stop it stretching — Permanent Style, quoting a Gieves & Hawkes coatmaker). This
explains *that* the lapel behaves differently from the straight-grain body, not a specific angle.
Treat 11° as our own calibrated target, not a textbook constant.

**Mechanism:** the current compositor applies ONE heavily-smoothed (`NSMOOTH`) normal-driven warp
across the whole alpha mask — smoothing that washes out any real local lapel-fold signal from the
Marigold normal into the surrounding smoother field, consistent with the code's own comment
("the man changes when you switch cut... lapels/sleeves don't run in the correct direction yet").
A genuine fixed rotation, not a surface effect, is needed: rotate the sampling coordinate by ±11°
for lapel-panel pixels before the existing `dispX/dispY` offset, using the prototype's rotation
math (`u=(x·cosθ+y·sinθ)·dens, v=(−x·sinθ+y·cosθ)·dens`) — same shape as the disabled `SIL_WRAP`
code path, but a rigid rotation instead of a width-taper term, and gated to the lapel panel mask
only (from the extended `buildPanels`), not the whole silhouette.

### Sleeve — verify before adding a new mechanism
**Measurement:** photo ~+4-6° (flat shoulder to mid-forearm, cuff excluded as noise —
contaminated by fold/wrist); isolated CAD layer ~±2-3°, same sign pattern, smaller magnitude
(consistent with the lapel's flat-vs-photo gap, just less pronounced since the sleeve angle
itself is smaller).

**Why (R1):** no documented convention (same absence as the lapel). Note an open question R1
surfaced: sleeve angle may be a side-effect of sleeve *pitch* (the forward-hang angle cutters set
for fit) rather than a pattern-matching decision — plausible, unconfirmed, doesn't change the
target number either way.

**Mechanism — this is the one open implementation question:** unlike the lapel, the sleeve is a
real, distinctly-shaped 3D piece in the Marigold normal map (not smoothed into the torso the way
the lapel's local fold is). It's plausible the existing normal-driven warp already produces close
to +5° once the sleeve gets its own panel mask (mainly needed for the seam-phase break at the
armhole, not for the angle itself). **Recommend: implement the panel segmentation and seam break
first, render with the existing (unmodified) normal-driven mechanism applied to the sleeve's own
alpha region, measure the result against the ±5° target, and only add an explicit fixed rotation
if that first pass falls short.** Cheaper to verify than to assume.

### Collar — NEW fixed-angle rotation, ~85-90°
**Measurement:** the isolated CAD `lapel` layer includes the collar band as a distinct region;
measured -85° to -90° from vertical (i.e. running almost perpendicular to the body's grain) —
noisy (small sample, tiny sliver, sd ~42-44°) but the *direction* of the reading (nowhere near
vertical, unlike everything else on the garment) held up across two independent measurement
passes, including after the erosion fix. The photographic still's collar sliver was too small to
read at all (inconclusive, not contradictory).

**Why (R1) — high confidence:** the undercollar/collar stand is conventionally cut on the **true
bias (45°)**, for a structural reason — it must fold and stretch smoothly around the curved
neckline — not for decorative pattern display. 3-0 vote, independently corroborated across 4+
tailoring/pattern-cutting sources (fashion-incubator.com, patternscissorscloth.com,
biasbespoke.com, dpstudio-fashion.com). This is the strongest-grounded finding in the whole spec.
A note of caution: a separate, more specific claim — that the *visible outer* collar fabric is
cut on straight grain, distinct from a bias-cut *structural* undercollar underneath it — was
tested and refuted (not established either way). So we don't have a confirmed answer for whether
the visible top-collar pattern should show bias-45° or something else; our own measurement
(~85-90°) is the best available number and is at least *consistent* with "cut very differently
from the body," which the bias convention would produce.

**Mechanism:** treat as its own tiny panel, fixed rotation ~85-90° (i.e. can be implemented
identically to the lapel's rotation, just with a much larger angle — near-perpendicular).

### Back — deferred, no asset
No back-view render with a directional pattern exists to measure (the photographic still and
every CAD layer captured are front-view only). Assume the torso's normal-driven mechanism applies
unchanged (backs are broad, gently-curved panels much like the front torso) until a back-view
striped render exists to check. **R1 gives a strong seam rule for this panel regardless of angle**
— see below.

### Pockets / welts — inherit the panel grain, no independent rotation
**Measurement:** noise (tiny samples, sd 34-57° on both the photo and CAD layers) — not usable as
a target.

**Why (R1) — genuinely disputed, not settled:** whether a pocket jett/flap should be cut on the
body's grain (preserving pattern continuity — Anderson & Sheppard's approach) or cross-grain for
structural strength (Bob Bigg, working with Whitcomb & Shaftesbury, calls matching-to-body "bad
tailoring" because a cross-grain jett is stronger) is a **named, real disagreement between bespoke
houses**, not an unsettled-because-under-researched question. There is no single right answer to
converge on.

**Recommendation:** default to inheriting whichever panel's grain the pocket sits on (simplest,
matches one legitimate school of thought, and the alternative requires picking an arbitrary cross
angle with no measured target to justify it). Don't build a separate pocket mechanism.

---

## Seam behaviour (R1, the best-grounded part of this research pass)

- **Center-back seam — MATCH, but not by mirroring the two halves.** 3-0 vote, corroborated by
  Westwood Hart and Threads Magazine (a Savile Row tailor "begins plaid matching at a garment's
  center back, because the plaids must match the collar"). The two back panels are positioned so
  the pattern runs **continuously up into the collar** — meaning the panels sit exactly one
  stripe/check-repeat apart at the top where they meet the collar, and that gap **widens and
  narrows down the back following body shape**. This is a genuinely different rule than "mirror
  the two halves around center back" or "no phase break at all" — implement as: phase-align each
  back-panel half so their pattern is continuous *through the collar point*, not symmetric to each
  other at the seam's own midline.
- **Sleeve-to-body seam — match at exactly ONE prominent horizontal line, at the chest/armhole
  junction; nowhere else.** 2-1 vote, corroborated by two independent sources, one of which
  (Westwood Hart) calls this single-line match "non-negotiable in quality construction" while
  explicitly noting full-sleeve continuous matching is structurally impossible (sleeve pitch,
  elbow shaping, armhole insertion). A more specific claim — that matching happens only at the
  *front* of the armhole, not the back — was tested and refuted, so don't over-specify the
  location beyond "the chest/armhole junction, one line." Implement as a single phase-anchor point
  at that height, free elsewhere (matches the sleeve's already-small, mostly-cosmetic angle
  difference from the body).
- **Front opening (lapel/body button-line) — the code already applies a break (`SEAM_PHASE`), and
  R1 didn't produce a confirmed rule to confirm or contradict it.** A specific forum claim that
  collar-to-lapel matching is "unnatural" and relaxes with wear, and a competing claim that
  mismatch there is "normal, not a flaw," were both tested and refuted — genuinely unresolved.
  Leave `SEAM_PHASE` as-is; this isn't a place to spend more research budget.
- **Pocket flap/jett — no fixed rule (see above), it's a real style choice.** Don't force a match
  or a deliberate break; inheriting the panel grain (no independent rotation) sidesteps the
  question rather than resolving it, which is fine given it's disputed even among bespoke houses.
- **Checks/windowpane (2D pattern) — same seam priorities as stripes, plus a stricter 2D bar at
  matched points.** 2-1 vote: checks require matching in BOTH vertical and horizontal directions
  simultaneously at a matched seam (a strictly higher bar than a stripe's single axis) — no
  source gives checks a *different* seam-by-seam priority order, just a harder standard at the
  seams that do get matched. Practically: wherever this spec says "phase-match" for a stripe
  (collar-continuity at center back, one-line match at the sleeve), a check pattern needs its full
  4-way grid-crossing aligned at that same point, not just one axis. Windowpane has no
  windowpane-specific convention beyond this — extrapolate from the general check rule.
- **A structural note, not directly actionable:** R1 found (3-0) that bespoke tailors sometimes
  *restructure the garment itself* to ease pattern matching — cutting without a sidebody/extended
  front dart, or the historical "Westfield back" (many small darts instead of center-back/side
  seams) specifically to minimize how much an overcheck visibly narrows down the back. We use one
  fixed panel geometry across all fabrics — we can't do this. Worth naming as a known,
  deliberate scope limit: our matching will read as good RTW-grade, not bespoke-Westfield-grade,
  and that's an acceptable trade for a live, fabric-independent compositor.

---

## Addendum — check/windowpane, both axes (added same day, follow-up question)

The R2 measurement above is stripe-only (1D pattern). Went back to measure check/windowpane
directly, since a 2D pattern has an independent horizontal component a stripe doesn't.

**Quantitative measurement hit a real technical wall, honestly reported rather than forced.**
A stripe has one dominant direction, so the structure-tensor approach works directly. A check has
TWO line sets, so I tried a gradient-angle histogram (find two peaks instead of one dominant
angle) on live-pulled isolated `lapel`/`model` layers for two check fabrics (`S486.367-2`,
`S2390-4496`) and one houndstooth (`SNICHOLSON-2791`). First pass produced a suspiciously
identical "31° separation" on every single panel and fabric — caught by printing the raw
histogram and looking (same rule as everywhere else this session): it was an artifact of the
peak-finder's exclusion-zone threshold, not real cloth structure. Fixed the peak-finder, then hit
a second, more fundamental problem: checks/windowpane have thin, SPARSE grid lines with a fine,
DENSE woven micro-texture underneath (visible at native 3280×4100 resolution). The natural fix —
blur to isolate the coarse grid from the fine texture, the same split `prep_fabrics.py`'s
`tame_pattern()` already uses — doesn't work here, because a thin sparse line is destroyed by
blur *faster* than a dense repeating texture is (blur spreads a thin line's limited contrast over
a wider area, crashing its peak intensity, while a dense texture's average local contrast survives
longer). This is the opposite of the stripe case and needs a different tool (a sparse line/ridge
detector, not a scale-split blur) to get a clean quantitative number — not done this session.

**What DID work, and it's a strong, decisive finding: a straightforward visual comparison.**
Brightened, isolated crops of the `S2390-4496` (dark blue check) `lapel` and `model` layers at
native resolution show:
- **Torso**: the grid's vertical lines run dead-parallel to the torso's own vertical axis and the
  horizontal lines run screen-horizontal — a clean, unrotated, orthogonal grid. Matches the stripe
  torso finding exactly (no tilt, already-solved panel).
- **Lapel**: **both grid axes are visibly rotated together, by the same amount, staying
  perpendicular to each other** — not one axis tilting while the other stays level. The grid
  reads as a single rigid pattern rotated to follow the lapel's own diagonal, the same qualitative
  behavior as the stripe lapel finding, just with two lines instead of one.

**Why this matters for implementation — arguably the most useful result of this whole check:**
the mechanism `plan/PATH_A_GRAIN_SPEC.md` already specifies for the lapel (rotate the *sampling
coordinates* by a fixed angle before reading the tile, per the prototype's
`u=(x·cosθ+y·sinθ)·dens, v=(−x·sinθ+y·cosθ)·dens`) is a **rigid rotation of whatever the tile
contains** — it doesn't know or care whether the tile is a 1D stripe or a 2D check. Rotating the
sampling coordinates by ±11° will rotate both a check's grid axes together automatically, with
zero extra check-specific code. The visual finding above is exactly the behavior that mechanism
already produces by construction. **No separate 2D-pattern mechanism needs to be designed** —
verify this prediction once Path A is implemented (render a check on the lapel, confirm both axes
rotate together at the same ±11°), but don't expect to need new code for it.

## Addendum 2 — cross-checking against real (non-Suitsupply) suit photography

Every number above came from one source family: Suitsupply (one photo + their CDN layers). The
user asked the obvious next question — what do ordinary real suit photos show? Pulled two
independent, freely-viewable examples from Permanent Style (menswear editorial with real bespoke
photography, unrelated to Suitsupply): a checked jacket from Whitcomb & Shaftesbury (the same
`matching-checks-on-a-jacket` article R1 already cited for text) and a chalk-stripe DB from
Ciardi. **Verdict: the qualitative mechanism holds up; the magnitude does not — real examples run
higher than the single Suitsupply photo suggested, and single-source measurement understates the
true spread.**

**Lapel (checked jacket, Whitcomb & Shaftesbury):** visually, the check's grid tilts
substantially on the lapel — by eye, tracing a clear grid line, more like **15-30°** from
vertical, not the ~11° the single Suitsupply photo gave. The torso/chest region in the same photo
stays essentially untilted (0°, both grid axes screen-vertical/horizontal), matching every prior
torso finding exactly. Automated measurement was **not** attempted here beyond a sanity check —
a structure-tensor run on the chest region returned +27.7° despite the region visibly reading as
~0° by eye, reconfirming (on real photography, not just synthetic layers) that single-dominant-
angle tools don't work on 2D check patterns. The visual read is what's trustworthy.

**Sleeve (chalk-stripe DB, Ciardi):** attempted the reliable structure-tensor method (the one that
worked cleanly on Suitsupply's studio photo) and it failed here for a *different*, also-useful-
to-know reason: casual/editorial photography has wool-weave texture, natural lighting, and JPEG
compression noise that a clean studio product shot doesn't. First pass "converged" to a clean
+11-12° — then a diagnostic overlay (the same discipline as every other catch this session)
showed it wasn't measuring the pinstripes at all, it was measuring the **sleeve's own silhouette
edge** against the blurred background, which happens to taper at a similar angle. Re-run with the
box inset away from the edge, and the reading became unstable (spread 54-64°) — the actual
pinstripe signal in this photo is just too weak relative to texture/noise for this method. By eye,
the sleeve stripes read as close to vertical with a modest lean, broadly consistent with a small
angle, but not confidently quantifiable beyond that from this image.

**What this changes:** treat **±11° (lapel) and ±5° (sleeve) as floor estimates from one clean
but narrow source, not as precise targets.** Real garments plausibly run higher, especially on
the lapel — a real check example suggested 15-30°. Recommend implementing Path A with the
existing numbers as a starting point, then **tuning by eye against the actual render** once
built (rotate the lapel sampling angle up from 11° while visually comparing to real reference
photos, the same "settle by eye" method already established for other unresolved metrics in this
codebase) rather than treating 11°/5° as fixed. This also means the earlier resolution of the
L/R asymmetry (recommending a symmetric average) still stands, but the magnitude itself should be
open to revision during implementation, not locked in from this research pass alone.

**Methodological note for any future measurement pass:** automated structure-tensor measurement
is reliable on (a) clean studio product photography shot on a plain background and (b) isolated
CDN component layers with a real alpha channel — both cases this session used successfully. It is
**not** reliable, without much more careful pre-processing, on casual/editorial real-world photos
— texture, lighting, and compression noise all defeat it, and it can silently lock onto a
silhouette edge instead of the pattern (as it did here) unless that's explicitly guarded against.
For that class of image, visual inspection is the correct tool, not a fallback.

## Addendum 3 — does this even matter for delivery? Checked directly with KuteTailor

Separate from render accuracy: does any of this matter if GCC's actual manufacturer doesn't
pattern-match directional fabric in the first place? The whole render exists to set expectations
for a real, paid order that KuteTailor physically cuts and ships (`orders/paid` webhook → backend
→ KuteTailor, per `HANDOVER.md` §1) — accuracy against tailoring convention is pointless if the
delivered garment can't reflect it.

**Checked directly on `platform.kutetailor.com` (logged in as the ARUAP account already used for
the order API).** Found a real, orderable KuteTailor house product in their own "Order By Style"
catalog — `26AWM2P203` (fabric `DBV9300`, a grey glen/windowpane check), a DB jacket + trousers —
with 18 real product photos. **Their own reference photography shows the same pattern-matching
behavior found everywhere else this session**: the lapel's check grid tilts, following the roll;
the chest, torso, and trousers all stay cleanly orthogonal (screen-vertical/horizontal), no tilt.
This is the strongest possible evidence for the original question — it's not a competitor's
marketing photo or a generic tailoring reference, it's KuteTailor's own manufactured sample.
**Their cutters can and do produce this.**

Two caveats worth carrying forward, not blocking:
- **The order platform's preview is a fixed hero photo per style, not dynamic per fabric.**
  Switching the fabric swatch on that same product page (tested: swapped to a purplish-red check,
  `DBV9302`) did not regenerate the image — it stayed the original `DBV9300` sample. So this
  proves the *capability* exists, not that it's guaranteed for every arbitrary custom fabric a
  GCC customer might pick.
- **No pattern-matching option exists anywhere in the customer-facing craft/style catalog**
  (Canvas, Chest pocket, etc. — same categories already reviewed via the API earlier this
  session). This is consistent with it being a default cutting practice/skill, not a
  toggleable parameter — which is good news for "will it happen" and bad news for "can we
  confirm it via the API for a specific order" — there's no field to check or set.

**Net: reasonable to proceed treating GCC's render as broadly representative of what KuteTailor
will deliver**, given direct evidence their factory does this on their own house designs. If a
harder guarantee is ever needed for a specific customer order (e.g. a bold, expensive directional
fabric where a mismatch would be a real complaint), that's a conversation with the KuteTailor
account rep, not something resolvable by browsing their platform further.

## What's still open (explicitly, so it doesn't get lost)

1. **Sleeve mechanism** — verify the existing normal-driven warp against the ±5° target once the
   sleeve has its own panel mask, before writing a new fixed-rotation code path for it.
2. **Back panel** — no directional-pattern render exists yet to confirm the "same as torso"
   assumption; low-risk (backs are broad/gentle like the torso) but unverified.
3. **Windowpane/check — mechanism now confirmed (see addendum below), exact numbers still not.**
   Visual comparison confirms the lapel rotates a check's grid as one rigid unit (both axes
   together, same qualitative behavior as a stripe) — so the *mechanism* question is resolved:
   reuse the stripe rotation as-is, no separate 2D code path needed. What's still open is a hard
   quantitative angle for the check case specifically (the gradient-histogram approach used for
   stripes doesn't transfer cleanly — see addendum for why) and the seam-matching behavior at the
   lapel/sleeve specifically for 2D patterns (R1's sources only documented the pocket in detail
   for checks). Low priority given the mechanism finding — the stripe numbers are the best
   available target until proven otherwise.
4. **Collar's exact mechanism** — 85-90° is our own measurement, consistent with (but not proven
   identical to) the documented 45° bias-cut convention. Fine as an implementation target; not
   fine to cite elsewhere as "the bias-cut angle is 85-90°."

## Implementation sequencing (unchanged from the approved plan, now unblocked)
1. Extend `buildPanels` from the current binary left/right-of-button split to the prototype's
   richer segmentation (torso-L/R, lapel-L/R, sleeve-L/R, collar), refined against these targets.
2. Add a fixed-rotation code path in `buildWarpNormal`/`warpedCloth` for the lapel (±11°) and
   collar (~85-90°) panels — reuse the disabled `SIL_WRAP` machinery's *shape* (per-panel, applied
   in `warpedCloth`'s sampling step) but as a rigid rotation, not a width-taper term.
3. Verify the sleeve against the existing mechanism before adding anything new there.
4. Implement the center-back collar-continuity phase rule and the sleeve one-line chest/armhole
   phase anchor as the seam behavior (generalizing the existing single `SEAM_PHASE` constant,
   which only covers the front opening today).
5. Roll across all 15 cut-views; verify against `audit/pattern_map.py`/`panel_angles.py` at
   matched px/cm, plus the standing 6× visual check. Torso must not regress.
