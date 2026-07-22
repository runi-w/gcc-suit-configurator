# Adversarial review of RESEARCH_FINDINGS.md — revise the report

Paste into the SAME research session (Sonnet) that produced `plan/RESEARCH_FINDINGS.md`.

---

Your report was reviewed adversarially against its own cited sources. The competitor teardown (§2) and evidence-tier honesty hold up well — leave them. But one **load-bearing claim fails** and there are **three gaps** that would misdirect real money and effort. Address each below, then **revise `plan/RESEARCH_FINDINGS.md` in place** and append a short "## 7. Revision after adversarial review" section stating exactly what you changed and why. Where you disagree, defend it with evidence, don't hand-wave.

## Challenge 1 (load-bearing) — "AI-bake fixes wrap for free" is contradicted by your own cited memory

Your AI-technique matrix and Recommendation 1 claim image-to-image swap solves per-panel wrap, "proven repeatedly in the catalog work: windowpanes/houndstooth/pinstripes correctly follow garment structure." Re-read the `gcc-fabric-ai-product-images` memory you cite — it documents the **opposite** for exactly those fabrics:
- a **15-fabric bold-check/windowpane REWORK LIST** (they rendered badly);
- **DBS139A "user unhappy"**; DBQ791A's deterministic attempt the user called **"TERRIBLE"**;
- the fix required the **user photographing cloth with a ruler + SpyderCheckr**, then a **two-step double-method** (gpt-5.5-pro writing prompts for gpt-image-2), per view;
- front/back **colour drift needed recolour QA on 36/116 Elite + 18/37 Prestige**.

So: for **solids and subtle textures** AI-bake is easy and good; for **directional patterns — the pinstripes/checks/windowpanes the business is actually struggling with — it was the hardest, most expensive, sometimes-failed part.** Correct the matrix and Rec 1 to say this plainly, and split the "wrap solved?" verdict by fabric class (solid/texture = yes, easy; bold directional pattern = only with heavy per-fabric human work, sometimes unsatisfactory).
- **Definitive way to settle it** (state this as the required validation gate even if you don't run it): one empirical bake — run the real Gemini recipe on a chalk-stripe and a windowpane onto `renders/front_2button_notch.png` and inspect whether stripe *direction* and per-panel wrap come out correct, vs the current compositor. Do not trust the "free wrap" claim until that specific test passes.

## Challenge 2 — the cost estimate is API-only; the real cost is human hours + cross-cut consistency

"166 × 5 ≈ 830 renders ≈ $40–125" counts only the API call. Rebuild it to include what the catalog record proves the patterned fabrics actually cost: ruler photoshoots, multiple engine passes, and colour QA. Add the burden Rec 1 never mentions: baking **per cut** requires the cuts to stay consistent **with each other** (same man, same cloth colour across notch/peak/DB), which the catalog work shows drifts and needed per-item recolour fixes. Give a realistic effort estimate that separates the cheap solids from the expensive directional patterns.

## Challenge 3 — Rec 1 has an unstated hard dependency

Rec 1 says "feed the configurator's own 5 cut base renders." Per HANDOVER, **4 of those 5 are the old, inconsistent house models** — the standing blocker. So per-cut baking is *gated on the 14-render regeneration first*, then inherits cross-cut consistency QA. State this dependency explicitly. Also note: the catalog pipeline's "proven" bakes were all on the **walking** catalog model; the configurator's house model is a **standing** pose — an untested base for the swap.

## Challenge 4 — surface the buried strategic question, and add the option you missed

"Demote the compositor to quick-preview" implies that if the fabric step *and* the options are baked stills, the configurator collapses into the product catalogue the business already has (165 live stills). Confront that directly: what is the configurator *for* under your recommendation?

Then add the option the report omits — **difficulty-routing**, which is likely the real optimum: the runtime compositor now measures at Suitsupply parity for solids/herringbone/birdseye/subtle textures (colour, scale, sharpness, no moiré, tonal range — per this session's audit), so **keep the compositor for the easy majority and AI-bake only the ~15–30 bold directional patterns** where wrap breaks and the per-fabric hand-work is worth it. This keeps live interactivity for most of the book and spends effort only where it pays. Your Rec 3 "hybrid" is about *when* to show a bake, not *which fabrics* deserve one — add difficulty-routing as a distinct, first-class recommendation and rank it against bake-everything.

## Output
Revise `plan/RESEARCH_FINDINGS.md` in place (fix §3 matrix, Rec 1, the cost lines, add the difficulty-routing recommendation, add the base-render dependency), and append "## 7. Revision after adversarial review" summarising each change. Keep the parts that held up.
