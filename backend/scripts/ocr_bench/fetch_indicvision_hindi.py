import json
import urllib.request
from pathlib import Path

OUT = Path("/tmp/hin_bundle")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://datasets-server.huggingface.co/rows?dataset=krutrim-ai-labs/IndicVisionBench&config=ocr&split=test"


def get(u):
    req = urllib.request.Request(u, headers={"User-Agent": "ocr-eval"})
    return json.load(urllib.request.urlopen(req, timeout=60))


rows = []
offset = 0
while True:
    d = get(f"{BASE}&offset={offset}&length=100")
    batch = d.get("rows", [])
    if not batch:
        break
    for item in batch:
        row = item["row"]
        lang = str(row.get("language", "")).strip().lower()
        if lang.startswith("hindi") or lang == "hi":
            rows.append(row)
    offset += 100
    if offset >= d.get("num_rows_total", 0):
        break

print("hindi rows:", len(rows))
sel = rows[:24]
manifest = []
for i, r in enumerate(sel):
    img = r["image"]
    url = img["src"] if isinstance(img, dict) else img
    p = OUT / f"hin_{i:03d}.png"
    if not p.exists():
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "ocr-eval"}), timeout=90).read()
            p.write_bytes(data)
        except Exception as e:  # noqa: BLE001
            print("fail", i, e)
            continue
    manifest.append({"id": f"hin_{i:03d}", "image": p.name, "ref": " ".join(str(r.get("text", "")).split()),
                     "lang": r.get("language"), "url": r.get("page_url")})
(OUT / "manifest.jsonl").write_text("".join(json.dumps(m, ensure_ascii=False) + "\n" for m in manifest), encoding="utf-8")
print("wrote", len(manifest))