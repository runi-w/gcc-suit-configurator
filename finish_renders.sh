#!/bin/bash
# One-shot: finish the 14 new renders -> masks + drapes + Marigold normals + rebuild.
# Run with heavy apps (Chrome) CLOSED — Marigold needs ~5GB and the 8GB M1 swap-thrashes
# otherwise (~1 hr/render vs ~1-2 min when RAM is free).
set -e
cd ~/Desktop/GCC_House_Model
NEW="front_2button_peak front_1button_peak front_doublebreasted front_3piece_vest \
side_2button_notch side_2button_peak side_1button_peak side_doublebreasted side_3piece_vest \
back_2button_notch back_2button_peak back_1button_peak back_doublebreasted back_3piece_vest"

echo "=== 1/3 masks + drapes (CPU, fast) ==="
for r in $NEW; do
  python3 builder/make_mask.py  renders/$r.png /tmp/${r}_mask.png >/dev/null
  python3 builder/make_drape.py renders/$r.png /tmp/${r}_mask.png drape_maps/${r}_drape.png >/dev/null
  echo "  $r"
done

echo "=== 2/3 Marigold normals (low-res 448 to fit 8GB; ~1-2 min each with RAM free) ==="
N_RES=448 N_STEPS=4 ~/gcc_normals_venv/bin/python gen_normals_all.py $NEW

echo "=== 3/3 rebuild ==="
python3 builder/build_configurator_v0.py
echo "DONE — configurator-v0.html rebuilt with all 5 cuts x front/side/back."
