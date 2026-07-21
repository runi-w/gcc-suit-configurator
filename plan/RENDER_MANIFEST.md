# Render manifest — every option, and what each one costs

_21 July 2026. Companion to `AI_PROMPT_PACK.md`. Source of truth for what needs generating._

---

## The headline

**126 generations covers every visible option, across all 4 cuts and all 3 views.**

Not 25,000. The difference is architectural: Suitsupply bake cloth into every layer, so their asset
count multiplies by their 347 fabrics. **We composite cloth at runtime from the scans, so our asset
count is fabric-independent** — the same 126 renders serve all 117 cloths, and every cloth we add
later costs nothing.

That is the single biggest advantage we have over their system, and it only exists because the
fabric pipeline is measured and correct.

---

## 1. Cloth geometry — needs a generated render

These change the garment's shape, so the cloth must be re-rendered over them.

| Option | Choices | Visible in | Per cut? | New renders |
|---|---:|---|---|---:|
| **Cut / closure** | 4 | front, side, back | — | 12 _(the base set)_ |
| Lapel | 5 | front, side | yes | 32 |
| Chest pocket | 3 | front | yes | 8 |
| Lower pockets | 4 | front, side | yes | 24 |
| Vents | 3 | back | yes | 8 |
| Ticket pocket | 2 | front | yes | 4 |
| Front hem shape | 2 | front | yes | 4 |
| Shoulder | 3 | front, side, back | yes | 24 |
| Trouser pleats | 2 | front | no | 1 |
| Trouser cuffs / turn-ups | 2 | all | no | 3 |
| Leg opening | 3 | front, side | no | 4 |
| Waistcoat front | 2 | front | no | 1 |
| Waistcoat collar | 2 | front | no | 1 |
| | | | **Total** | **126** |

Counts are _(choices − 1)_ because the default is already in the base set.

**Cut is the only one currently rendered.** Lapel is partly rendered (2 of 5). Everything else below
the first row changes the order and not the picture today.

---

## 2. Hardware — composite as sprites, do NOT generate

| Option | Choices | Why no generation |
|---|---:|---|
| **Buttons** | 8 | Small, fixed positions, fabric-independent. Suitsupply treat these the same way — a `shared/buttons` layer reused across all 347 cloths. Overlay a button image at known coordinates. |
| **Pocket square** | if made an option | Same: a small sprite at a fixed position on the chest. |
| **Necktie** | if made an option | Larger, but still a fixed-position overlay on a closed shirt front. |

Generating 8 button variants × 4 cuts × 3 views would be 96 wasted generations for something a
40×40 px sprite solves. Do the sprite.

---

## 3. Internal — never rendered, make-ticket only

Invisible from outside a closed jacket. These carry KuteTailor codes and belong in the order, but
cost **zero** render effort.

| Option | Choices | Note |
|---|---:|---|
| **Monogram** | 550 combos | ⭐ All five positions are internal — inner pocket, collar felt, name label. 10 threads × 11 fonts × 5 positions and **not one pixel of render cost.** |
| Canvas | fused / half / full | Construction, not silhouette |
| Inner facing, inner pocket | — | Inside the jacket |
| Trouser fly, closure, lining | — | Inside |
| Waistcoat inner lining | — | Inside |

**Lining (12 colours) is the awkward one.** Currently invisible, because our jacket renders closed.
Suitsupply ship a `shared/lining` layer, so they show it somewhere. Options: an open-jacket view, an
interior detail shot, or a flat swatch inset in the rail. **Decision needed — see §5.**

---

## 4. THE LOCK BLOCK — paste into every prompt, unchanged

The model and everything he is wearing that is *not* the option under test must be identical in every
generation. Any drift here shows up as the model "jumping" when a customer changes an option.

