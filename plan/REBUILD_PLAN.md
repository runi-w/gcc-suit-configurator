# Rebuild plan — regenerate the base renders

Written 2026-07-23. Decides, on evidence, whether the ceiling on this configurator is set by the
**source renders** rather than by the compositor.

---

## 0. What this is actually testing

The compositor is not in question. 32 audit findings this session produced **zero** that said the
architecture is wrong, and the expensive properties are measured at or near reference parity:
colour 98% of the mill scan, pattern scale 0.99× true, no moiré, specular 3.08 vs 3.30, crease
depth better than the reference, band-limiting ~0.89 against 0.96. Those took sessions to reach
and a rewrite resets them to zero.

What IS in question is the **input**. Six findings sit in the base renders, and they are the ones
without cheap fixes:

- the generator invented a key light and never drew the screen-right lapel gorge — in **10 of 10**
  front generations ever made, including the five superseded ones. It is retouched by code today.
- the shirt carries a 4,867 px blue-channel plateau.
- the mask has to *infer* where the garment ends from a render it did not author, which is the
  shared root of the shoe cut, the shoulder band and the button question.

So the question this plan answers is narrow and answerable: **can a different generator, given
everything we now know, produce a base render that is measurably better on the axes we care
about?** Not "is the project right" — just "is the ceiling higher".

**Cost of finding out: one image.**

---

## 1. Stage 1 — one test image (you generate)

**Prompt:** `plan/PROMPT_03_hero.txt`. Front view, 2-button notch, the default cut.

**Generator:** Fable, run by you. Nothing is sent to any API by me.

Hard requirements — the pipeline cannot use the image otherwise:

| | |
|---|---|
| Aspect | 3:4 portrait |
| Resolution | ≥1600 px wide (current renders are 1874×2499) |
| Figure | full length, head to sole, straight on |
| Pose | upright, square, arms at sides, **not** touching the jacket |
| Cloth | plain mid-grey, matte, neutral — no blue/brown/green cast |
| Shoes | black, not brown |
| Background | seamless near-white sweep, flat |

**Do not fight the generator over framing or background level.** `normalize_render.py` keys the
sweep to neutral and pads the canvas so the figure lands at exactly 0.898 of frame height. Asking
for it once is enough; the arithmetic does the rest. This is why the prompt spends its budget on
construction and light instead.

---

## 2. The acceptance gate

Run: `OUT=/tmp python3 builder/check_rebuild.py <candidate.png>`

It scores the candidate against the **pristine, pre-retouch** hero (`*.orig.png`) so we compare
like with like — not against an image we already fixed by hand.

| Axis | Current baseline | Want |
|---|---|---|
| Garment px carrying construction detail | 17.3% | **higher** — this is the layer the compositor re-applies |
| Band-pass std | 11.67 levels | higher |
| Frame px at 255 | 0.011% | < 0.05% |
| Shirt median | 242 | ≤ 245 (reference sits ~242) |
| Shirt texture std | 5.90 | > 3 — flat means paper cutout |
| Garment p1 | 26 | > 8 — crushed folds are dead drape |
| Right minus left luminance | +17.7 | \|x\| < 30 |

**On that last row — asymmetry is not a defect.** Suitsupply's own production layers measure
−14.1 (their AI hero), +23.4 and +12.0 (their flat CAD layers). A key-plus-fill setup produces
exactly this, and a perfectly flat figure would look lifeless. We corrected for it earlier in the
session on the assumption it was an invented key light; that assumption was wrong. Do not select
a candidate for being symmetric.

**The gorge is judged BY EYE and only by eye.** The tool crops both gorges at 4× and stacks
candidate over baseline. Three metrics were tried against a known-broken render and its retouched
twin: edge energy read 0.89–1.00 on both, connected-component read 0.99 on the broken one and 0.61
on the fixed one — **backwards** — and a shared threshold gave no signal at all. A check that
reports PASS on a render with no right gorge is worse than no check. Look at the sheet.

### Verdict rule, fixed in advance so we can't move the goalposts

- **Both gorges clean, and ≥5 of 7 numeric axes at or better than baseline** → the ceiling is
  higher. Proceed to Stage 3.
- **Gorges still broken** → the ceiling is real and generator-independent. Stop; keep the current
  renders and the `fix_gorge.py` retouch, and spend the effort on the compositor instead.
- **Mixed** → generate 2–3 more from the same prompt before deciding. The defect was 10/10 with
  the old prompt, so a single clean result is meaningful but not conclusive.

---

## 3. Stage 2 — the identity problem (read before generating ten)

