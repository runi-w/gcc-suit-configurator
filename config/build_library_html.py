#!/usr/bin/env python3
"""Render library.json into a self-contained by-garment visual browser (library.html)."""
import json, os, html
os.chdir(os.path.dirname(os.path.abspath(__file__)))
lib = json.load(open('library.json'))
G = lib['garments']

def esc(s): return html.escape(str(s if s is not None else ''))

def tile(name, code, img, sub=''):
    im = f'<img src="{esc(img)}" loading="lazy">' if img else '<div class="noimg">no image</div>'
    sub = f'<div class="sub">{esc(sub)}</div>' if sub else ''
    code = f'<div class="c">{esc(code)}</div>' if code else ''
    return f'<div class="t">{im}<div class="n">{esc(name)}</div>{sub}{code}</div>'

def grid(tiles): return f'<div class="grid">{"".join(tiles)}</div>'

def section(title, body, n=None, open_=False):
    cnt = f' <span class="cnt">{n}</span>' if n is not None else ''
    return f'<details {"open" if open_ else ""}><summary>{esc(title)}{cnt}</summary>{body}</details>'

CATORDER = ['Style','Lapel','Back design','Pocket','Sleeve','Collar felt','Contrast','Lining','Bttn & Thread','Waist','Bottom','Monogram & Label','Other']

def garment_html(prod, g):
    out = []
    # 1) swatch catalogs (the colored grids)
    if g['swatchCatalogs']:
        parts = []
        for n, c in g['swatchCatalogs'].items():
            tiles = [tile(i.get('name') or i.get('color') or '', i.get('code'), i.get('image'),
                          ' · '.join(x for x in [i.get('color'), i.get('material'), i.get('size')] if x)) for i in c['items']]
            parts.append(section(f"{c['label']}", grid(tiles), c['count'], open_=(n in ('buttons','body_lining'))))
        out.append(f'<h2>Swatch catalogs — colored grids</h2>{"".join(parts)}')
    # 2) monogram & label
    if g['monogram']:
        m = g['monogram']; parts = []
        if m.get('fonts'):
            parts.append(section('Monogram fonts', grid([tile(f['name'], f['code'], f.get('image')) for f in m['fonts']]), len(m['fonts']), open_=True))
        if m.get('threadColors'):
            parts.append(section('Thread colors', grid([tile(t['name'], t['code'], t.get('image')) for t in m['threadColors']]), len(m['threadColors'])))
        if m.get('positions'):
            li = ''.join(f"<li><b>{esc(p['code'])}</b> — {esc(p['name'])}</li>" for p in m['positions'])
            parts.append(section('Embroidery positions', f'<ul class="list">{li}</ul>', len(m['positions'])))
        if m.get('wovenLabels'):
            cards = ''
            for lb in m['wovenLabels']:
                tms = ''.join(f"<li>{esc(t['name'])} @ {esc(t['position'])}{(' — '+esc(t['content'])) if t['content'] else ''}</li>" for t in lb['trademarks'])
                dflt = ' <span class="cnt">default</span>' if lb.get('isDefault') else ''
                cards += f'<div class="lbl"><div class="n">{esc(lb["label"])}{dflt}</div><ul class="list">{tms}</ul></div>'
            parts.append(section('Woven labels', f'<div class="lbls">{cards}</div>', len(m['wovenLabels'])))
        out.append(f'<h2>Monogram &amp; Label</h2>{"".join(parts)}')
    # 3) construction
    cons = g['construction']
    parts = []
    for cat in CATORDER + [c for c in cons if c not in CATORDER]:
        if cat not in cons: continue
        opts = cons[cat]
        tiles = [tile(o['name'], o['code'], o.get('image'), o.get('path')) for o in opts]
        parts.append(section(cat, grid(tiles), len(opts)))
    out.append(f'<h2>Construction options</h2>{"".join(parts)}')
    return ''.join(out)

tabs = ''.join(f'<button class="tab{" on" if i==0 else ""}" onclick="show(\'{esc(p)}\')">{esc(p)}</button>' for i, p in enumerate(G))
panels = ''.join(f'<div class="panel" id="p-{esc(p)}" style="{"" if i==0 else "display:none"}">{garment_html(p, g)}</div>' for i, (p, g) in enumerate(G.items()))

