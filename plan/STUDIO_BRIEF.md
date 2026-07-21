# Studio brief — single-jacket CAD proof

**Gage Court Clothiers · 3D garment pilot · 21 July 2026**

---

## 1. What we're buying

**One digital jacket, built properly, to prove the pipeline before we commission the rest.**

We are not asking for a finished configurator asset set. We are asking whether a garment built in
CAD, draped, and rendered with our own fabric scans beats what we currently produce by compositing
cloth onto a photographic still. We have an objective test for that (§6), so this is a decision that
can be settled with one garment rather than argued about.

If it passes, the full option set follows (§8).

---

## 2. Background — what already exists

We run a live 2D configurator. Fabric rendering is measured and good: pattern renders at true
physical scale (0.99× against the mill scan) and the garment sits at 105% of the cloth's linear
luminance, which matches Suitsupply on the same measurement.

What we cannot do is change the garment's *shape*. Our base images are stills, so pockets, vents and
most lapel shapes do not change the picture. That is the gap this pilot addresses.

**You are not being asked to solve fabric rendering.** We supply the cloth data and we will judge
the result against our own measurements.

---

## 3. Scope of the pilot

| | |
|---|---|
| Garment | Men's single-breasted **two-button jacket**, notch lapel, flap pockets, side vents |
| Size | One size, EU 50 / US 40R, on a standard avatar |
| Avatar | Male, **183 cm**, athletic-slim build, standing square, arms at sides, feet together |
| Views | **Front only** for the pilot (side and back are in the full scope, §8) |
| Cloth | Three we will supply (§5) |

Trousers and waistcoat are **out of scope** for the pilot.

---

## 4. Technical delivery spec

This spec exists so the output drops into our compositor without rework. Please flag anything here
that is awkward before starting rather than substituting.

**Camera**
- Straight on, lens at chest height, **long lens — no perspective distortion, no converging verticals**
- Portrait **3:4** frame
- Figure occupies **95%** of frame height, centred horizontally
- **Camera locked and identical across every render.** This is the single most important requirement:
  we composite these, and a camera that moves between variants breaks everything downstream.

**Output**
- **3280 × 4100 px, RGBA PNG**, straight (un-premultiplied) alpha
- Garment isolated on **transparent background** — no sweep baked in, no floor shadow baked into the
  garment layer
- Floor contact shadow delivered as a **separate layer**
- At this size the cloth resolves at ~20 px/cm, comparable to Suitsupply's ~21

**Per-component passes** — each rendered in isolation on the locked camera, with alpha:
1. Jacket body (no lapel, no pockets)
2. Lapel
3. Chest pocket
4. Lower pockets
5. Topstitching / AMF
6. Buttons *(separate — these are fabric-independent and get reused across all cloths)*

**Colour management**
- Render and deliver in **sRGB**, no LUTs, no filmic or ACES tone-mapping, no grade
- Neutral, even, soft frontal studio lighting — the reference look is a pressed garment on a
  seamless white sweep, not a dramatic key light
- **Do not stylise.** We measure these against physical cloth; a "nice grade" is a defect here

---

## 5. What we supply

- **117 fabric scans at 300 DPI**, each exactly 10.0 × 7.0 cm of real cloth (118.11 px/cm).
  Vignetting ≤2%, zero blown highlights, verified neutral — a black cloth measures a* +0.1, b* +0.1,
  so the colour is trustworthy as shot and needs no correction.
- **Per-fabric micro-normal maps**, derived from each scan's weave.
- **Measured per-fabric parameters**: mean linear luminance, sheen and relief values.
- Three cloths for the pilot: **DBU080A** (grey chalk stripe, 1.44 cm pitch), **DBV196A** (silver
  glen check — our busiest pattern, the hardest case), and **DBS131A** (navy herringbone, a solid).

Tiling must preserve true physical scale. Pattern pitch on the finished garment is something we
measure, not eyeball.

---

## 6. Acceptance test

We will measure your renders with the same harness we used to audit Suitsupply. Please treat these
as pass/fail, not aspirations:

| Measure | Target | Why |
|---|---|---|
| Pattern pitch vs mill scan | **within ±3%** | Our current pipeline achieves 0.99×. Cloth must not be scaled to look nice. |
| Garment median linear luminance vs cloth | **95 – 110%** | Suitsupply measure 105%. A customer compares the screen to a physical swatch in our showroom. |
| Colour cast vs scan | **\|Δb*\| < 1.5** | Navies losing their blue is the failure mode we just eliminated. |
| Camera drift across component passes | **0 px** | Non-negotiable; the layers are composited. |
| Alpha edges | clean, un-premultiplied, no white fringe | White fringing destroys compositing against our cream stage. |

We will also compare side by side against our current render of the same cloth. **The pilot passes
if it is visibly better; it fails if it is merely different.**

---

## 7. Deliverables

1. The rendered passes described in §4, for all three cloths.
2. The **source garment file** (CLO3D / Browzwear / Marvelous native) and the avatar, so the option
   set can be extended without rebuilding from zero.
3. The material setup for one cloth, documented well enough that we can apply the remaining 114
   ourselves.
4. A short note on how long one additional cloth takes to render, and on what hardware.

Point 2 matters. We are buying an asset we can build on, not a folder of pictures.

---

## 8. Full scope, if the pilot passes

For quoting purposes — **do not build this yet.**

- **Cuts**: 2-button, 1-button, double-breasted, 3-piece (4 body variants)
- **Lapels**: notch, peak, shawl, semi-notch, semi-peak (5)
- **Chest pockets**: welt, patch, besom (3)
- **Lower pockets**: flap, besom, patch, slanted (4)
- **Vents**: side, centre, none (3, back view)
- **Views**: front, side, back (3)
- **Garments**: jacket, trousers, waistcoat
- **Cloths**: 117, rising

By our arithmetic that is roughly **25,000 layer renders** for full coverage across the cloth book.
Render compute is not the concern — that is $600–$2,500 of GPU time and about 29 GB of storage.
**The cost we are trying to understand is the garment and option modelling**, which is your quote,
and it is the reason we are running a pilot first.

We would also expect to **render lazily** in production — generating a cloth's layer set on first
request and caching it — rather than pre-rendering all 117 up front.

---

## 9. Questions we'd like answered in your response

1. Roughly how long for the pilot, and what does it cost?
2. Can you hit the camera-lock and per-component-pass requirements in §4, or does your pipeline
   want a different structure? (We are flexible on structure, not on camera lock.)
3. For the full scope, does option geometry cost roughly linearly per option, or is there a large
   fixed cost in the base block that later options amortise against?
4. Would you use our fabric scans directly, or do you want a different capture (e.g. 600 DPI, or
   a Browzwear/Substance digital-fabric format we could request from the mill)?

---

**Contact:** Runi Willner · runi@gcclothiers.com · Gage Court Clothiers, Pikesville MD & Central Jersey
