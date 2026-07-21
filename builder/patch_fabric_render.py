#!/usr/bin/env python3
"""Wire the new fabric pipeline into the configurator build (items 1,2,3,4,7).

 - fabrics now come from fabric_build/ (real Elite Wool, 300-DPI derived)
 - TRUE SCALE baked into the tile size, so runtime density is a constant  [item 2]
 - tiles are wrap-blended, not mirrored                                    [item 3]
 - per-fabric sheen + relief params                                        [item 4]
 - per-fabric weave micro-normal rides along                               [item 7]
 - additive grazing-angle SHEEN pass in the compositor                     [item 1]
"""
import re
src = open('build_configurator_v0.py').read()

# ---------- 1. raise render resolution (weave/pattern need pixels) ----------
src = src.replace("W = 470", "W = 700", 1)

# ---------- 2. replace the fabric block: source, scale, params ----------
old_start = src.index("# fabric: code, name, kind, indicative upcharge $")
old_end   = src.index("def datauri(")
new_block = '''# Fabrics come from prep_fabrics.py (real Elite Wool scans, 300 DPI -> true cm scale).
FAB_DIR = "fabric_build"
OVERSAMPLE = 4          # tile is baked at 4x its on-screen size -> runtime density is a constant
FIGURE_CM = 183.0       # model height, for px-per-cm on the render
FIGURE_FRAC = 0.93      # fraction of frame height the figure occupies

'''
src = src[:old_start] + new_block + src[old_end:]

# ---------- 3. replace the fabric-processing loop ----------
old_fab_start = src.index("ANALYSIS = {}")
old_fab_end   = src.index("# curated option set")
new_fab = '''PX_PER_CM = (FIGURE_FRAC * H) / FIGURE_CM     # how many render px one cm of cloth spans
FABMETA = json.load(open(f"{FAB_DIR}/fabrics.json"))
fabs = []
for m in FABMETA:
    tp = os.path.join(FAB_DIR, f"tile_{m['code']}.jpg")
    npth = os.path.join(FAB_DIR, f"norm_{m['code']}.jpg")
    if not os.path.exists(tp):
        continue
    # TRUE SCALE: bake the tile at OVERSAMPLE x its real on-screen size
    on_screen = m["cmPerTile"] * PX_PER_CM
    out_px = max(24, int(round(on_screen * OVERSAMPLE)))
    tile = Image.open(tp).convert("RGB").resize((out_px, out_px), Image.LANCZOS)
    micro = Image.open(npth).convert("RGB").resize((out_px, out_px), Image.LANCZOS) if os.path.exists(npth) else None
    fab = {
        "code": m["code"], "name": m["name"], "kind": m["kind"],
        "tile": datauri(tile, "JPEG", quality=90, optimize=True),
        "sheen": m["sheen"], "relief": m["relief"],
        "cmPerTile": m["cmPerTile"], "onScreenPx": round(on_screen, 1),
        "price2pc": 575, "priceVest": 200,
    }
    if micro is not None:
        fab["micro"] = datauri(micro, "JPEG", quality=86, optimize=True)
    fabs.append(fab)
print(f"px/cm on render = {PX_PER_CM:.2f}; fabric tiles baked at {OVERSAMPLE}x true scale")

'''
src = src[:old_fab_start] + new_fab + src[old_fab_end:]

# ---------- 4. compositor: constant density, graze map, sheen pass ----------
src = src.replace(
  "const WARP_AMP_N=6,NZ_MIN=0.35,NSMOOTH=3,WARP_CAP=34,PAT_DENSITY=2.15,SEAM_PHASE=0.42,SEAM_BUTTON=0.46,SS=3;",
  "const WARP_AMP_N=6,NZ_MIN=0.35,NSMOOTH=3,WARP_CAP=34,PAT_DENSITY=4,SEAM_PHASE=0.42,SEAM_BUTTON=0.46,SS=3;\n"
  "const OVERSAMPLE=4;            // tiles are pre-scaled, so sampling density is constant\n"
  "const SHEEN_POW=1.6;           // how tightly the sheen hugs grazing angles\n"
  "const GLINT=0.55;              // how much the weave micro-normal modulates the sheen")

# buildWarpNormal also emits a grazing-angle map (sheen peaks where the surface turns away)
src = src.replace(
  "  return {dispX,dispY,alpha};}",
  "  const graze=new Float32Array(W*H);\n"
  "  for(let i=0;i<W*H;i++){if(!alpha[i])continue;const nz=Math.min(1,Math.abs(g[i*4+2]/127.5-1));\n"
  "    graze[i]=Math.pow(1-nz,SHEEN_POW);}\n"
  "  return {dispX,dispY,alpha,graze};}")

