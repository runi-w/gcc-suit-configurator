#!/usr/bin/env python3
"""Reskin the configurator UI to Suitsupply's custom-made pattern:
full-bleed photographic preview + bottom control dock (section tabs + swatch strip + selected label),
minimal warm-grey palette, clean grotesque type. Keeps all compositor + order-capture logic."""
src = open('build_configurator_v0.py').read()

# ---------- 1. CSS (everything between <style> and </style>) ----------
NEW_CSS = r"""
 :root{
  --bg:#efeeec;--stage:#e4e2de;--dock:#f7f6f4;--line:#dcd9d4;--line2:#c7c4bc;
  --ink:#1b1b19;--soft:#76746e;--faint:#a3a19a;--on:#141412;--chip:#fff;
  --sans:system-ui,-apple-system,"Helvetica Neue","Segoe UI",Arial,sans-serif;
  /* aliases kept so the make-ticket dialog styles work unchanged */
  --ground:#efeeec;--panel:#fff;--hair:#dcd9d4;--hair2:#c7c4bc;--brassd:#76746e;}
 *{box-sizing:border-box}
 html,body{margin:0}
 body{background:var(--bg);color:var(--ink);font-family:var(--sans);font-weight:300;line-height:1.4;-webkit-font-smoothing:antialiased}
 .app{display:flex;flex-direction:column;height:100vh;min-height:560px;max-height:1040px;background:var(--bg)}
 .topbar{flex:none;position:relative;display:flex;align-items:center;justify-content:space-between;padding:14px 20px}
 .tot b{font-weight:600;font-size:16px;letter-spacing:-.01em}
 .tot small{display:block;color:var(--soft);font-size:11.5px;margin-top:1px}
 .brand{position:absolute;left:50%;transform:translateX(-50%);font-weight:600;letter-spacing:.24em;font-size:14px;white-space:nowrap}
 .finish{border:none;background:var(--on);color:#fff;border-radius:999px;padding:11px 22px;font:500 13.5px var(--sans);cursor:pointer;white-space:nowrap}
 .finish[disabled]{opacity:.55;cursor:default}
 .stage{flex:1;min-height:0;position:relative;display:flex;align-items:center;justify-content:center;background:var(--stage);overflow:hidden}
 canvas.hero{display:block}
 .approx{position:absolute;left:16px;bottom:14px;max-width:44%;font-size:11px;color:var(--soft);line-height:1.35}
 .spec-link{position:absolute;right:14px;bottom:12px;font:400 11px var(--sans);color:var(--soft);background:transparent;border:none;cursor:pointer;text-decoration:underline;text-underline-offset:2px}
 .dock{flex:none;background:var(--dock);border-top:1px solid var(--line);padding:9px 14px 15px}
 .tabs{display:flex;gap:2px;justify-content:center;overflow-x:auto;scrollbar-width:none}
 .tabs::-webkit-scrollbar{display:none}
 .tab{flex:none;border:none;background:transparent;color:var(--soft);font:400 14px var(--sans);padding:7px 15px;border-radius:999px;cursor:pointer;white-space:nowrap;transition:.12s}
 .tab:hover{color:var(--ink)}
 .tab.on{background:#e6e4df;color:var(--ink);font-weight:500}
 .strip{display:flex;gap:10px;overflow-x:auto;padding:15px 2px 7px;align-items:flex-start;justify-content:center;scrollbar-width:none;min-height:86px}
 .strip::-webkit-scrollbar{display:none}
 .strip.left{justify-content:flex-start}
 .strip.wrap{flex-wrap:wrap;overflow:visible;gap:14px 10px}
 .chip{flex:none;width:60px;height:60px;border-radius:12px;border:1px solid var(--line2);background:var(--chip);background-size:cover;background-position:center;cursor:pointer;padding:0;transition:.12s}
 .chip.round{border-radius:50%}
 .chip:hover{transform:translateY(-1px)}
 .chip.on{box-shadow:0 0 0 2px var(--ink);border-color:var(--ink)}
 .tile{flex:none;width:72px;border:none;background:transparent;padding:0;cursor:pointer;text-align:center;color:var(--soft);font:400 10.5px var(--sans);line-height:1.2}
 .tile img{width:72px;height:52px;object-fit:contain;background:#fff;border:1px solid var(--line2);border-radius:9px;margin-bottom:4px;transition:.12s}
 .tile.on{color:var(--ink)}.tile.on img{border-color:var(--ink);box-shadow:0 0 0 1px var(--ink)}
 .pill{flex:none;border:1px solid var(--line2);background:#fff;color:var(--soft);border-radius:999px;padding:9px 15px;font:400 13px var(--sans);cursor:pointer;white-space:nowrap;transition:.12s}
 .pill:hover{border-color:var(--ink);color:var(--ink)}
 .pill.on{background:var(--ink);color:#fff;border-color:var(--ink)}
 .subrow{display:flex;flex-direction:column;align-items:center;gap:6px}
 .subrow .lbl{font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint)}
 .subrow .r{display:flex;gap:8px}
 .mono-row{display:flex;gap:10px;align-items:center;flex-wrap:wrap;justify-content:center;padding:4px 0}
 .mono-row input{font:inherit;font-size:13px;padding:9px 11px;border:1px solid var(--line2);border-radius:8px;background:#fff;width:118px;color:var(--ink)}
 .toggle{display:inline-flex;align-items:center;gap:9px;cursor:pointer;font-size:13px;color:var(--ink)}
 .toggle .sw2{width:38px;height:22px;border-radius:999px;background:var(--line2);position:relative;flex:none;transition:.15s}
 .toggle.on .sw2{background:var(--ink)}
 .toggle .sw2::after{content:"";position:absolute;top:2.5px;left:2.5px;width:17px;height:17px;border-radius:50%;background:#fff;transition:.15s}
 .toggle.on .sw2::after{left:18.5px}
 .sel{text-align:center;padding-top:3px;min-height:20px}
 .sel b{font-weight:500;font-size:14.5px}
 .sel span{color:var(--soft);font-size:13px;margin-left:7px}
 /* make-ticket dialog */
 dialog{border:none;border-radius:14px;max-width:560px;width:92%;padding:0;background:#fff;color:var(--ink)}
 dialog::backdrop{background:rgba(0,0,0,.45)}
 .dlg{padding:20px 22px}.dlg h3{font-weight:600;margin:0 0 4px;font-size:19px}
 .dlg .sub{color:var(--soft);font-size:13px;margin:0 0 14px}
 .codes{background:var(--bg);border:1px solid var(--line);border-radius:9px;padding:12px;font-size:12px;max-height:46vh;overflow:auto}
 .codes .r{display:flex;justify-content:space-between;padding:3px 0;border-bottom:1px solid var(--line)}
 .codes .r:last-child{border:none}.codes .c{font-family:ui-monospace,monospace;color:var(--soft)}
 .dlg .x{margin-top:14px;display:flex;gap:8px}.dlg button{font:500 13px var(--sans);border-radius:999px;padding:9px 16px;cursor:pointer;border:1px solid var(--line2);background:#fff;color:var(--ink)}
 .dlg button.p{background:var(--on);color:#fff;border-color:var(--on)}
 .codes .sec{margin-bottom:12px}
 .codes .sech{font:600 11px var(--sans);letter-spacing:.06em;text-transform:uppercase;color:var(--soft);padding:2px 0 5px;border-bottom:1px solid var(--line2);margin-bottom:3px;display:flex;justify-content:space-between}
 .codes .sech .pc{color:var(--faint);font-weight:400;letter-spacing:0;text-transform:none}
 .codes .secn{font-size:11px;color:var(--soft);margin:1px 0 5px;line-height:1.4}
 .codes .sec.default{opacity:.8}
 .codes .r.tot{border-top:2px solid var(--line2);margin-top:9px;padding-top:9px;font-size:13px;font-weight:600}
"""
i0 = src.index('<style>') + len('<style>')
i1 = src.index('</style>')
src = src[:i0] + NEW_CSS + src[i1:]

