# The Model Bible — full regeneration of the house model

**Gage Court configurator · 21 July 2026 · supersedes the existing `renders/`**

This is the canonical spec. Everything the configurator shows derives from these renders, so
they get generated once, properly, against a written standard — not patched.

---

## Why regenerate rather than patch

Five things are now known that were not known when the current renders were made:

1. **Shoes are black**, not brown.
2. **Three views are needed** — front, side, back. We only ever generated front.
3. **The framing constant is measurable and load-bearing**: the figure must be **0.898** of frame
   height. `PX_PER_CM` derives from it, so a 2% framing drift is a 2% cloth-scale error.
4. **The base suit must be mid-grey, neutral and unclipped** — it is not decoration, it *becomes*
   the drape map. The current renders happen to get this right (saturation 0.046, p1–p99 = 111
   levels, 0.004% crushed); the new ones must too, and now it is checked rather than lucky.
5. **The model must be one locked identity** across every render. Generating each independently
   produces subtly different men, which reads as the model "jumping" between options.

---

## The 15 base renders

Five cuts × three views. Names must match exactly — the builder resolves by filename.

| # | Cut | Front | Side | Back |
|---|---|---|---|---|
| 1 | 2-button, notch lapel ⭐ **HERO** | `front_2button_notch` | `side_2button_notch` | `back_2button_notch` |
| 2 | 2-button, peak lapel | `front_2button_peak` | `side_2button_peak` | `back_2button_peak` |
| 3 | 1-button, peak lapel | `front_1button_peak` | `side_1button_peak` | `back_1button_peak` |
| 4 | Double-breasted 6×2, peak | `front_doublebreasted` | `side_doublebreasted` | `back_doublebreasted` |
| 5 | 3-piece, notch + waistcoat | `front_3piece_vest` | `side_3piece_vest` | `back_3piece_vest` |

Save to `~/Desktop/GCC_House_Model/renders/` as PNG.

---

## Generation order — this matters more than the prompts

**Do not generate 15 images independently.** Identity drift will make them unusable together.

```
STEP 0   Generate the HERO  (front_2button_notch) from the text prompt below.
         Iterate until it is genuinely right. Everything inherits from it —
         a flaw here is a flaw in all 15. Do not proceed until it passes.

STEP 1   Attach the approved HERO as reference. Generate the other 4 FRONT views.
         Same session, one after another.

STEP 2   Attach each approved FRONT. Generate its SIDE and BACK.
         Same session per cut.
```

Reference-editing from one approved hero is the only way to hold identity. Starting a fresh chat
mid-way re-rolls the model.

---

## Acceptance — run before doing anything else with a render

```bash
python3 builder/check_render.py renders/<name>.png
```

Ten automated checks: resolution, 3:4 aspect, figure height 0.898 ±0.02, horizontal centring,
sweep cleanliness and flatness, garment neutrality, garment tonal range, black-crush, and that the
shoes read black rather than brown. **If it fails, regenerate — do not proceed.** Every check
corresponds to something that silently corrupts the compositor later.

---

## THE LOCK BLOCK

Paste this **first**, then the render-specific block. It never changes.

```
LOCKED — identical in every image, never reinterpret:

MODEL
- The same man throughout: mid-30s, athletic-slim build, approximately 183 cm tall.
- Short dark-brown hair, neatly cut, combed to one side, same hairline.
- Clean-shaven. Same face, neutral expression, calm, looking straight ahead.
- Fair-to-medium skin tone. Hands relaxed and slightly open, thumbs forward.

POSE
- Standing upright and square, weight even on both feet.
- Feet together, flat on the floor, toes pointing forward.
- Arms hanging straight down at his sides, not touching the jacket.
- Shoulders level and relaxed.

GARMENT — this is a fit and drape reference, not a colour reference
- A plain MID-GREY suit, matte wool, no pattern, no sheen, completely neutral grey
  with no blue, brown or green cast.
- Evenly lit so the cloth holds detail everywhere: no crushed black shadows in the
  folds, no blown-out white highlights. Soft, readable shading throughout.
- Modern tailored fit, natural shoulder, clean drape, light break over the shoe.

WARDROBE
- White cotton shirt, point collar, worn open at the neck with NO NECKTIE.
- Shirt cuffs showing approximately 1 cm below the jacket sleeve on both sides.
- White linen pocket square, straight "TV" fold, showing about 1 cm.
- BLACK leather derby shoes, plain toe, matching pair, lightly polished.
- No belt visible, no watch, no jewellery, no glasses, no hat, no bag.

CAMERA AND FRAME
- Full length, straight on, lens at chest height.
- Long lens: no perspective distortion, no converging verticals, no wide-angle stretch.
- Portrait frame, 3:4 aspect ratio, as high resolution as possible.
- The figure fills 90% of the frame height, head to sole, centred horizontally,
  with an even margin of background above the head and below the shoes.

LIGHT AND BACKGROUND
- Soft, even, frontal studio light. No hard shadows on the garment.
- A soft contact shadow on the floor directly beneath the shoes.
- Seamless near-white studio sweep, flat and even, no vignette, no gradient,
  no visible horizon line.

OUTPUT
- Photographic, sharp, high detail. No text, no watermark, no logo, no props,
  no additional people, no reflections, no border.
```