Whatever man Fable produces **will not be the man in the current renders**, and all ten cut-views
must be the same person or the cut selector swaps the model mid-session — which the user already
rejected once, when the baked-still experiment did exactly that.

The current set was made by generating the hero fresh and then producing the other cuts as
image-to-image *edits* of it ("keep the exact man, pose, grey and background; change ONLY the
jacket to X"). That gave excellent identity consistency — and it is also precisely the mode in
which this generator ignores instructions: asked for background 246 it gave 229, asked for figure
0.88 it gave 0.936. The gorge defect propagated through every one of those edits.

So the sequencing matters:

1. Generate and **accept the hero first**, on its own, with no reference image attached, so the
   prompt is obeyed as fully as it ever will be.
2. Derive the other nine as edits from the accepted hero.
3. **Run the gorge check on every front, not just the hero.** The retouch exists as a backstop and
   stays in the pipeline regardless — it costs nothing when the gorge is already correct, because
   it transfers structure rather than replacing pixels.
4. Backs are lower risk: no lapels, no gorge.

If Fable supports seed locking or multi-image identity, that is worth testing before falling back
to edit-chaining — it would remove the one mechanism that has caused the most damage.

---

## 4. Stage 3 — derivation, if the hero is accepted

Per render, in order:

```bash
python3 builder/normalize_render.py renders_v2/<name>.png     # sweep + framing
python3 builder/check_render.py      renders_v2/<name>.png     # 10 acceptance checks
python3 builder/check_rebuild.py     renders_v2/<name>.png     # the rebuild axes + gorge sheet
python3 builder/make_mask.py  <render> /tmp/m.png
python3 builder/make_drape.py <render> /tmp/m.png drape_maps/<name>_drape.png
```

Then Marigold **once over the whole batch** — ~18 min per render on the 8 GB M1 with Chrome open,
so quit Chrome and run it off-hours. Then `python3 builder/build_configurator_v0.py`.

Add the new names to `CUTS` in the builder first.

**Nothing in the compositor changes.** The renders are an input, not a dependency — every fix
made this session applies unchanged to a new set.

---

## 5. What is already fixed and does not depend on this

Committed this session, independent of the rebuild:

- **Sleeve run-width** (`panels.py`) — a 2 px mask speck was flipping whole trouser rows to the
  SLEEVE panel, jumping the pattern ~4 px sideways. 27,403 px → 177. This was the ruled horizontal
  break across the thighs.
- **Seam-phase region** (`build_configurator_v0.py`) — the front-overlap phase offset ended at a
  fixed 0.46 of image height, cutting straight across the chest. Now runs to the jacket hem.
  Torso-R row correlation 0.06 → 0.83.
- **Side views removed** — front and back only, 4.96 MB.

Not yet built, and worth doing whether or not the rebuild proceeds:

- **The construction detail layer** (prototyped, §Suitsupply below). Extract the render's
  band-pass inside the mask, zero-mean it, re-apply multiplicatively over the cloth. Measured cost
  after zero-meaning: +0.17% exposure shift, no hue drift. Fixes buttons taking the cloth's
  colour, welts and flaps vanishing, the lapel having no roll, and `soften_drape`'s blur erasing
  thin lines — five findings, one mechanism.

---

## 6. What the Suitsupply teardown changed

Their configurator preview is **not** a photograph. It is ~30–38 flat CAD layers, and the base
`model` layer is a bare torso shell — no collar, no lapels, no sleeves. The gorge that has cost us
the most is something they never generate: it is a dedicated `lapel/{option}` layer, drawn once
and reused across every fabric.

We cannot copy the whole architecture — their layers are baked **per fabric**, which is why they
need ~25,000 of them, and our fabric-independent asset count is the commercial case for this build.
But the separation is portable: construction is geometry, not colour, so it needs one layer per
cut-view, not one per fabric. That is exactly what the detail layer in §5 does.

Their beautiful AI hero is a separate per-fabric marketing still, shown while browsing fabrics —
and its relaxed, hand-in-pocket pose is the one our own persona research rejected because it
distorts drape and breaks masking. We cannot copy that either.

---

## 7. Abort criteria

Stop and keep the current renders if:

- the gorge is still broken across 3 candidates — the ceiling is real, and it is the model's, not
  the prompt's;
- construction detail density comes in **below** 17.3% — a prettier render with less structure is
  a worse input, because the compositor now consumes that band directly;
- identity cannot be held across cuts without reintroducing instruction drift.

None of these are failures. Each one converts an open strategic question into a settled one, which
is the whole point of spending one image on it.
