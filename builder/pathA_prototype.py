#!/usr/bin/env python3
"""Path A per-panel pattern-wrap PROTOTYPE (2026-07-22).

Proof-of-concept that the runtime compositor CAN wrap a pinstripe per garment panel — vertical
on the torso, diagonal along the lapel, tilted on the sleeves — instead of one global-vertical
warp. Built in Python (fast to iterate) on the notch-front render; if the approach is approved
after the R1-R4 research (see plan/PATH_A_RESEARCH_PLAN.md), it gets ported into the live JS
compositor (`buildWarpNormal`/`warpedCloth` in build_configurator_v0.py).

Run:  python3 builder/pathA_prototype.py
Out:  scratchpad panels_v2.png (panel viz) + proto_compare2.png (vertical vs per-panel grain).

STATUS / KNOWN GAPS (the research is meant to resolve these before a real port):
  - The per-panel grain ANGLES here are GUESSED (lapel 20deg, sleeve 6deg). Real targets come
    from measuring Suitsupply (R2) + tailoring convention (R1).
  - The MECHANISM is a naive tile-rotation. The real driver per panel may be the Marigold normal
    (3D surface), the SIL_WRAP silhouette-width taper, or a genuine cut-grain — that is the crux
    question the research must answer per panel.
  - Panel-boundary SEAMS are ragged (hard theta jump). Clean tailored seam breaks are unbuilt.
  - Segmentation is geometric heuristics on ONE render; needs refining + rolling to all 15.
"""
import numpy as np, json, os
from PIL import Image, ImageDraw, ImageFont
import sys
HM = "/Users/runiwillner/Desktop/GCC_House_Model"
sys.path.insert(0, f"{HM}/builder")
from make_mask import suit_mask, _dilate

OUT = os.environ.get("OUT", "/tmp")
W = 1300

# ---------------------------------------------------------------- segmentation
render = Image.open(f"{HM}/renders/front_2button_notch.png").convert("RGB")
H = round(render.height * W / render.width)
render = render.resize((W, H), Image.LANCZOS)
a = np.asarray(render).astype(float)
mask = np.asarray(suit_mask(render).resize((W, H))) > 127
V = a.max(-1) / 255
mn = a.min(-1)
Sat = np.where(a.max(-1) > 0, (a.max(-1) - mn) / np.maximum(a.max(-1), 1e-6), 0)

cen = np.full(H, W / 2.0); hw = np.zeros(H)
for y in range(H):
    xs = np.where(mask[y])[0]
    if len(xs):
        cen[y] = (xs[0] + xs[-1]) / 2; hw[y] = (xs[-1] - xs[0]) / 2
def smooth(arr, r=25):
    k = np.ones(2 * r + 1) / (2 * r + 1)
    return np.convolve(np.pad(arr, r, "edge"), k, "same")[r:-r]
cenS = smooth(cen); hwS = smooth(hw)

# shirt V-neck: bright neutral hole in the upper centre -> lapels are the garment adjacent to it
shirt = (V > 0.80) & (Sat < 0.12) & (~mask)
shirt[:int(H * 0.16)] = False; shirt[int(H * 0.62):] = False
sc = np.where(shirt.any(1))[0]; neck_y = sc[0] if len(sc) else int(H * 0.22)
cb = shirt[:, int(W * 0.44):int(W * 0.56)]; br = np.where(cb.any(1))[0]
button_y = (br[-1] if len(br) else int(H * 0.42))
hem_y = int(H * 0.60)
for y in range(int(H * 0.52), int(H * 0.72)):
    if hwS[y] < 0.55 * hwS[int(H * 0.30):int(H * 0.50)].max():
        hem_y = y; break
shoulder_y = int(H * 0.22)
for y in range(int(H * 0.15), int(H * 0.4)):
    if hwS[y] > 0.60 * hwS.max():
        shoulder_y = y; break

yy, xx = np.mgrid[0:H, 0:W]; c = cenS[yy]; hwr = hwS[yy]
shirt_near = _dilate(shirt, 26)
lapel = shirt_near & mask & (yy >= neck_y) & (yy < button_y + 10)
sleeve = mask & (np.abs(xx - c) > 0.60 * hwr) & (yy > shoulder_y) & (yy < hem_y)
trous = mask & (yy >= hem_y)
jacket = mask & (yy < hem_y)
# panels: 1 torsoL 2 torsoR 3 lapelL 4 lapelR 5 sleeveL 6 sleeveR 7 trouser
panel = np.zeros((H, W), np.uint8)
panel[jacket & (xx < c)] = 1; panel[jacket & (xx >= c)] = 2
panel[sleeve & (xx < c)] = 5; panel[sleeve & (xx >= c)] = 6
panel[lapel & (xx < c)] = 3; panel[lapel & (xx >= c)] = 4
panel[trous] = 7