---

## STEP 0 — the hero  ⭐

No reference image. This one defines the man.

```
[LOCK BLOCK]

Generate a full-length studio photograph of this man wearing a single-breasted
TWO-BUTTON suit jacket with a NOTCH lapel of standard width, a welt chest pocket
holding the pocket square, straight flap lower pockets, and matching flat-front
trousers. Front view, facing the camera.
```

Iterate on this one alone until it is right. Then run `check_render.py` and only then move on.

---

## STEP 1 — the other four fronts

Attach the approved hero. One prompt each, same session.

```
[LOCK BLOCK]

Using the attached photograph as an exact reference for the man, his pose, the camera,
the framing, the lighting and the background — change ONLY the jacket:
a single-breasted TWO-BUTTON jacket with a PEAK lapel, the lower lapel edge angling
sharply upward into a defined point. Standard lapel width. Front view.
```

```
[LOCK BLOCK]

Using the attached photograph as an exact reference for the man, his pose, the camera,
the framing, the lighting and the background — change ONLY the jacket:
a single-breasted ONE-BUTTON jacket with a PEAK lapel and a lower, cleaner button
stance. Front view.
```

```
[LOCK BLOCK]

Using the attached photograph as an exact reference for the man, his pose, the camera,
the framing, the lighting and the background — change ONLY the jacket:
a DOUBLE-BREASTED six-button two-to-button jacket with peak lapels, wrapped and
fastened left over right, with the wider overlapping front panel. Front view.
```

```
[LOCK BLOCK]

Using the attached photograph as an exact reference for the man, his pose, the camera,
the framing, the lighting and the background — change ONLY the outfit:
a THREE-PIECE suit. The same two-button notch-lapel jacket, worn open and unbuttoned
so a matching mid-grey WAISTCOAT is clearly visible underneath — five buttons, V neck,
no collar, welt lower pockets, ending just below the waistband. Front view.
```

---

## STEP 2 — side and back

Attach the approved **front of that same cut**. Repeat per cut.

```
[LOCK BLOCK]

Using the attached photograph as an exact reference — the same man, the same suit,
the same camera, framing, lighting and background — rotate him exactly 90 degrees to
his left so we see his RIGHT side in true profile.
Show: the jacket side seam falling vertically, the sleeve hanging naturally along his
side, the lapel seen edge-on, the jacket front edge and hem, one side vent at the hem,
and the trouser side seam running straight from hip to hem with the same break over the
shoe. His arm hangs at his side and does not obscure the side seam.
```

```
[LOCK BLOCK]

Using the attached photograph as an exact reference — the same man, the same suit,
the same camera, framing, lighting and background — show him from directly BEHIND.
Show: the jacket's back collar sitting cleanly against the shirt collar with a narrow
sliver of white shirt collar above it, the centre back seam from collar to hem, natural
shaping over the shoulder blades, the backs of both sleeves, TWO SIDE VENTS at the hem
hanging closed and straight, and the back of the trousers with a clean seat and a single
centre seam.
```

---

## After generation — the pipeline

For each accepted render, in this order. Marigold is **step 4**, not step 2.

```bash
cd ~/Desktop/GCC_House_Model

python3 builder/check_render.py renders/<name>.png                       # 1. accept or reject
python3 builder/make_mask.py  renders/<name>.png /tmp/<name>_mask.png    # 2. garment mask
python3 builder/make_drape.py renders/<name>.png /tmp/<name>_mask.png \
                              drape_maps/<name>_drape.png                # 3. drape map
# 4. add every new name to CUTS inside gen_normals_all.py, then ONE batch run, off-hours:
~/gcc_normals_venv/bin/python gen_normals_all.py
# 5. register in builder/build_configurator_v0.py (CUTS + CUTMAP), then:
python3 builder/build_configurator_v0.py
```

Do steps 1–3 for **every** render first; run Marigold once over the whole batch. It is the only
slow step (~2 min per render) and wants the machine to itself with Chrome quit.

---

## Builder work this unlocks — and requires

- **A view dimension.** `CUTS` currently maps one filename per cut. It needs cut × view, and the
  Front/Back control needs wiring to it (it is styled and disabled today).
- **Per-cut framing.** With 15 renders, `FIGURE_FRAC` as a single global constant becomes a
  liability. Measure each render and solve for the value that preserves `PX_PER_CM = 8.85`.
  Never "correct" `FIGURE_FRAC` alone — see the warning in `AI_PROMPT_PACK.md`.
- **`recolor_shoes.py` is superseded** by generating black shoes directly. Kept only in case any
  existing render is retained.

---

## What comes after the base set

The 87-item option manifest in `RENDER_MANIFEST.md` — lapels, pockets, vents — all generated the
same way, referencing the approved base render for that cut and view. **Do not start those until
all 15 base renders are accepted.** They inherit the model's identity, and the identity is only
as good as the hero.
