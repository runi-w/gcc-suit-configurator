#!/usr/bin/env python3
"""Assemble the KuteTailor customization LIBRARY, organized BY GARMENT.
Merges: craft construction tree (kt_craft_full.json) + accessory swatch catalogs
(kt_aided_catalogs.json) + monogram/label (kt_monogram_options.json).
Outputs library.json (manifest) + library.html (visual browser). Resolves local images.
"""
import json, os, glob
CFG = os.path.dirname(os.path.abspath(__file__))
os.chdir(CFG)
IMGBASE = 'https://aws-static-webp.kutetailor.com/comm'

craft   = json.load(open('kt_craft_full.json'))
aided   = json.load(open('kt_aided_catalogs.json'))
mono    = json.load(open('kt_monogram_options.json'))

# ---- index every local image by basename (craft) + by (catalog,code) ----
craft_imgs = {os.path.basename(p): p for p in glob.glob('img/*.*')}
def craft_local(url):
    if not url: return None
    b = os.path.basename(url.split('?')[0])
    return craft_imgs.get(b)
def find_local(*globs):
    for g in globs:
        m = glob.glob(g)
        if m: return m[0]
    return None

TYPE_NAME = {'3':'buttons','4':'collar_felt','6':'tuxedo_satin','7':'lapel_buttonhole_thread',
             '8':'zipper','37':'body_lining','2019072515':'button_spacing','2019072727':'artistic_lining'}

# ---- 1) craft construction options, grouped by garment -> top category ----
garments = {}
for r in craft:
    prod = r.get('product') or 'Other'
    parts = r['path'].split(' > ')
    if len(parts) < 2:      # the garment root itself
        continue
    cat = parts[1]
    if not r.get('ecode'):  # keep only selectable options (have an order code)
        continue
    g = garments.setdefault(prod, {'construction': {}, 'swatchCatalogs': {}, 'monogram': {}})
    g['construction'].setdefault(cat, []).append({
        'code': r['ecode'], 'name': r['en'],
        'path': ' > '.join(parts[2:]) if len(parts) > 2 else '',
        'image': craft_local(r.get('image')),
    })

# ---- 2) accessory swatch catalogs, attached to garments that use them ----
for t, c in aided.get('catalogs', {}).items():
    if not c.get('total'): continue
    name = TYPE_NAME.get(t, 'type_' + t)
    items = []
    for it in c['items']:
        code = it.get('code')
        loc = find_local(f'img/swatches/{name}/{code}.*') if code else None
        items.append({'code': code, 'name': it.get('name'), 'color': it.get('color'),
                      'material': it.get('material'), 'size': it.get('size'),
                      'price': it.get('price'), 'image': loc})
    for prod in c.get('garments', ['Jacket']):
        garments.setdefault(prod, {'construction': {}, 'swatchCatalogs': {}, 'monogram': {}})
        garments[prod]['swatchCatalogs'][name] = {
            'label': name.replace('_', ' ').title(), 'count': len(items),
            'filterDims': c.get('filterDims', []), 'items': items}

# ---- 2b) FULL lining + button catalogs (node-pid dropdowns) — flat, no material sub-grouping ----
btn_full = json.load(open('kt_buttons_full.json'))
lin_full = json.load(open('kt_lining_full.json'))
def button_items():
    out = []
    for it in btn_full['items']:
        code = it.get('c')
        loc = find_local(f'img/swatches/buttons_full/{code}.*') if it.get('fn') else None
        out.append({'code': code, 'name': None, 'color': it.get('col') or None,
                    'material': None, 'size': None, 'price': None, 'image': loc})
    return out
def lining_items():
    out = []
    for it in lin_full['items']:
        code = it.get('code')
        loc = find_local(f'img/swatches/lining_full/{code}.*') if it.get('image') else None
        out.append({'code': code, 'name': None, 'color': it.get('color') or None,
                    'material': None, 'size': None, 'price': None, 'image': loc})
    return out
BI, LI = button_items(), lining_items()
for prod in ['Jacket', 'Pants']:
    g = garments.setdefault(prod, {'construction': {}, 'swatchCatalogs': {}, 'monogram': {}})
    # drop the tiny/material-typed lining+button sets; keep collar felt / satin / thread / zipper
    for k in ('buttons', 'body_lining', 'artistic_lining'):
        g['swatchCatalogs'].pop(k, None)
    sc = g['swatchCatalogs']
    # rebuild so Buttons + Lining come first
    g['swatchCatalogs'] = {
        'buttons': {'label': 'Buttons', 'count': len(BI), 'filterDims': [], 'items': BI},
        'lining':  {'label': 'Lining',  'count': len(LI), 'filterDims': [], 'items': LI},
        **sc,
    }

# ---- 3) monogram / label, per garment ----
def mono_local(g, ax, e, i):
    if not i: return None
    code = (e or 'x').replace('/', '-').replace(',', '_')
    return find_local(f"img/monogram/{g.lower()}/{ax.replace(' ','_')}/{code}.*")
for r in mono['mono']:
    prod = r['g']
    g = garments.setdefault(prod, {'construction': {}, 'swatchCatalogs': {}, 'monogram': {}})
    axis = {'Embroidery position':'positions','Font':'fonts','Color':'threadColors'}.get(r['ax'], r['ax'])
    g['monogram'].setdefault(axis, []).append({'code': r['e'], 'name': r['n'],
                                               'image': mono_local(prod, r['ax'], r['e'], r.get('i'))})
for lb in mono['labels']:
    prod = lb['garment']
    g = garments.setdefault(prod, {'construction': {}, 'swatchCatalogs': {}, 'monogram': {}})
    g['monogram'].setdefault('wovenLabels', []).append(lb)

lib = {'meta': {'source': 'KuteTailor quickOrder (2pc Suit / DBU133A / ARUAP)',
                'imageBase': IMGBASE, 'garments': list(garments.keys())},
       'garments': garments}
json.dump(lib, open('library.json', 'w'), indent=1, ensure_ascii=False)

# ---- summary ----
print("== LIBRARY by garment ==")
for prod, g in garments.items():
    print(f"\n{prod}:")
    print("  construction categories:")
    for cat, opts in sorted(g['construction'].items(), key=lambda x: -len(x[1])):
        imn = len([o for o in opts if o['image']])
        print(f"    {cat:22} {len(opts):3} options ({imn} imgs)")
    if g['swatchCatalogs']:
        print("  swatch catalogs:")
        for n, c in g['swatchCatalogs'].items():
            imn = len([i for i in c['items'] if i['image']])
            print(f"    {n:22} {c['count']:3} swatches ({imn} imgs)")
    if g['monogram']:
        print("  monogram:")
        for k, v in g['monogram'].items():
            print(f"    {k:22} {len(v):3}")