# counts for header
tot = sum(len(o) for g in G.values() for o in g['construction'].values())
sw = sum(c['count'] for g in G.values() for c in g['swatchCatalogs'].values())

HTML = f'''<!doctype html><meta charset="utf8"><title>GCC Customization Library — KuteTailor</title>
<style>
:root{{--gold:#b08d57;--ink:#2a2420;--bg:#faf8f5;--card:#fff;--line:#e7e0d5}}
*{{box-sizing:border-box}}body{{font:14px/1.4 -apple-system,Segoe UI,Arial;margin:0;background:var(--bg);color:var(--ink)}}
header{{background:linear-gradient(100deg,#2a2420,#4a3f33);color:#fff;padding:22px 28px}}
header h1{{margin:0;font-weight:600;letter-spacing:.3px}}header p{{margin:6px 0 0;color:#d9cdbb;font-size:13px}}
.tabs{{position:sticky;top:0;background:var(--bg);padding:12px 28px;border-bottom:1px solid var(--line);z-index:5}}
.tab{{font:600 14px inherit;background:#efe8dd;border:1px solid var(--line);color:var(--ink);padding:9px 22px;border-radius:22px;margin-right:8px;cursor:pointer}}
.tab.on{{background:var(--gold);color:#fff;border-color:var(--gold)}}
.panel{{padding:8px 28px 60px}}
h2{{margin:30px 0 6px;font-size:15px;text-transform:uppercase;letter-spacing:1px;color:var(--gold);border-bottom:2px solid var(--gold);padding-bottom:5px}}
details{{background:var(--card);border:1px solid var(--line);border-radius:9px;margin:10px 0;overflow:hidden}}
summary{{cursor:pointer;padding:12px 16px;font-weight:600;user-select:none;list-style:none}}
summary::-webkit-details-marker{{display:none}}summary:before{{content:'▸ ';color:var(--gold)}}
details[open] summary:before{{content:'▾ '}}
.cnt{{background:#efe8dd;color:#7a6a52;font-size:11px;font-weight:700;border-radius:10px;padding:1px 9px;margin-left:6px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:12px;padding:6px 16px 18px}}
.t{{background:#fbf9f6;border:1px solid var(--line);border-radius:8px;padding:8px;text-align:center;font-size:12px}}
.t img{{width:100%;height:110px;object-fit:contain;background:#fff;border-radius:5px;border:1px solid #f0ebe2}}
.noimg{{height:110px;display:flex;align-items:center;justify-content:center;color:#bcae98;background:#fff;border-radius:5px;font-size:11px}}
.t .n{{margin-top:6px;min-height:28px}}.t .sub{{color:#9a8b74;font-size:10px}}.t .c{{color:var(--gold);font-weight:700;font-size:11px;margin-top:2px}}
.list{{margin:4px 16px 16px;columns:2;font-size:12px;color:#4a4034}}.list li{{break-inside:avoid;margin:2px 0}}
.lbls{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;padding:6px 16px 16px}}
.lbl{{background:#fbf9f6;border:1px solid var(--line);border-radius:8px;padding:10px}}.lbl .n{{font-weight:700;margin-bottom:4px}}
.lbl .list{{columns:1;margin:0}}
</style>
<header><h1>Gage Court Clothiers — Customization Library</h1>
<p>Live from KuteTailor (2pc Suit · fabric DBU133A). {tot} construction options · {sw} accessory swatches · full monogram &amp; label. Organized by garment. Codes = order codes.</p></header>
<div class="tabs">{tabs}</div>
{panels}
<script>function show(p){{document.querySelectorAll('.panel').forEach(x=>x.style.display='none');document.getElementById('p-'+p).style.display='';document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('on',t.textContent===p));}}</script>
'''
open('library.html', 'w').write(HTML)
print('wrote library.html  (', len(HTML)//1024, 'KB )')
print('open:', os.path.abspath('library.html'))
