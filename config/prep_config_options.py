#!/usr/bin/env python3
"""Curate a sensible OPTION SET for the configurator v0 from the full catalog.
Picks common business options per axis (lapel, pockets, buttons, linings, monogram)
with real KuteTailor codes, English names, and existing local images. -> configurator_options.json"""
import json, os, glob, re
os.chdir(os.path.dirname(os.path.abspath(__file__)))

lib = json.load(open('library.json'))
JC = lib['garments']['Jacket']['construction']

def local_exists(*globs):
    for g in globs:
        m = glob.glob(g)
        if m: return m[0]
    return None

def pick_from_construction(cat, wants):
    """wants = list of (label, regex) -> pick first option whose name matches, that has a local image."""
    opts = JC.get(cat, [])
    out = []
    for label, rx in wants:
        for o in opts:
            nm = o.get('name') or ''
            if re.search(rx, nm, re.I) and o.get('image') and os.path.exists(o['image']):
                out.append({'label': label, 'code': o['code'], 'name': nm, 'image': o['image']})
                break
    return out

lapel = pick_from_construction('Lapel', [
    ('Notch', r'^notch$|notch lapel$'), ('Peak', r'^peak'), ('Shawl', r'shawl'),
    ('Semi-notch', r'semi.?notch'), ('Semi-peak', r'semi.?peak')])
chest = pick_from_construction('Pocket', [
    ('Welt', r'welt'), ('None', r'^no |^none'), ('Patch', r'patch'), ('Besom', r'besom')])
lower = pick_from_construction('Pocket', [
    ('Flap', r'flap'), ('Besom / jetted', r'besom|jetted'), ('Patch', r'patch'), ('Slanted', r'slant')])
vent = pick_from_construction('Back design', [
    ('Center vent', r'center|centre'), ('Side vents', r'side'), ('No vent', r'no vent|ventless')])

# curated buttons: spread of colours, must have image
btn_all = json.load(open('kt_buttons_full.json'))['items']
def btn_img(c): return local_exists(f'img/swatches/buttons_full/{c}.*')
want_btn = [('Black horn', 'KSZ257'), ('Dark navy', 'KB011'), ('Coffee horn', 'KSZ255'),
            ('Brown nut', 'KG108'), ('Grey', 'KB115'), ('Charcoal', 'KSZ256'),
            ('GCC signature', 'KYKARUA01'), ('GCC signature II', 'KYKARUA03')]
buttons = []
for label, code in want_btn:
    it = next((b for b in btn_all if b['c'] == code), None)
    img = btn_img(code)
    if it and img: buttons.append({'label': label, 'code': code, 'color': it.get('col') or '', 'image': img})
# top up from any coded+imaged buttons if short
if len(buttons) < 6:
    for b in btn_all:
        if len(buttons) >= 8: break
        img = btn_img(b['c'])
        if img and b['c'] not in [x['code'] for x in buttons]:
            buttons.append({'label': b.get('col') or b['c'], 'code': b['c'], 'color': b.get('col') or '', 'image': img})

# curated linings: spread of colours
lin_all = json.load(open('kt_lining_full.json'))['items']
def lin_img(c): return local_exists(f'img/swatches/lining_full/{c}.*')
by_color = {}
for it in lin_all:
    c = (it.get('color') or '').strip()
    img = lin_img(it['code'])
    if not img or not c: continue
    key = c.lower()
    if key not in by_color: by_color[key] = {'label': c, 'code': it['code'], 'color': c, 'image': img}
prefer = ['navy','blue','royal blue','black','grey','gray','burgundy','wine','red','green','purple','sky blue','silver','brown','teal','pink','orange']
linings = []
for p in prefer:
    if p in by_color: linings.append(by_color.pop(p))
for v in by_color.values():
    if len(linings) >= 12: break
    linings.append(v)
linings = linings[:12]

# monogram
mono = json.load(open('kt_monogram_options.json'))
colors = [m for m in mono['mono'] if m['g'] == 'Jacket' and m['ax'] == 'Color']
def mono_named(sub):
    # clean "3712#-Navy blue" -> "Navy blue"
    return re.sub(r'^[0-9A-Za-z]+#?-+', '', sub).strip().title()
want_thread = ['White','Black','Silvery grey','Navy blue','Dark blue','Dark grey','Wine Red','Gold','Silver','Dark green']
thread = []
for w in want_thread:
    it = next((c for c in colors if w.lower() in mono_named(c['n']).lower() or w.lower() in c['n'].lower()), None)
    if it: thread.append({'name': mono_named(it['n']), 'code': it['e']})
fonts = [{'name': re.sub(r'^RC\d+\s*', '', m['n']) or m['n'], 'code': m['e'],
          'image': local_exists('img/monogram/jacket/Font/'+(m['e'] or '').replace('/','-')+'.*')}
         for m in mono['mono'] if m['g'] == 'Jacket' and m['ax'] == 'Font']
positions = [{'name': m['n'], 'code': m['e']} for m in mono['mono']
             if m['g'] == 'Jacket' and m['ax'] == 'Embroidery position'][:5]

out = {'lapel': lapel, 'chestPocket': chest, 'lowerPocket': lower, 'vent': vent,
       'buttons': buttons, 'linings': linings,
       'monogram': {'thread': thread, 'fonts': fonts, 'positions': positions}}
json.dump(out, open('configurator_options.json', 'w'), indent=1, ensure_ascii=False)

for k, v in out.items():
    if k == 'monogram':
        print(f"{k}: thread {len(v['thread'])}, fonts {len(v['fonts'])}, positions {len(v['positions'])}")
    else:
        print(f"{k}: {len(v)}  -> {[x.get('label') or x.get('name') for x in v]}")