# ---------- 2. Markup (between </style> and <dialog id="dlg">) ----------
NEW_MARKUP = r"""
<div class="app">
 <div class="topbar">
  <div class="tot"><b id="totVal">$575</b><small id="totSub">Made to measure &middot; fitted at your appointment</small></div>
  <div class="brand">GAGE COURT</div>
  <button class="finish" id="addCart">Add to cart</button>
 </div>
 <div class="stage">
  <canvas class="hero" id="hero"></canvas>
  <div class="approx" id="approx"></div>
  <button class="spec-link" id="specLink">Review spec</button>
 </div>
 <div class="dock">
  <div class="tabs" id="tabs"></div>
  <div class="strip" id="strip"></div>
  <div class="sel"><b id="selName">&mdash;</b><span id="selMeta"></span></div>
 </div>
</div>
"""
j0 = src.index('</style>') + len('</style>')
j1 = src.index('<dialog id="dlg">')
src = src[:j0] + NEW_MARKUP + src[j1:]

# ---------- 3. render() tail ----------
src = src.replace(
"""  document.getElementById('tagName').textContent=f.name;
  document.getElementById('tagSub').textContent=f.code+' · '+state.style+' · '+state.lapel+' lapel';
  document.getElementById('approx').textContent=approx?('Preview shown with the nearest rendered lapel — your suit is made with the '+state.lapel+' lapel.'):'';
  updateSummary();}""",
"""  const ap=document.getElementById('approx');if(ap)ap.textContent=approx?('Preview shows the nearest rendered lapel — made with your '+state.lapel+' lapel.'):'';
  updateChrome();}""")