# warpedCloth: sample the micro-normal too, and emit a parallel SHEEN buffer
src = src.replace(
  "function warpedCloth(cutId,code){const {dispX,dispY,alpha}=cutAssets[cutId].warp,panel=cutAssets[cutId].panel,T=fabPix[code],tw=T.w,th=T.h,td=T.d;",
  "let sheenBuf=null;\n"
  "function warpedCloth(cutId,code){const {dispX,dispY,alpha,graze}=cutAssets[cutId].warp,panel=cutAssets[cutId].panel,T=fabPix[code],tw=T.w,th=T.h,td=T.d;\n"
  "  const MN=microPix[code]||null,fdef=FABRICS.find(f=>f.code===code)||{},sheenAmt=(fdef.sheen!=null?fdef.sheen:0.14);\n"
  "  if(!sheenBuf||sheenBuf.length!==W*H)sheenBuf=new Float32Array(W*H);")

src = src.replace(
  "    const n=SS*SS;od[i*4]=lin2srgb(rl/n);od[i*4+1]=lin2srgb(gl/n);od[i*4+2]=lin2srgb(bl/n);od[i*4+3]=255;}",
  "    const n=SS*SS;const R=rl/n,G=gl/n,B=bl/n;\n"
  "    od[i*4]=lin2srgb(R);od[i*4+1]=lin2srgb(G);od[i*4+2]=lin2srgb(B);od[i*4+3]=255;\n"
  "    // --- sheen: luminance of the cloth, weighted to grazing angles, modulated by weave micro-normal ---\n"
  "    let gz=graze[i];\n"
  "    if(MN){let mx=cx%tw;if(mx<0)mx+=tw;let my=cy%th;if(my<0)my+=th;\n"
  "      const mp=((my|0)*tw+(mx|0))*4;const tilt=(MN[mp]/127.5-1)*0.5+(MN[mp+1]/127.5-1)*0.5;\n"
  "      gz*=(1+GLINT*tilt);}\n"
  "    sheenBuf[i]=Math.max(0,(0.2126*R+0.7152*G+0.0722*B))*gz*sheenAmt;}")

src = src.replace(
  "  clothX.putImageData(out,0,0);return clothC;}",
  "  clothX.putImageData(out,0,0);return clothC;}\n"
  "let sheenC,sheenX;\n"
  "function sheenLayer(){ // additive pass — multiply can only darken, sheen is what makes cloth read as cloth\n"
  "  if(!sheenC){sheenC=document.createElement('canvas');sheenC.width=W;sheenC.height=H;sheenX=sheenC.getContext('2d');}\n"
  "  const im=sheenX.createImageData(W,H),d=im.data;\n"
  "  for(let i=0;i<W*H;i++){const v=sheenBuf?sheenBuf[i]:0;const s=lin2srgb(v);\n"
  "    d[i*4]=s;d[i*4+1]=s;d[i*4+2]=s;d[i*4+3]=255;}\n"
  "  sheenX.putImageData(im,0,0);return sheenC;}")

# render(): always use the tiled/warped path, then add the sheen
src = src.replace(
  "  const f=FABRICS.find(x=>x.code===state.fabric),useWarp=f.kind==='pattern';\n"
  "  ox.setTransform(1,0,0,1,0,0);ox.clearRect(0,0,W,H);ox.globalCompositeOperation='source-over';\n"
  "  if(useWarp){ox.drawImage(warpedCloth(cut,state.fabric),0,0);}else{ox.fillStyle=pat[state.fabric];ox.fillRect(0,0,W,H);}",
  "  const f=FABRICS.find(x=>x.code===state.fabric);\n"
  "  ox.setTransform(1,0,0,1,0,0);ox.clearRect(0,0,W,H);ox.globalCompositeOperation='source-over';\n"
  "  ox.drawImage(warpedCloth(cut,state.fabric),0,0);   // tiled at true scale for every cloth")

src = src.replace(
  "  hx.drawImage(off,0,0);",
  "  hx.drawImage(off,0,0);\n"
  "  // additive sheen, masked to the suit\n"
  "  ox.globalCompositeOperation='source-over';ox.clearRect(0,0,W,H);\n"
  "  ox.drawImage(sheenLayer(),0,0);\n"
  "  ox.globalCompositeOperation='destination-in';ox.drawImage(A.drapeLA,0,0);\n"
  "  ox.globalCompositeOperation='source-over';\n"
  "  hx.globalCompositeOperation='lighter';hx.drawImage(off,0,0);hx.globalCompositeOperation='source-over';")

# init(): also decode the micro-normal tiles
src = src.replace(
  "  await Promise.all(FABRICS.map(async f=>{const t=await load(f.tile);pat[f.code]=ox.createPattern(t,'repeat');",
  "  await Promise.all(FABRICS.map(async f=>{const t=await load(f.tile);pat[f.code]=ox.createPattern(t,'repeat');\n"
  "    if(f.micro){const mi=await load(f.micro);const mc=document.createElement('canvas');mc.width=mi.naturalWidth;mc.height=mi.naturalHeight;\n"
  "      const mxx=mc.getContext('2d');mxx.drawImage(mi,0,0);microPix[f.code]=mxx.getImageData(0,0,mc.width,mc.height).data;}")

src = src.replace("let W=0,H=0,off,ox,cutAssets={},pat={},fabPix={};",
                  "let W=0,H=0,off,ox,cutAssets={},pat={},fabPix={},microPix={};")

open('build_configurator_v0.py','w').write(src)
print("patched compositor: true-scale tiles + per-fabric sheen/relief + additive grazing sheen pass")
