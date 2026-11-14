import argparse
import json
import resource
import time
from pathlib import Path
import pytesseract
from PIL import Image
from transformers import AutoModel, AutoTokenizer
import Levenshtein

B = Path("/tmp/ocr_bundle")


def norm(s):
    return " ".join(s.split())


def cer(p, r):
    return Levenshtein.distance(p, r) / len(r) if r else 0.0


def wer(p, r):
    ps, rs = p.split(), r.split()
    if not rs:
        return 0.0
    prev = list(range(len(rs) + 1))
    for i, pw in enumerate(ps, 1):
        cur = [i]
        for j, rw in enumerate(rs, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (pw != rw)))
        prev = cur
    return prev[-1] / len(rs)


def line_boxes(img):
    d = pytesseract.image_to_data(img, lang="tel", config="--psm 6", output_type=pytesseract.Output.DICT)
    groups = {}
    for i in range(len(d["text"])):
        if not d["text"][i].strip():
            continue
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        x, y, w, h = d["left"][i], d["top"][i], d["width"][i], d["height"][i]
        g = groups.setdefault(key, [10**9, 10**9, 0, 0])
        g[0] = min(g[0], x)
        g[1] = min(g[1], y)
        g[2] = max(g[2], x + w)
        g[3] = max(g[3], y + h)
    return [b for _, b in sorted(groups.items(), key=lambda kv: (kv[1][1], kv[1][0]))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--decode", default="ctc")
    a = ap.parse_args()
    model = AutoModel.from_pretrained("harsha-desaraju/telugu-ocr-model", trust_remote_code=True).eval()
    tok = AutoTokenizer.from_pretrained("harsha-desaraju/telugu-ocr-model", trust_remote_code=True)
    rows = [
        json.loads(line) for line in (B / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    res = []
    t0 = time.time()
    for m in rows:
        img = Image.open(B / m["image"]).convert("RGB")
        s = time.time()
        boxes = line_boxes(img)
        crops = [img.crop(tuple(b)) for b in boxes if b[2] > b[0] and b[3] > b[1]]
        texts = model.transcribe(crops, tok, decode=a.decode)
        pred = norm(" ".join(texts))
        dt = time.time() - s
        ref = norm(m["ref"])
        c, w = round(cer(pred, ref), 4), round(wer(pred, ref), 4)
        res.append({"id": m["id"], "cer": c, "wer": w, "sec": round(dt, 3), "lines": len(crops)})
        print(f"{m['id'][:36]:36s} cer={c:.3f} wer={w:.3f} lines={len(crops)} {dt:.2f}s")
    cs = sorted(x["cer"] for x in res)
    ws = sorted(x["wer"] for x in res)

    def median(values):
        return values[len(values) // 2]

    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    total = time.time() - t0
    sup = {
        "engine": "telugu-ocr-model",
        "decode": a.decode,
        "pages": len(res),
        "mean_cer": round(sum(cs) / len(cs), 4),
        "median_cer": round(median(cs), 4),
        "median_wer": round(median(ws), 4),
        "total_sec": round(total, 2),
        "sec_per_page": round(total / len(res), 3),
        "peak_rss_mb": round(rss / 1024, 1),
    }
    print("SUMMARY", json.dumps(sup))
    if a.out:
        Path(a.out).write_text(json.dumps({**sup, "rows": res}, ensure_ascii=False, indent=2))
        print("wrote", a.out)


if __name__ == "__main__":
    main()
