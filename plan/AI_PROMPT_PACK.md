# AI prompt pack — generating the missing configurator views

_21 July 2026. For Gemini 3 Pro Image (reference-edit), the pipeline already in use._

---

## The one constraint that matters

Our compositor derives the drape map, normal map and garment mask **from the base render itself**. So
every generated view is **self-contained** — it does not need to register pixel-for-pixel against any
other view. That is why this approach can work for us and could not work for Suitsupply, who composite
registered layers.

What we *do* need is **framing consistency**, because `PX_PER_CM` is computed from the figure's height
in the frame. If a new render puts the figure at a different scale, cloth on that view renders at the
wrong size.

> **Reference measurement: the figure occupies 0.898 of the frame height — head to sole, excluding
> the soft floor shadow — in a 1792×2400 (3:4) frame.** Every generated view must match that.
>
> _Measure it the same way: threshold the render against the white sweep at a firm level. A soft
> threshold catches the floor shadow and reports 0.951, which is wrong and would scale cloth on the
> new view by about 6%._

---

## How to run these

1. Start a **new chat** (not a continuation — old context drifts the model).
2. Attach `renders/front_2button_notch.png` as the reference.
3. Paste one prompt below, unchanged.
4. If the result drifts, **do not iterate in the same thread** — start fresh and adjust the prompt.

**Generate all variants of a group in one session from the same reference.** Variants from a single
session share more of the model's identity; variants generated days apart visibly differ, and the
customer sees that as the model "jumping" when they change an option.

---

## A — Back view  ⭐ do this first

Highest value: it unlocks the disabled **Back** toggle and makes **vents** visible (a 3-choice option
that currently changes nothing on screen).

```
Using the attached photograph as an exact reference, generate the SAME man photographed from
directly BEHIND.

MUST MATCH THE REFERENCE EXACTLY — do not reinterpret any of this:
- The same man: same build, same height, same hair colour and cut.
- The same pose: standing upright and square, weight even, feet together and flat on the floor,
  arms hanging straight down at his sides, hands relaxed and open.
- The same camera: full length, straight on, lens at chest height, long lens with no perspective
  distortion or converging verticals. Portrait frame, 3:4 aspect ratio.
- The same framing and scale: the top of his head sits just below the top edge, his shoes sit just
  above the bottom edge, and he fills 95% of the frame height. Centred horizontally.
- The same lighting: soft, even, frontal studio light, no hard shadows on the garment, a soft
  contact shadow on the floor directly beneath his shoes.
- The same background: a seamless near-white studio sweep, flat and even, no vignette, no gradient.
- The same clothing: identical navy two-piece suit, identical fit and trouser break, white shirt
  with an open collar and no tie, dark brown leather derby shoes.

WHAT CHANGES — we are now looking at the back of the suit:
- The jacket's back collar sitting cleanly against the shirt collar, with a narrow sliver of white
  shirt collar visible above it.
- The centre back seam running from collar to hem.
- Natural shaping over the shoulder blades, the backs of both sleeves, and the sleeve heads.
- Two side vents at the hem, hanging closed and straight.
- The back of the trousers with a clean seat and a single centre seam.

Photographic, sharp, high detail, evenly lit. No text, no watermark, no logos, no props,
no additional people.
```

## B — Side view

```
[Same reference. Same MUST MATCH block as prompt A, verbatim.]

WHAT CHANGES — the man is rotated exactly 90 degrees to his left so we see his RIGHT side in
true profile:
- The side seam of the jacket running vertically, the sleeve hanging naturally along his side.
- The lapel visible edge-on at the chest, the jacket front edge and the hem.
- One side vent visible at the hem.
- The trouser side seam straight from hip to hem, with the same break over the shoe.
- His arm hangs at his side and does not obscure the jacket's side seam.

Photographic, sharp, high detail, evenly lit. No text, no watermark, no logos, no props.
```

## C — Lapel variants

These three currently fall back to the nearest rendered shape, which is why the UI has to print
_"Preview shows the nearest rendered lapel."_ Generating them removes that sentence.

Use the **MUST MATCH** block from prompt A, then swap in one of these. Widths are specified because
Suitsupply specify theirs (8.6 / 9.8 / 10.8 cm) and vague lapel prompts drift wildly.

```
WHAT CHANGES — only the lapel. Everything else in the photograph is identical.
Replace the notch lapel with a SHAWL lapel: one continuous unbroken curve of cloth running from
the back of the collar down both sides to the closure, with no notch and no peak, no step or
break in the outline. Smooth, even width of about 9 cm at the chest. The jacket remains a
two-button single-breasted jacket and the button stance is unchanged.
```

```
WHAT CHANGES — only the lapel. Everything else in the photograph is identical.
Replace the notch lapel with a SEMI-NOTCH lapel: a notch lapel whose notch opening is narrower and
set at a shallower angle than standard, giving a softer, less pronounced step. Lapel width about
9 cm at the chest. Two-button single-breasted, button stance unchanged.
```

```
WHAT CHANGES — only the lapel. Everything else in the photograph is identical.
Replace the notch lapel with a SEMI-PEAK lapel: the lower lapel edge angles gently upward into a
soft, shallow peak rather than a sharp one — less angular than a full peak lapel but clearly
pointing upward, not notched. Lapel width about 9.5 cm at the chest. Two-button single-breasted,
button stance unchanged.
```

## D — Pocket variants

Currently **all four lower-pocket choices and all three chest-pocket choices render identically.**
These are the cheapest wins after the back view, because the change is small and local, so the model
has less room to drift.