col = {1:(70,110,200),2:(90,170,230),3:(235,110,50),4:(245,175,60),5:(120,200,120),6:(70,175,110),7:(150,110,190)}
viz = a.copy()
for k, c3 in col.items():
    m = panel == k; viz[m] = viz[m] * 0.4 + np.array(c3) * 0.6
Image.fromarray(np.clip(viz, 0, 255).astype("uint8")).save(f"{OUT}/panels_v2.png")

# ---------------------------------------------------------------- per-panel warp + composite
rl = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
shade = (rl / np.median(rl[mask]))[..., None]          # transfer render's drape onto the cloth
fab = {f["code"]: f for f in json.load(open(f"{HM}/fabric_build/fabrics.json"))}
code = "DBT6860"; cmPerTile = fab[code]["cmPerTile"]; PXCM = 8.85
onpx = max(8, int(round(cmPerTile * PXCM)))
tile = np.asarray(Image.open(f"{HM}/fabric_build/tile_{code}.jpg").convert("RGB")
                  .resize((onpx * 4, onpx * 4), Image.LANCZOS)).astype(float)
tw = th = onpx * 4; dens = 4.0
ANG = {1:0.0, 2:0.0, 3:+20.0, 4:-20.0, 5:-6.0, 6:+6.0, 7:0.0}   # GUESSED — see docstring
theta = np.zeros((H, W))
for k, ang in ANG.items():
    theta[panel == k] = np.radians(ang)

def warp(theta):
    yg, xg = np.mgrid[0:H, 0:W].astype(float)
    ct, st = np.cos(theta), np.sin(theta)
    u = (xg * ct + yg * st) * dens; v = (-xg * st + yg * ct) * dens
    fu = u % tw; fv = v % th
    x0 = np.floor(fu).astype(int); y0 = np.floor(fv).astype(int)
    x1 = (x0 + 1) % tw; y1 = (y0 + 1) % th; ax = (fu - x0)[..., None]; ay = (fv - y0)[..., None]
    return (tile[y0, x0]*(1-ax)*(1-ay) + tile[y0, x1]*ax*(1-ay)
            + tile[y1, x0]*(1-ax)*ay + tile[y1, x1]*ax*ay)

def comp(cloth):
    shaded = np.clip(cloth * shade, 0, 255); m = mask[..., None]
    return np.clip(a * (1 - m) + shaded * m, 0, 255).astype("uint8")

vert = comp(warp(np.zeros((H, W)))); grain = comp(warp(theta))
def font(s):
    try: return ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", s)
    except Exception: return ImageFont.load_default()
def block(imV, imG, box, H2, t1, t2):
    A = Image.fromarray(imV).crop(box); B = Image.fromarray(imG).crop(box)
    A = A.resize((int(A.width * H2 / A.height), H2)); B = B.resize((int(B.width * H2 / B.height), H2))
    m = Image.new("RGB", (A.width + B.width + 14, H2 + 28), (24, 24, 26)); d = ImageDraw.Draw(m)
    m.paste(A, (0, 28)); m.paste(B, (A.width + 14, 28))
    d.text((5, 5), t1, font=font(18), fill=(255, 255, 255))
    d.text((A.width + 19, 5), t2, font=font(18), fill=(150, 220, 150)); return m
chest = block(vert, grain, (int(W*0.30), int(H*0.17), int(W*0.74), int(H*0.62)), 560,
              "CURRENT all-vertical", "PER-PANEL grain")
lap = block(vert, grain, (int(W*0.40), int(H*0.18), int(W*0.62), int(H*0.40)), 440,
            "lapel: vertical", "lapel: grain (diagonal)")
full = Image.new("RGB", (max(chest.width, lap.width), chest.height + lap.height + 12), (24, 24, 26))
full.paste(chest, (0, 0)); full.paste(lap, (0, chest.height + 12))
full.save(f"{OUT}/proto_compare2.png")
print(f"wrote {OUT}/panels_v2.png and {OUT}/proto_compare2.png  (onpx={onpx})")
