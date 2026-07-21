#!/usr/bin/env python3
"""Gage Court — KuteTailor DRAFT-order placer for the suit configurator.

Takes a saveOrder body (the configurator's "Copy order JSON" output) and:
  --dry (DEFAULT)  validate + print the exact request; SEND NOTHING
  --send           POST /order/saveOrder (submit is FORCED false = DRAFT unless --submit)
  --status NO      GET /order/status/{orderNo}
  --cancel NO      POST /order/cancelOrder/{orderNo}  (clean up a test draft)

Safety: never submits a production order. --send always forces submit:false unless
you pass --submit AND --i-understand. A draft is a saved, editable, cancellable record.

Usage:
  python3 kt_place_draft.py payload.json            # dry-run (default)
  python3 kt_place_draft.py payload.json --send     # save as DRAFT
  python3 kt_place_draft.py --status GCNJ12607099
  python3 kt_place_draft.py --cancel GCNJ12607099
"""
import os, sys, json, ssl, urllib.request, urllib.parse, argparse

BASE = "https://platform.kutetailor.com/api"
# Credentials live OUTSIDE the repo — never inline them here. Same pattern as
# builder/gen_model.py. File is chmod 600 and the keys/ dir is gitignored.
CREDS_FILE = os.path.expanduser("~/Desktop/GCC_Fabric_Handoff/keys/kutetailor_creds.json")
try:
    CREDS = json.load(open(CREDS_FILE))
except FileNotFoundError:
    sys.exit(f"missing credentials file: {CREDS_FILE}")
_ctx = ssl.create_default_context(); _ctx.check_hostname = False; _ctx.verify_mode = ssl.CERT_NONE

# minimal placeholder customer for a DRAFT (GCC completes real customer + measurements at fitting)
TEST_CUSTOMER = {"nickname": "Configurator Draft", "firstname": "TEST", "lastname": "DRAFT",
                 "gender": "1002", "height": 178, "heightUnit": 1019, "weight": 80, "weightUnit": 1017}

def _req(path, tok=None, data=None, form=False, method=None):
    url = BASE + path
    headers = {'Accept-Language': 'en_US', 'Accept': 'application/json'}
    body = None
    if form:
        body = urllib.parse.urlencode(data).encode(); headers['Content-Type'] = 'application/x-www-form-urlencoded'
    elif data is not None:
        body = json.dumps(data).encode(); headers['Content-Type'] = 'application/json'
    if tok: headers['Authorization'] = 'bearer ' + tok
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, context=_ctx, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try: return {"_httpError": e.code, **json.loads(raw)}
        except Exception: return {"_httpError": e.code, "_raw": raw[:800]}

def auth():
    return _req("/token/oauth/token", data=CREDS, form=True)['data']['access_token']

# ---- validation (offline, against the authoritative code reference) ----
def validate(body, ref):
    errs, warns = [], []
    if body.get('submit') is True: warns.append("submit=true → PRODUCTION order (not a draft)")
    cat = body.get('category'); want = {'T': ['MXF','MXK'], 'S': ['MXF','MXK','MMJ']}
    if cat not in want: errs.append(f"top-level category '{cat}' not T/S")
    dets = body.get('orderDetails', [])
    have = [d.get('categoryCode') for d in dets]
    if cat in want and have != want[cat]:
        errs.append(f"garments {have} != expected {want[cat]} for category {cat}")
    if not body.get('fabric'): errs.append("missing fabric code")
    LINER = {'MXF': ('000A','000B','00C1','00D1','00C3'), 'MMJ': ('4714','423M','423U'), 'MXK': None}
    for d in dets:
        cc = d.get('categoryCode'); codes = [c.split(':')[0] for c in (d.get('crafts') or '').split(',') if c]
        if not codes: errs.append(f"{cc}: empty crafts")
        req_liner = LINER.get(cc)
        if req_liner and not any(c in req_liner for c in codes):
            warns.append(f"{cc}: no liner-type process ({'/'.join(req_liner)}) in crafts")
        gref = {'MXF': ref['jacket'], 'MXK': ref['pants'], 'MMJ': ref['vest']}.get(cc, {})
        unknown = [c for c in codes if c not in gref.get('ec2desc', {})]
        if unknown: warns.append(f"{cc}: codes not in EXCEL ref: {unknown}")
    return errs, warns

