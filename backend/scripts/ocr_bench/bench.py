import argparse
import json
import resource
import subprocess
import time
from pathlib import Path
import Levenshtein


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


_ocr = None


def paddle_text(img, lang):
    global _ocr
    if _ocr is None:
        from paddleocr import PaddleOCR

        try:
            _ocr = PaddleOCR(
                lang=lang,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                enable_mkldnn=False,
            )
        except TypeError:
            _ocr = PaddleOCR(lang=lang)
    res = _ocr.predict(str(img)) if hasattr(_ocr, "predict") else _ocr.ocr(str(img), cls=False)
    out = []

    def collect(x):
        if isinstance(x, dict):
            t = x.get("rec_texts")
            if t:
                out.extend(t)
            return
        if isinstance(x, (list, tuple)):
            if len(x) == 2 and isinstance(x[1], (list, tuple)) and x[1] and isinstance(x[1][0], str):
                out.append(x[1][0])
                return
            for y in x:
                collect(y)
            return
        if not isinstance(x, (str, bytes, int, float)) and hasattr(x, "__getitem__"):
            try:
                t = x["rec_texts"]
                if t:
                    out.extend(t)
            except Exception:
                pass

    collect(res)
    return " ".join(out)


def tess_text(img, lang):
    return subprocess.run(
        ["tesseract", str(img), "stdout", "-l", lang, "--psm", "6"], capture_output=True, text=True
    ).stdout


ap = argparse.ArgumentParser()
ap.add_argument("--engine", required=True, choices=["tesseract", "paddle"])
ap.add_argument("--lang", default="te")
ap.add_argument("--bundle", default="/tmp/ocr_bundle")
ap.add_argument("--out")
a = ap.parse_args()
B = Path(a.bundle)

rows = [json.loads(line) for line in (B / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
res = []
t0 = time.time()
for m in rows:
    s = time.time()
    pred = tess_text(B / m["image"], a.lang) if a.engine == "tesseract" else paddle_text(B / m["image"], a.lang)
    dt = time.time() - s
    p, r = norm(pred), norm(m["ref"])
    c, w = round(cer(p, r), 4), round(wer(p, r), 4)
    res.append({"id": m["id"], "cer": c, "wer": w, "sec": round(dt, 3)})
    print(f"{m['id'][:36]:36s} cer={c:.3f} wer={w:.3f} {dt:.2f}s")

cs = sorted(x["cer"] for x in res)
ws = sorted(x["wer"] for x in res)


def median(values):
    return values[len(values) // 2]


rss = max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
total = time.time() - t0
sup = {
    "engine": a.engine,
    "lang": a.lang,
    "bundle": str(B),
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
    Path(a.out).write_text(json.dumps({**sup, "rows": res}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", a.out)
