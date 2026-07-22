# Deep-research prompt — realistic drape & pattern-wrap for a 2D suit configurator

Paste everything below into a fresh **Claude Code (Sonnet)** session in `~/Desktop/GCC_House_Model`.

---

I need a deep, rigorously-verified research report. **Do not write code and do not tune anything** — this is research only. The output is a written report at `plan/RESEARCH_FINDINGS.md`.

## 0. Ground yourself first (do this before any research — it prevents redoing settled work)

Read, in order:
- `~/Desktop/GCC_House_Model/HANDOVER.md` — full state of the configurator.
- The `gcc-pattern-render-playbook` memory — the LOCKED rendering standard, plus a "tried-and-rejected" list. **Everything on that rejected list is closed; do not propose it.**
- The `gcc-fabric-ai-product-images` memory — an EXISTING, working AI pipeline that fabric-swaps a flat swatch onto a base model photo with Gemini and produces Suitsupply-grade per-fabric stills (116 Elite + 49 Prestige already live on Shopify).

## 1. The product & the two problems

A self-serve custom-suit configurator for gcclothiers.com. Architecture (settled, not up for debate): **2D compositing, not real-time 3D.** A house-model base photo + the customer's chosen cloth composited at runtime in the browser (a flat fabric tile warped by an AI-derived normal/drape map, ~10 screen px per cm of cloth). Add-to-cart on Shopify.

The two things that still look wrong, and the entire focus of this research:

1. **Drape** — the cloth reads flat. Real tailoring has soft body folds, near-black structural creases (lapel roll, front edge, under-flap, armscye), and light catching the crests. Ours is getting closer but isn't there.
2. **Pattern wrap** — pinstripes, glen checks, and windowpanes do not wrap around the garment's form. On a real suit each panel has its own grain: the lapel rolls to its own direction, each sleeve follows the sleeve's axis, the torso cylinder-wraps so stripes splay slightly toward the edges, and the pattern breaks cleanly at every seam. Ours warps the pattern with one global field, so it doesn't follow the panels.

## 2. Hard constraints (any recommendation must live inside these)

