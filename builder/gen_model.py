#!/usr/bin/env python3
"""Generate a house-model render via the Gemini API at 2K.

The web UI caps downloads at 896x1200. The API's generationConfig.imageConfig.imageSize="2K"
is what produces the 1792x2400 assets — that setting is the whole reason for using the API.

    python3 gen_model.py <out_name> <prompt.txt> [ref1.png ref2.png ...]

Writes renders_v2/<out_name>.png, then runs check_render.py on it.
Reference images hold the model's identity: always pass the approved hero.
"""
import base64, json, os, sys, time, urllib.request, subprocess

ROOT = "/Users/runiwillner/Desktop/GCC_House_Model"
KEYF = "/Users/runiwillner/Desktop/GCC_Fabric_Handoff/keys/gemini_key.txt"
MODEL = "gemini-3-pro-image"
OUTDIR = f"{ROOT}/renders_v2"
ATTEMPTS = 3


def b64(p):
    return base64.b64encode(open(p, "rb").read()).decode()


def generate(prompt, refs, out_path):
    key = open(KEYF).read().strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key=" + key
    parts = [{"text": prompt}] + [
        {"inlineData": {"mimeType": "image/png", "data": b64(r)}} for r in refs
    ]
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"imageConfig": {"aspectRatio": "3:4", "imageSize": "2K"}},
    }
    data = json.dumps(body).encode()
    for a in range(1, ATTEMPTS + 1):
        try:
            req = urllib.request.Request(url, data=data,
                                         headers={"Content-Type": "application/json"})
            d = json.loads(urllib.request.urlopen(req, timeout=420).read())
            imgs = [p for p in d["candidates"][0]["content"]["parts"] if "inlineData" in p]
            if not imgs:
                txt = " ".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
                raise RuntimeError(f"no image returned. model said: {txt[:200]}")
            open(out_path, "wb").write(base64.b64decode(imgs[0]["inlineData"]["data"]))
            return True
        except Exception as e:
            # never surface the URL — it carries the key
            print(f"  attempt {a}/{ATTEMPTS} failed: {str(e)[:160]}")
            if a < ATTEMPTS:
                time.sleep(5)
    return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(2)
    name, prompt_file = sys.argv[1], sys.argv[2]
    refs = sys.argv[3:]
    for r in refs:
        if not os.path.exists(r):
            print(f"missing reference: {r}"); sys.exit(2)
    os.makedirs(OUTDIR, exist_ok=True)
    out = f"{OUTDIR}/{name}.png"
    prompt = open(prompt_file).read()
    print(f"generating {name}  (2K, 3:4, {len(refs)} reference image(s))")
    t0 = time.time()
    if not generate(prompt, refs, out):
        print("FAILED"); sys.exit(1)
    from PIL import Image
    print(f"  wrote {out}  {Image.open(out).size}  in {time.time()-t0:.0f}s\n")
    subprocess.run([sys.executable, f"{ROOT}/builder/check_render.py", out])
