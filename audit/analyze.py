import numpy as np, glob, os, json
from PIL import Image

def srgb2lin(x): 
    x=x/255.0
    return np.where(x<=0.04045, x/12.92, ((x+0.055)/1.055)**2.4)
def lum_lin(rgb): 
    l=srgb2lin(rgb.astype(np.float64))
    return 0.2126*l[...,0]+0.7152*l[...,1]+0.0722*l[...,2]

# ---------- masks ----------
def ss_mask(p):
    a=np.array(Image.open(p).convert('RGBA'))
    return a[...,:3], a[...,3]>200          # GOTCHA: hard mask alpha>200

def ours_stack():
    ps=sorted(glob.glob('ours/ours_D*.png'))
    ps=[p for p in ps if 'stripe' not in p]
    arrs=[np.array(Image.open(p).convert('RGB')).astype(np.float64) for p in ps]
    st=np.stack(arrs)                        # fabric region = pixels that change across fabrics
    var=st.std(0).mean(-1)
    m=var>6.0
    return ps, arrs, m

# ---------- geometry ----------
def widest_run(mask, y0f, y1f):
    h=mask.shape[0]; sub=mask[int(h*y0f):int(h*y1f)]
    return int(sub.sum(1).max())

def figure_height(mask):
    rows=np.where(mask.any(1))[0]
    return int(rows[-1]-rows[0]+1), int(rows[0]), int(rows[-1])

# ---------- pattern period via FFT ----------
def period_px(gray, mask, y0f, y1f, xpad=0.12):
    h,w=gray.shape
    ys=slice(int(h*y0f), int(h*y1f))
    band=gray[ys].copy(); bm=mask[ys]
    cols=np.where(bm.any(0))[0]
    if len(cols)<40: return None
    x0,x1=cols[0],cols[-1]; span=x1-x0
    x0+=int(span*xpad); x1-=int(span*xpad)
    seg=band[:,x0:x1]; sm=bm[:,x0:x1]
    rows=[r for r in range(seg.shape[0]) if sm[r].all()]
    if len(rows)<10: return None
    prof=seg[rows].mean(0)
    prof=prof-np.convolve(prof, np.ones(31)/31, mode='same')   # high-pass: kill shading
    prof*=np.hanning(len(prof))
    F=np.abs(np.fft.rfft(prof, n=8192))
    freqs=np.fft.rfftfreq(8192, d=1.0)
    lo,hi=len(prof)/60.0, len(prof)/4.0          # 4..60 repeats across the band
    band_idx=(freqs*len(prof)>=4)&(freqs*len(prof)<=60)
    if not band_idx.any(): return None
    k=np.argmax(np.where(band_idx,F,0))
    if freqs[k]<=0: return None
    return 1.0/freqs[k], (x1-x0), F[k]/ (F[band_idx].mean()+1e-9)

def stats(gray, mask):
    v=gray[mask]
    return dict(p1=round(float(np.percentile(v,1)),4), p5=round(float(np.percentile(v,5)),4),
                p50=round(float(np.percentile(v,50)),4), p95=round(float(np.percentile(v,95)),4),
                p99=round(float(np.percentile(v,99)),4),
                rng5_95=round(float(np.percentile(v,95)-np.percentile(v,5)),4),
                mean=round(float(v.mean()),4), std=round(float(v.std()),4))

print('='*100); print('SUITSUPPLY  Jacket/model layers  (1600x2000, alpha>200 mask)'); print('='*100)
ssres={}
for p in sorted(glob.glob('ss/model_*.png')):
    nm=os.path.basename(p)[6:-4]
    rgb,m=ss_mask(p); g=lum_lin(rgb)
    fh,r0,r1=figure_height(m)
    chest=widest_run(m,0.12,0.30)
    per=period_px(g,m,0.28,0.55)
    ssres[nm]=dict(chest_px=chest, garment_h=fh, top=r0, bot=r1, stats=stats(g,m),
                   period_px=(round(per[0],2) if per else None),
                   band_px=(per[1] if per else None),
                   peak_ratio=(round(float(per[2]),1) if per else None))
    s=ssres[nm]['stats']
    print(f"{nm:22s} chest={chest:4d}px  h={fh:4d}  period={str(ssres[nm]['period_px']):>7s}px "
          f"peak={str(ssres[nm]['peak_ratio']):>6s}  L p5-p95={s['rng5_95']:.3f} p1={s['p1']:.4f} med={s['p50']:.3f}")

print(); print('='*100); print('OURS  composited canvas (700x937, fabric mask = cross-fabric variance)'); print('='*100)
ps,arrs,m=ours_stack()
fh,r0,r1=figure_height(m)
chest=widest_run(m,0.12,0.30)
print(f"fabric-region mask: {m.sum()} px, garment bbox h={fh} (rows {r0}-{r1}), chest widest={chest}px")
ourres={}
for p,a in zip(ps,arrs):
    nm=os.path.basename(p)[5:-4]
    g=lum_lin(a)
    per=period_px(g,m,0.28,0.55)
    ourres[nm]=dict(chest_px=chest, stats=stats(g,m),
                    period_px=(round(per[0],2) if per else None),
                    band_px=(per[1] if per else None),
                    peak_ratio=(round(float(per[2]),1) if per else None))
    s=ourres[nm]['stats']
    print(f"{nm:22s} period={str(ourres[nm]['period_px']):>7s}px peak={str(ourres[nm]['peak_ratio']):>6s}"
          f"  L p5-p95={s['rng5_95']:.3f} p1={s['p1']:.4f} med={s['p50']:.3f}")

json.dump({'ss':ssres,'ours':ourres}, open('out/measure.json','w'), indent=1)
print('\nwrote out/measure.json')