# ---------- 4. Dock UI (from '// ---- UI ----' to before 'function nameOf(') ----------
NEW_DOCK = r"""// ---- UI: Suitsupply-style dock (section tabs + swatch strip + selected label) ----
const SECTIONS=[{key:'cloth',label:'Cloth'},{key:'style',label:'Style'},{key:'lapel',label:'Lapel'},
  {key:'pockets',label:'Pockets'},{key:'buttons',label:'Buttons'},{key:'lining',label:'Lining'},{key:'mono',label:'Monogram'}];
let activeSection='cloth';
function chip(img,on,cb,round){const b=document.createElement('button');b.className='chip'+(round?' round':'')+(on?' on':'');if(img)b.style.backgroundImage='url("'+img+'")';b.onclick=cb;return b;}
function tile(img,label,on,cb){const b=document.createElement('button');b.className='tile'+(on?' on':'');b.innerHTML=(img?'<img src="'+img+'">':'')+'<span>'+label+'</span>';b.onclick=cb;return b;}
function pill(label,on,cb){const b=document.createElement('button');b.className='pill'+(on?' on':'');b.textContent=label;b.onclick=cb;return b;}
function subrow(label,nodes){const w=document.createElement('div');w.className='subrow';const l=document.createElement('div');l.className='lbl';l.textContent=label;const r=document.createElement('div');r.className='r';nodes.forEach(n=>r.appendChild(n));w.appendChild(l);w.appendChild(r);return w;}
function pick(setter){setter();render();renderStrip();}
function renderStrip(){const s=document.getElementById('strip');s.innerHTML='';s.className='strip';
  if(activeSection==='cloth'){s.classList.add('left');FABRICS.forEach(f=>s.appendChild(chip(f.tile||f.img,state.fabric===f.code,()=>pick(()=>state.fabric=f.code))));}
  else if(activeSection==='style'){STYLES.forEach(st=>s.appendChild(pill(st.label,state.style===st.label,()=>pick(()=>state.style=st.label))));}
  else if(activeSection==='lapel'){OPTS.lapel.forEach(l=>s.appendChild(tile(l.img,l.label,state.lapel===l.label,()=>pick(()=>state.lapel=l.label))));}
  else if(activeSection==='pockets'){s.classList.add('wrap');
    s.appendChild(subrow('Chest',OPTS.chestPocket.map(o=>tile(o.img,o.label,state.chest===o.code,()=>pick(()=>state.chest=o.code)))));
    s.appendChild(subrow('Lower',OPTS.lowerPocket.map(o=>tile(o.img,o.label,state.lower===o.code,()=>pick(()=>state.lower=o.code)))));
    s.appendChild(subrow('Vents',OPTS.vent.map(o=>pill(o.label,state.vent===o.code,()=>pick(()=>state.vent=o.code)))));}
  else if(activeSection==='buttons'){OPTS.buttons.forEach(o=>s.appendChild(chip(o.img||o.tile,state.button===o.code,()=>pick(()=>state.button=o.code),true)));}
  else if(activeSection==='lining'){OPTS.linings.forEach(o=>s.appendChild(chip(o.img||o.tile,state.lining===o.code,()=>pick(()=>state.lining=o.code),true)));}
  else if(activeSection==='mono'){renderMono(s);}
  updateChrome();}
function renderMono(s){const row=document.createElement('div');row.className='mono-row';
  const tog=document.createElement('div');tog.className='toggle'+(state.mono.on?' on':'');tog.innerHTML='<span class="sw2"></span><span>Add a monogram</span>';
  tog.onclick=()=>pick(()=>state.mono.on=!state.mono.on);row.appendChild(tog);
  if(state.mono.on){const inp=document.createElement('input');inp.type='text';inp.maxLength=4;inp.placeholder='Initials';inp.value=state.mono.initials||'';
    inp.oninput=e=>{state.mono.initials=e.target.value;updateChrome();};row.appendChild(inp);
    OPTS.monogram.thread.slice(0,8).forEach(t=>row.appendChild(pill(t.name,state.mono.thread===t.code,()=>pick(()=>state.mono.thread=t.code))));}
  s.appendChild(row);}
function renderTabs(){const t=document.getElementById('tabs');t.innerHTML='';SECTIONS.forEach(sec=>{const b=document.createElement('button');b.className='tab'+(sec.key===activeSection?' on':'');b.textContent=sec.label;b.onclick=()=>{activeSection=sec.key;renderTabs();renderStrip();};t.appendChild(b);});}
function selInfo(){const f=FABRICS.find(x=>x.code===state.fabric)||{};
  if(activeSection==='cloth')return [f.name||'','$'+price().toLocaleString()];
  if(activeSection==='style')return [state.style,''];
  if(activeSection==='lapel')return [state.lapel+' lapel',''];
  if(activeSection==='pockets')return [nameOf(OPTS.chestPocket,state.chest)+' chest · '+nameOf(OPTS.lowerPocket,state.lower)+' lower',nameOf(OPTS.vent,state.vent)+' vent'];
  if(activeSection==='buttons')return [nameOf(OPTS.buttons,state.button)+' buttons',''];
  if(activeSection==='lining')return [nameOf(OPTS.linings,state.lining)+' lining',''];
  if(activeSection==='mono')return [state.mono.on?(state.mono.initials||'Monogram'):'No monogram',''];
  return ['',''];}
function updateChrome(){const a=selInfo();const sn=document.getElementById('selName'),sm=document.getElementById('selMeta'),tv=document.getElementById('totVal');
  if(sn)sn.textContent=a[0];if(sm)sm.textContent=a[1];if(tv)tv.textContent='$'+price().toLocaleString();}
function buildDock(){renderTabs();renderStrip();
  const ac=document.getElementById('addCart');if(ac)ac.onclick=addToCart;
  const sl=document.getElementById('specLink');if(sl)sl.onclick=openTicket;}
"""
a0 = src.index('// ---- UI ----')
a1 = src.index('function nameOf(')
src = src[:a0] + NEW_DOCK + src[a1:]

# ---------- 5. Remove obsolete updateSummary (between its def and openTicket) ----------
b0 = src.index('function updateSummary(){')
b1 = src.index('function openTicket(')
src = src[:b0] + src[b1:]

# ---------- 6. sizeHero -> fit the flex stage; init buildPanelUI->buildDock ----------
old_sh = src[src.index('function sizeHero(){'):src.index('async function init(){')]
src = src.replace(old_sh,
"""function sizeHero(){const st=hero.parentElement;if(!st||!W)return;const sw=Math.max(40,st.clientWidth-6),sh=Math.max(40,st.clientHeight-6),AR=W/H;
  let h=sh,w=h*AR;if(w>sw){w=sw;h=w/AR;}hero.style.width=Math.round(w)+'px';hero.style.height=Math.round(h)+'px';}
""")
src = src.replace('buildPanelUI();render();}', 'buildDock();render();sizeHero();}')

open('build_configurator_v0.py','w').write(src)
print("patched UI -> Suitsupply dock layout")
