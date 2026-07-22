#!/usr/bin/env python3
"""Batch: generate high-quality Marigold NORMAL MAPS for all house-model cuts.
Run OFF-HOURS with heavy apps closed (M1 / 8GB RAM). Model already cached (~4.8GB).
Run with:  ~/gcc_normals_venv/bin/python ~/Desktop/GCC_House_Model/gen_normals_all.py
Outputs per cut -> drape_maps/<cut>_normal.png (viz) + <cut>_normal.npy (raw HxWx3 in [-1,1]).
Logs to gen_normals.log.
"""
import os, sys, time, traceback
import numpy as np
from PIL import Image
import torch
from diffusers import MarigoldNormalsPipeline

HM = "/Users/runiwillner/Desktop/GCC_House_Model"
LOG = open(f"{HM}/gen_normals.log", "a")
def log(m):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {m}"
    print(line, flush=True); LOG.write(line + "\n"); LOG.flush()

# QUALITY settings (apps closed -> can afford these on 8GB). Lower RES if OOM.
STEPS = int(os.environ.get("N_STEPS", 4))
RES   = int(os.environ.get("N_RES", 768))
# fp16 on MPS produces NaNs (degenerate maps) -> use fp32. Env N_DTYPE=fp16 to override.
DTYPE = torch.float16 if os.environ.get("N_DTYPE") == "fp16" else torch.float32
CUTS = sys.argv[1:] or ["front_2button_notch", "front_2button_peak", "front_1button_peak",
        "front_doublebreasted", "front_3piece_vest"]

log(f"=== START normals: steps={STEPS} res={RES} cuts={len(CUTS)} ===")
dev = "mps" if torch.backends.mps.is_available() else "cpu"
log(f"device={dev}")
t0 = time.time()
try:
    pipe = MarigoldNormalsPipeline.from_pretrained(
        "prs-eth/marigold-normals-v1-1", torch_dtype=DTYPE, local_files_only=True).to(dev)
    log(f"dtype={DTYPE}")
    pipe.enable_attention_slicing()
    try: pipe.enable_vae_slicing()
    except Exception: pass
    log(f"model loaded {time.time()-t0:.0f}s")
except Exception as e:
    log("MODEL LOAD FAILED: " + repr(e)); log(traceback.format_exc()); sys.exit(1)

ok = 0
for cut in CUTS:
    src = f"{HM}/renders/{cut}.png"
    if not os.path.exists(src):
        log(f"SKIP {cut} (no render)"); continue
    try:
        t1 = time.time()
        img = Image.open(src).convert("RGB")
        out = pipe(img, num_inference_steps=STEPS, ensemble_size=1,
                   processing_resolution=RES, match_input_resolution=True)
        if np.isnan(out.prediction).any():
            log(f"FAIL {cut}: prediction is NaN ({np.isnan(out.prediction).mean()*100:.0f}%) — bad dtype/precision"); continue
        vis = pipe.image_processor.visualize_normals(out.prediction)[0]
        vis.save(f"{HM}/drape_maps/{cut}_normal.png")
        np.save(f"{HM}/drape_maps/{cut}_normal.npy", out.prediction[0].astype("float16"))
        ok += 1
        log(f"OK {cut}  {vis.size}  {time.time()-t1:.0f}s")
    except Exception as e:
        log(f"FAIL {cut}: {repr(e)}")
log(f"=== DONE {ok}/{len(CUTS)} normals in {time.time()-t0:.0f}s ===")
LOG.close()