```
LOCKED — identical in every image, never reinterpret:

MODEL
- The same man throughout: mid-30s, athletic-slim build, approximately 183 cm.
- Short dark-brown hair, neatly cut and combed to one side, same hairline.
- Clean-shaven. Same face, same neutral expression, looking straight at the camera.
- Fair-to-medium skin tone. Hands relaxed and open, thumbs forward.

POSE
- Standing upright and square to the camera, weight even on both feet.
- Feet together, flat on the floor, toes pointing forward.
- Arms hanging straight down at his sides, not touching the jacket.
- Shoulders level and relaxed.

WARDROBE  (fixed unless the prompt explicitly changes one)
- White cotton shirt, point collar, worn open at the neck with NO NECKTIE.
- Shirt cuffs showing approximately 1 cm below the jacket sleeve on both sides.
- White linen pocket square in the chest pocket, straight "TV" fold, showing about 1 cm.
- Dark brown leather derby shoes, plain toe, matching pair.
- No belt visible, no watch, no jewellery, no glasses, no hat, no bag.

CAMERA AND FRAME
- Full length, straight on, lens at chest height.
- Long lens: no perspective distortion, no converging verticals.
- Portrait frame, 3:4 aspect ratio.
- The figure fills 0.898 of the frame height, head to sole, centred horizontally.

LIGHT AND BACKGROUND
- Soft, even, frontal studio light. No hard shadows on the garment.
- A soft contact shadow on the floor directly beneath the shoes.
- Seamless near-white studio sweep, flat and even, no vignette, no gradient.

OUTPUT
- Photographic, sharp, high detail. No text, no watermark, no logo, no props,
  no additional people, no reflections.
```

---

## 5. Decisions needed before generating

These change the manifest, so settle them first.

| # | Decision | Why it matters |
|---|---|---|
| 1 | **Necktie — fixed absent, or an option?** | Currently absent, and that was a deliberate choice ("natural, tieless"). Suitsupply show a tie. If it becomes an option it is a sprite, not a generation — cheap. But it changes the shirt collar (open vs closed), which **is** a generation. |
| 2 | **Pocket square — fixed, or an option?** | Currently white, present. As an option it is a cheap sprite. As a fixed item it must be in the lock block, which it now is. |
| 3 | **Shirt — always white and open?** | If shirt colour becomes configurable it is a large visible area and would need generations, not sprites. Recommend: keep fixed for v1. |
| 4 | **Shoes — always brown derbies?** | Recommend fixed. They anchor the image and no one is buying shoes here. |
| 5 | **How do we show lining?** | 12 colours currently invisible. Cheapest honest answer: a swatch inset in the rail, labelled — not a fake open-jacket render. |
| 6 | **Which options do we actually expose?** | Shoulder, ticket pocket, front hem, trouser cuffs and leg opening are currently **fixed house standards**, not offered. Exposing them adds 39 of the 126 generations. Leaving them fixed drops the manifest to **87**. |

**If you leave the house-standard options fixed, the manifest is 87 generations.** That is a realistic
first pass.

---

## 6. Sequencing — highest value first

| Phase | What | Generations | Unlocks |
|---|---|---:|---|
| **1** | Back + side views, default config, all 4 cuts | **8** | The disabled Back toggle; makes vents renderable at all |
| **2** | Vents (3) on the back view | 8 | A whole option group that currently does nothing |
| **3** | The 3 missing lapels | 32 | Removes the _"nearest rendered lapel"_ disclaimer |
| **4** | Lower + chest pockets | 32 | The two largest option groups that don't render |
| **5** | Everything else | 46 | Full coverage |

Phase 1 is **eight images** and it is the single most visible improvement available.

---

## 7. The technique that makes this scale

Gemini regenerates the *whole* image, so a "patch pocket" variant is a new render, not a patch.
Left alone, combinations would multiply — patch-pockets-with-a-shawl-lapel would need its own image.

**Harvest the variants into layers instead.** Because every generation shares the lock block —
same pose, same camera, same framing — the changed region is local. So:

1. Generate the variant.
2. Align it to the base render (the fixed frame makes this a small translation at most).
3. Cut out only the changed region with a soft-edged mask.
4. Store it as a layer with alpha.

Now options **add** instead of multiplying, exactly like Suitsupply's stack — but produced from a
generator that only knows how to make whole images. This is worth building once, in the builder,
before generating in bulk.

If alignment proves unreliable for a given option, fall back to whole-image variants for that option
only. Pockets and vents are small and local and should harvest cleanly; lapels are larger and may not.
