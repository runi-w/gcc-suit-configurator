# Gage Court Suit Configurator

Self-serve custom-suit configurator for gcclothiers.com. Customer picks cloth + style, sees it
rendered on a house model, pays on Shopify; an order envelope is handed to a backend that submits
to KuteTailor.

**Start with [`HANDOVER.md`](HANDOVER.md)** — full state, locked constants, next actions — and the
`gcc-pattern-render-playbook` memory (the locked rendering standard).

## Build

```bash
cd builder && python3 build_configurator_v0.py   # writes ../configurator-v0.html
```

Reproduces byte-identical output. Preview over `http://` (not `file://`).

## What's in the repo vs not

Committed: all source (`builder/`, `audit/*.py`, `config/*.json`), the plan docs (`plan/`), and the
**irreplaceable AI renders** (`renders/`, `renders_v2/`, `drape_maps/*.png`).

Not committed (see `.gitignore`): the 121 MB mill scans (`hires_swatches/` — source material,
back up separately), Marigold `.npy` maps (regenerable from renders), the build artifact
(`configurator-v0.html`, reproducible), and re-downloadable reference imagery.

## Credentials

**Never in the repo.** Live outside the tree in `~/Desktop/GCC_Fabric_Handoff/keys/`:
`gemini_key.txt` (render generation) and `kutetailor_creds.json` (order submission). Both are read
at runtime by the scripts that need them.

## Pipeline (regenerating a render)

```
gen_model.py  →  normalize_render.py  →  check_render.py  →  make_mask.py  →  make_drape.py  →  Marigold  →  build
```

Details and the acceptance thresholds are in `plan/MODEL_BIBLE.md` and `plan/AI_PROMPT_PACK.md`.
