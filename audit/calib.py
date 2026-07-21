"""Rendered garment vs the mill scan DOWNSAMPLED to the render's px/cm.
Removes the resolution confound so the ratio isolates exposure. Target 1.00."""
import numpy as np, glob, json, sys
from PIL import Image
def lin(x):
    x=np.asarray(x,float)/255.
    return np.where(x<=0.04045,x/12.92,((x+0.055)/1.055)**2.4)
def Y(rgb):
    l=lin(rgb); return 0.2126*l[...,0]+0.7152*l[...,1]+0.0722*l[...,2]
pref,d = sys.argv[1], sys.argv[2]
PXCM = float(sys.argv[3]) if len(sys.argv)>3 else 8.85
ps=[p for p in sorted(glob.glob(f'{d}/{pref}D*.png')) if 'stripe' not in p]
imgs={p.split(pref)[-1][:-4]: np.array(Image.open(p).convert('RGB')) for p in ps}
M=np.stack([v.astype(float) for v in imgs.values()]).std(0).mean(-1)>6.0
fj={f['code']:f for f in json.load(open('fabric_build/fabrics.json'))}
rows=[]
for k,a in imgs.items():
    s=Image.open(glob.glob(f'hires_swatches/2501-117/*{k}*')[0]).convert('RGB')
    w,h=s.size; s=s.crop((int(w*.12),int(h*.12),int(w*.88),int(h*.88)))
    k2=PXCM/118.11                                   # match the render's cloth density
    s=s.resize((max(2,int(s.width*k2)),max(2,int(s.height*k2))),Image.LANCZOS)
    sc=Y(np.array(s)); g=Y(a)[M]
    rows.append((g.mean()/sc.mean(), np.median(g)/np.median(sc), fj[k]['name']))
mn=[r[0] for r in rows]; md=[r[1] for r in rows]
print(f'  {"fabric":22s} {"by MEAN":>8s} {"by MEDIAN":>10s}')
for a,b,n in sorted(rows): print(f'  {n:22s} {a:8.0%} {b:10.0%}')
print(f'  {"MEAN across fabrics":22s} {np.mean(mn):8.0%} {np.mean(md):10.0%}')
print(f'  {"SPREAD":22s} {max(mn)-min(mn):8.0%} {max(md)-min(md):10.0%}')
print(f'  -> next DRAPE_TARGET_MED multiplier x{(1.0/np.mean(mn))**(1/2.2):.4f}')