```
WHAT CHANGES — only the lower pockets. Everything else in the photograph is identical.
Replace the flap pockets with PATCH pockets: two pockets applied to the outside of the jacket as
visible panels of the same navy cloth, with stitched edges, softly rounded bottom corners, and no
flap. Same position and same size as the existing pockets.
```

```
WHAT CHANGES — only the lower pockets. Everything else in the photograph is identical.
Replace the flap pockets with BESOM (jetted) pockets: a clean horizontal welt opening with narrow
cloth lips above and below, no flap at all, sitting flush with the jacket front. Same position
and same width as the existing pockets.
```

```
WHAT CHANGES — only the lower pockets. Everything else in the photograph is identical.
Replace the straight flap pockets with SLANTED (hacking) flap pockets: the same flap pockets but
angled, sitting lower at the front edge and higher toward the side seam, at roughly 15 degrees
from horizontal.
```

## E — Vent variants (requires the back view from A first)

Attach the **generated back view** as the reference, not the front.

```
WHAT CHANGES — only the vents at the jacket hem. Everything else is identical.
[ Option 1 ] A single CENTRE VENT: one vertical opening on the centre back seam, running about
             22 cm up from the hem, hanging closed and straight.
[ Option 2 ] NO VENT: a completely closed, uninterrupted hem with no opening at all.
```

---

## Wiring a generated view into the configurator

**Generation is step 1 of 5, and Marigold is step 4 — not step 2.** A render on its own is unusable;
the compositor needs a garment mask and a drape map first. Both of those had **no script** until
21 July 2026 (the original generator was never saved) — they have now been reverse-engineered from
the existing maps and validated, so the whole chain is reproducible.

```bash
cd ~/Desktop/GCC_House_Model

# 1. GENERATE  — Gemini, prompts above. Save to renders/<cut>.png
#    Then check the framing before spending any compute on it:
python3 - <<'EOF'
import numpy as np; from PIL import Image
a=np.array(Image.open('renders/<cut>.png').convert('RGB')).astype(int)
m=(255-a).sum(-1)>150; r=np.where(m.sum(1)>3)[0]
print('figure fraction', round((r[-1]-r[0])/a.shape[0],3), '  target 0.898')
EOF

# 2. MASK      — which pixels are suit  (validated: mean IoU 0.962 vs the originals)
python3 builder/make_mask.py renders/<cut>.png /tmp/<cut>_mask.png

# 3. DRAPE     — L = luminance renormalised to median 128 inside the mask
python3 builder/make_drape.py renders/<cut>.png /tmp/<cut>_mask.png drape_maps/<cut>_drape.png

# 4. NORMALS   — Marigold. SLOW (~2 min/render on the M1). Batch every new render in one
#    off-hours run with Chrome quit; add the cut names to CUTS inside the script first.
~/gcc_normals_venv/bin/python gen_normals_all.py

# 5. REGISTER + BUILD
#    edit builder/build_configurator_v0.py -> CUTS list, and CUTMAP so options resolve to it
python3 builder/build_configurator_v0.py
python3 audit/calib.py <prefix>_ audit/<dir>      # expect ~100-110% of the cloth's luminance
```

**Do steps 1–3 for all eight renders first, then run Marigold once over the batch.** Marigold is the
only slow step and it wants the machine to itself; everything else is seconds.

### Known limitation of the auto-mask

It catches a few hundred pixels of the dark **shoes** (it keys on "dark and neutral-to-bluish", and
brown leather in shadow qualifies). Harmless at the current scale but it does put a speck of cloth on
the shoe. If it shows, add a rule excluding the bottom few percent of the figure, or paint it out
once. Precision is otherwise 0.99+, and the mask is deliberately tuned to the **navy house suit** —
it works because every base render shows the same garment, with fabric composited later.

> ### ⚠ Do not "fix" FIGURE_FRAC on its own
>
> The builder uses `FIGURE_FRAC 0.93` and `FIGURE_CM 183`, but the reference render actually measures
> **0.898**. It is tempting to correct the constant. Don't — not in isolation.
>
> Only their **product** matters: `PX_PER_CM = FIGURE_FRAC × H_FULL / FIGURE_CM`, currently **8.85**.
> That value is empirically validated — rendered pattern pitch measured **0.99×** against the mill
> scan. Changing `FIGURE_FRAC` to 0.898 alone shifts cloth scale by 3.6% and breaks a result we
> verified. (Taken together, 0.898 and 8.85 imply the model reads as ~177 cm rather than 183 — so
> it is `FIGURE_CM` that is the soft number, not the ratio.)
>
> The safe change is to have the builder **measure each render's figure height and solve for the
> per-cut constant that preserves PX_PER_CM = 8.85**, then re-run `audit/period.py` to confirm
> pattern pitch held. Otherwise every new view inherits a silent scale error.

---

## Honest limits of this route

- **Identity drift.** Every generation re-imagines the model slightly. Within one session it is
  small; across sessions it is visible. Generate a group in one sitting.
- **It does not scale to per-fabric.** These prompts produce *geometry* variants on the house
  model, which our compositor then dresses in any of the 117 cloths. Do **not** try to generate
  per-fabric images this way — the cloth would no longer be measured, and colour fidelity is the
  thing we just spent this project getting right.
- **No true option independence.** A generated "patch pocket" render is a whole new image, so
  patch-pockets-with-a-shawl-lapel needs its own generation. Combinations multiply where
  Suitsupply's layers would add. Fine for the handful of combinations that matter; not a path to
  full coverage.
- **This is a bridge, not the destination.** It closes the visible gaps cheaply. The CAD route in
  `STUDIO_BRIEF.md` is what removes the ceiling.
