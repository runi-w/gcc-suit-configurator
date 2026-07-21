import numpy as np, glob, json
from PIL import Image

def lin(x):
    x=np.asarray(x,dtype=np.float64)/255.0
    return np.where(x<=0.04045,x/12.92,((x+0.055)/1.055)**2.4)
def lum(rgb):
    l=lin(rgb); return 0.2126*l[...,0]+0.7152*l[...,1]+0.0722*l[...,2]

def fundamental(prof, pmin, pmax):
    """autocorrelation fundamental period, in px, searched in [pmin,pmax]"""
    p=prof-prof.mean()
    n=len(p)
    if n < pmax*2: pmax=max(pmin+2, n//2)
    ac=np.correlate(p,p,'full')[n-1:]
    ac/= (ac[0]+1e-12)
    lo,hi=int(pmin),int(min(pmax,len(ac)-2))
    if hi<=lo+1: return None,0
    seg=ac[lo:hi]
    # local maxima only
    k=None; best=-9
    for i in range(1,len(seg)-1):
        if seg[i]>seg[i-1] and seg[i]>=seg[i+1] and seg[i]>best:
            best=seg[i]; k=i+lo
    if k is None: return None,0
    # parabolic refine
    y0,y1,y2=ac[k-1],ac[k],ac[k+1]
    d=(y0-y2)/(2*(y0-2*y1+y2)+1e-12)
    return k+d, best

def hprofile(gray, mask, y0f, y1f, xpad, detrend):
    h,w=gray.shape
    ys=slice(int(h*y0f),int(h*y1f))
    band=gray[ys]; bm=mask[ys]
    cols=np.where(bm.all(0))[0]           # only fully-covered columns
    if len(cols)<60: 
        cols=np.where(bm.mean(0)>0.9)[0]
    if len(cols)<60: return None
    # longest contiguous run
    splits=np.split(cols,np.where(np.diff(cols)!=1)[0]+1)
    run=max(splits,key=len)
    if len(run)<60: return None
    pad=int(len(run)*xpad); run=run[pad:len(run)-pad] if pad*2<len(run)-20 else run
    prof=band[:,run].mean(0)
    prof=prof-np.convolve(prof,np.ones(detrend)/detrend,mode='same')
    return prof[detrend:-detrend] if len(prof)>2*detrend+20 else prof

OUT={}
# ---------- 1. TRUTH: source scans, 118.11 px/cm ----------
print('%-11s %-28s %s'%('CODE','TRUE pitch from 300dpi scan',''))
truth={}
for code in ['DBU080A','DBV196A','DBS137A','DEE1017','DBS139A','DBV305A','DBS131A']:
    f=glob.glob(f'hires_swatches/2501-117/*{code}*')
    if not f: continue
    g=lum(np.array(Image.open(f[0]).convert('RGB')))
    h,w=g.shape
    c=g[int(h*.12):int(h*.88), int(w*.12):int(w*.88)]
    prof=c.mean(0); prof=prof-np.convolve(prof,np.ones(201)/201,mode='same'); prof=prof[201:-201]
    # macro pattern: 0.8 cm .. 7 cm  -> 94 .. 827 px
    per,st=fundamental(prof, 0.8*118.11, 7.0*118.11)
    if per: truth[code]=per/118.11
    print(f'  {code:9s} {per and round(per,1)!s:>8s} px = {truth.get(code,float("nan")):5.2f} cm   (acf {st:.2f})')
OUT['truth_cm']=truth

# ---------- 2. OURS ----------
ps=[p for p in sorted(glob.glob('audit/ours/ours_D*.png')) if 'stripe' not in p]
arrs={p.split('ours_')[-1][:-4]: np.array(Image.open(p).convert('RGB')) for p in ps}
st=np.stack([a.astype(float) for a in arrs.values()])
MASK=st.std(0).mean(-1)>6.0
chest_ours=int(MASK[int(937*.12):int(937*.30)].sum(1).max())
PXCM_OURS=chest_ours/45.0
print(f'\nOURS   canvas 700x937  chest={chest_ours}px -> {PXCM_OURS:.2f} px/cm  (playbook: 4.76)')
print('%-10s %8s %8s %8s %7s'%('CODE','period','=cm','true cm','ratio'))
ours={}
for code,a in arrs.items():
    g=lum(a)
    prof=hprofile(g,MASK,0.30,0.52,0.10,31)
    if prof is None: print(f'  {code} no profile'); continue
    per,acf=fundamental(prof, 0.8*PXCM_OURS, 7.0*PXCM_OURS)
    if not per: print(f'  {code:9s} none'); continue
    cm=per/PXCM_OURS; t=truth.get(code)
    ours[code]=dict(px=round(per,2),cm=round(cm,2),true=t and round(t,2),
                    ratio=(round(cm/t,2) if t else None), acf=round(acf,2))
    print(f'  {code:9s} {per:7.1f}px {cm:7.2f} {"" if not t else f"{t:7.2f}"} {"" if not t else f"{cm/t:6.2f}x"}  acf={acf:.2f}')
OUT['ours']=ours

# ---------- 3. SUITSUPPLY ----------
print('\nSUITSUPPLY  layer 1600x2000')
ss={}
for p in sorted(glob.glob('audit/ss/model_*.png')):
    nm=p.split('model_')[-1][:-4]
    a=np.array(Image.open(p).convert('RGBA'))
    g=lum(a[...,:3]); m=a[...,3]>200
    chest=int(m[int(2000*.12):int(2000*.30)].sum(1).max())
    pxcm=chest/45.0
    prof=hprofile(g,m,0.30,0.52,0.10,61)
    if prof is None: print(f'  {nm} no profile'); continue
    per,acf=fundamental(prof, 0.8*pxcm, 7.0*pxcm)
    if not per: print(f'  {nm:22s} none'); continue
    ss[nm]=dict(px=round(per,2),cm=round(per/pxcm,2),pxcm=round(pxcm,2),acf=round(acf,2))
    print(f'  {nm:22s} chest={chest}px {pxcm:5.2f}px/cm  period={per:7.1f}px = {per/pxcm:5.2f} cm  acf={acf:.2f}')
OUT['ss']=ss
json.dump(OUT,open('audit/out/periods.json','w'),indent=1,default=float)
print('\nwrote audit/out/periods.json')