- **No CLO3D, no Marvelous Designer, no 3D garment CAD, no 3D artist, no in-house designer.** Assume none of these will ever be available. Solutions must be AI-forward and buildable by one engineer.
- Small business: ~1–3 online custom sales/month. Per-fabric offline compute is affordable; a $50k platform is not.
- Shopify standard plan; the deliverable is a self-contained page.
- Tools ALREADY on hand (confirm versions, don't assume): **Gemini 3 Pro Image ("nano banana")** for image-to-image fabric swap (key at `~/Desktop/GCC_Fabric_Handoff/keys/gemini_key.txt`); OpenAI **gpt-image-2**; **Marigold** for monocular normal/depth estimation; Python/PIL/canvas compositing. The fabric catalog is 117 Elite + 49 Prestige 300-DPI mill scans.

## 3. What is ALREADY PROVEN this session (treat as established; verify only if you find contradicting live evidence)

- Suitsupply and Hockerty are **pre-rendered 2D PNG layer stacks composited in the browser — neither runs real-time 3D.** SS: Cloudinary `cdn.suitsupply.com/.../suitconfig/{FABRIC}/{Garment}/{component}/{option}`, ~30–38 layers/view; switching fabric swaps the whole folder. SS also ships ONE `ai-generated/ai-model` still per fabric for the fabric-browsing step. Hockerty: Fabric.js, per-fabric-per-option 424×517 PNGs.
- **SS's "perfect wrap and drape" is BAKED per fabric offline**, not computed at runtime. That is why theirs is flawless and a runtime compositor struggles — different fidelity ceilings.
- On the **torso**, our pattern wrap already measures at SS parity; the unsolved wrap is **per-panel** (sleeves lean the wrong way, lapel doesn't roll to its own grain). Measured with `audit/pattern_map.py`.
- **AI cannot do garment CAD** (researched July 2026): Marvelous's AI Pattern Drafter is t-shirts only; the promising academic work (Dress-1-to-3, ReWeaver) is papers, not products. Don't propose these as shortcuts.
- Our existing catalog pipeline (Gemini fabric-swap onto a base model photo) **already produces SS-grade per-fabric on-model stills** with correct drape and wrap — because the AI renders the whole garment, form and all. The open question is how to make that the configurator's engine without losing interactivity or consistency across style options.

## 4. Research tasks

### A. Reverse-engineer the leaders — from LIVE ASSETS, not blog posts
For **Suitsupply** (gold standard), **Hockerty**, **Proper Cloth**, and **at least 4 more** you identify (candidates: Indochino, Black Lapel, Knot Standard, Sumissura, Tailor Store, Oliver Wicks, plus any Threekit/Zakeke/Emersya-powered builder). For each, open the live configurator and inspect the actual network assets / DOM:
- Real-time 3D (WebGL/three.js/model-viewer) or pre-rendered 2D layer stack? Prove it from what's loaded.
- Is the **pattern baked into each per-fabric asset**, or is a flat pattern composited/warped at runtime? Prove it (swap a striped fabric and watch what URLs change).
- How is **drape** achieved — baked shading, a normal/displacement map, a shadow layer stack?
- How is **pattern wrap per panel** achieved — baked, per-panel UV, or not attempted?
- Asset resolution and on-screen px/cm; how many assets per fabric.
- For any true-3D one: what's the source (PBR mesh?) and is delivery still pre-rendered layers?

### B. Survey the AI techniques (state of the art, 2026) for "flat swatch → realistic, draped, correctly-wrapped garment"
For each, report maturity (production-ready vs research), what it needs, cost, and how it addresses drape AND wrap:
- Image-to-image fabric transfer (Gemini/nano-banana, gpt-image-2) — the path we already use.
- Diffusion + **ControlNet / T2I-Adapter / IP-Adapter** conditioned on depth, normal, or a UV/grain map — can this force *correct per-panel wrap* while keeping the exact cloth?
- **UV-space texture synthesis / texture-to-garment** and neural material transfer.
- **Depth/normal estimation** (Marigold and successors) driving a displacement warp — the ceiling of the runtime approach.
- Differentiable/neural rendering, relighting, and any "garment texture replacement" models.
- Video/multi-view consistency tools, in case animated or multi-angle views are wanted.

### C. Resolve the core strategic question (the report must answer this directly)
Given the constraints, what is the **optimal division of labor** between (i) offline per-fabric AI bakes and (ii) runtime compositing — to maximize drape + wrap realism? Specifically test this hypothesis and confirm or refute it with evidence: *"Runtime 2D compositing has a fidelity ceiling below a per-fabric AI bake; the best achievable outcome mirrors Suitsupply — bake one high-quality image per fabric (and per major style if needed) with AI, and reserve runtime compositing only for fast option previews."* If refuted, say what beats it.

### D. Pattern-wrap, specifically
Concrete methods to get per-panel grain (lapel rolls to its own direction, each sleeve follows its axis, torso cylinder-wraps, clean seam breaks) **without a 3D model** — e.g. per-panel segmentation + per-panel UV/grain fields, AI depth→normal per panel, or baking the wrap per fabric. Rank by realism achievable within the constraints.

## 5. Method rules (the person who wrote this has been burned by unverified claims)
- **Verify against live assets and primary sources.** Distinguish what a vendor *markets* ("3D!") from what the browser *actually loads*. Quote the evidence (URLs, asset counts).
- Adversarially check every strong claim — try to refute it before reporting it. Flag anything you could not verify as unverified.
- Prefer 2024–2026 sources for AI capabilities; models move fast.
- When a quality question is subjective, describe how to settle it visually rather than asserting.

## 6. Deliverable → write to `plan/RESEARCH_FINDINGS.md`
1. **One-paragraph bottom line** — the single recommended path and why.
2. **Competitor teardown table** — each site: 2D-vs-3D, pattern baked-vs-composited, drape method, wrap method, assets/fabric, px/cm, evidence.
3. **AI-technique matrix** — technique × (maturity, needs, cost, drape?, wrap?, fits our constraints?).
4. **Ranked recommendations** — 3–5 concrete approaches, each with: how it fixes drape, how it fixes wrap, the exact AI tools, build effort, per-fabric cost, quality ceiling vs Suitsupply, and the first implementation step.
5. **What NOT to do** — dead ends (with the reason), so the next session doesn't re-explore them.
6. **Sources** — links, with the primary/live-asset evidence marked.

Be exhaustive and cite as you go. Use web search + fetch AND open the live configurators in the browser to inspect their real assets.