def decode(body, ref):
    m = {'MXF': ref['jacket'], 'MXK': ref['pants'], 'MMJ': ref['vest']}
    for d in body.get('orderDetails', []):
        cc = d['categoryCode']; gref = m.get(cc, {}).get('ec2desc', {})
        print(f"\n  [{cc}]  {'Jacket' if cc=='MXF' else 'Pants' if cc=='MXK' else 'Vest'}")
        for tok in (d.get('crafts') or '').split(','):
            code, _, content = tok.partition(':')
            print(f"      {code:8}{('· '+content):20} {gref.get(code, '??? unknown')}" if content
                  else f"      {code:8}{'':20} {gref.get(code, '??? unknown')}")
        for e in d.get('orderEmbs', []):
            print(f"      EMB pos={e.get('embPositionCode')} font={e.get('fontCode')} color={e.get('colorCode')} '{e.get('content')}'")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('payload', nargs='?')
    ap.add_argument('--send', action='store_true')
    ap.add_argument('--submit', action='store_true'); ap.add_argument('--i-understand', action='store_true')
    ap.add_argument('--status'); ap.add_argument('--cancel')
    ap.add_argument('--ref', default='/Users/runiwillner/Desktop/GCC_House_Model/config/kt_order_codes.json')
    a = ap.parse_args()
    ref = json.load(open(a.ref))

    if a.status:
        print(json.dumps(_req(f"/order/status/{a.status}", tok=auth()), indent=1, ensure_ascii=False)); return
    if a.cancel:
        # a submit:false order lands in the CART (Stay Payments/10039) — void it via deleteMoreCar, not cancelOrder
        tok = auth(); oid = None
        for pg in range(1, 6):
            d = _req(f"/order/order/orden/myCartList?pageNum={pg}&pageSize=100", tok).get('data', {})
            recs = d.get('records', []) if isinstance(d, dict) else []
            for r in recs:
                if r.get('ordenNo') == a.cancel: oid = r.get('id'); break
            if oid or len(recs) < 100: break
        if not oid: print(f"{a.cancel} not found in cart (already voided or submitted?)"); return
        print(f"voiding {a.cancel} (cart id {oid}) ...")
        print(json.dumps(_req(f"/order/order/orden/deleteMoreCar?orderIds={oid}", tok, method='DELETE'), ensure_ascii=False)); return

    body = json.load(open(a.payload))
    if not body.get('customer'): body['customer'] = TEST_CUSTOMER          # draft needs a customer stub
    if not body.get('customerNo'): body['customerNo'] = 'CFG-DRAFT-TEST'
    force_draft = not (a.submit and a.__dict__['i_understand'])
    if force_draft: body['submit'] = False

    errs, warns = validate(body, ref)
    print("=== DECODED CRAFTS ==="); decode(body, ref)
    print("\n=== VALIDATION ===")
    for e in errs: print("  ERROR:", e)
    for w in warns: print("  warn :", w)
    print("  OK" if not errs else "  ^ fix errors before sending")
    print(f"\n=== REQUEST ===  POST {BASE}/order/saveOrder   submit={body['submit']} (draft={body['submit'] is False})")
    print(json.dumps(body, indent=1, ensure_ascii=False))

    if not a.send:
        print("\n[dry-run] nothing sent. Re-run with --send to save this as a DRAFT."); return
    if errs:
        print("\n[aborted] validation errors present."); return
    print("\n>>> SENDING saveOrder (draft) ...")
    resp = _req("/order/saveOrder", tok=auth(), data=body)
    print(json.dumps(resp, indent=1, ensure_ascii=False))

if __name__ == '__main__':
    main()
