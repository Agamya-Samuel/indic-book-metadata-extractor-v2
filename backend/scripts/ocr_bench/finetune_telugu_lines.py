#!/usr/bin/env python3
"""Fine-tune the Telugu line model on aligned, verified book lines.

The model keeps its 81M-parameter architecture, so production inference stays
CPU-cheap. Training uses the decoder CE loss plus the encoder CTC loss
(``ctc_loss_weight``), with a book-level held-out split from the corpus builder.

Usage:
    /home/agamya/.cache/ocr-ft-venv/bin/python \
      backend/scripts/ocr_bench/finetune_telugu_lines.py \
      --data /home/agamya/.cache/telugu-ocr-ft/data \
      --out /home/agamya/.cache/telugu-ocr-ft/model
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import statistics
import sys
import time
from pathlib import Path

import Levenshtein
import torch
from PIL import Image, ImageEnhance, ImageFilter
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer

MODEL = "harsha-desaraju/telugu-ocr-model"


def norm(text: str) -> str:
    return " ".join(text.split())


def cer(pred: str, ref: str) -> float:
    return Levenshtein.distance(pred, ref) / len(ref) if ref else 0.0


class LineDataset(Dataset):
    def __init__(self, rows, data_dir: Path, tokenizer, train: bool, vocab_limit: int = 2048):
        self.rows = rows
        self.data_dir = data_dir
        self.tokenizer = tokenizer
        self.train = train
        self.vocab_limit = vocab_limit
        self.unk_id = tokenizer.unk_token_id

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        image = Image.open(self.data_dir / row["image"]).convert("RGB")
        if self.train:
            if random.random() < 0.5:
                image = ImageEnhance.Contrast(image).enhance(random.uniform(0.8, 1.25))
            if random.random() < 0.35:
                image = ImageEnhance.Brightness(image).enhance(random.uniform(0.85, 1.15))
            if random.random() < 0.25:
                image = image.filter(ImageFilter.GaussianBlur(random.uniform(0.2, 0.8)))
            if random.random() < 0.3:
                image = image.rotate(random.uniform(-1.2, 1.2), expand=True, fillcolor=(255, 255, 255))
        label = norm(row["label"])
        ids = [
            token_id if token_id < self.vocab_limit else self.unk_id
            for token_id in self.tokenizer.encode(label, add_special_tokens=False)
        ]
        input_ids = [self.tokenizer.bos_token_id, *ids, self.tokenizer.eos_token_id]
        return image, input_ids, ids


def pad_batch(model, images, input_ids, ctc_ids):
    pixel = []
    lengths = []
    for img in images:
        tensor = model.preprocess(img)  # (1, 64, W_padded)
        pixel.append(tensor.squeeze(0))
        lengths.append(tensor.shape[-1] // model.config.downsample)
    max_w = max(t.shape[-1] for t in pixel)
    pixel = [
        torch.cat([t, torch.ones(t.shape[0], max_w - t.shape[-1], dtype=t.dtype)], dim=-1) if t.shape[-1] < max_w else t
        for t in pixel
    ]
    pixel = torch.stack(pixel, dim=0).unsqueeze(1)  # (B, 1, 64, W)
    max_len = max(len(ids) for ids in input_ids)
    padded_ids = [ids + [model.config.pad_token_id] * (max_len - len(ids)) for ids in input_ids]
    masks = [[1] * len(ids) + [0] * (max_len - len(ids)) for ids in input_ids]
    max_ctc = max(len(ids) for ids in ctc_ids)
    ctc = [ids + [model.config.pad_token_id] * (max_ctc - len(ids)) for ids in ctc_ids]
    return (
        pixel,
        torch.tensor(padded_ids, dtype=torch.long),
        torch.tensor(lengths, dtype=torch.long),
        torch.tensor(masks, dtype=torch.bool),
        torch.tensor(ctc, dtype=torch.long),
        torch.tensor([len(ids) for ids in ctc_ids], dtype=torch.long),
    )


@torch.no_grad()
def evaluate(model, tokenizer, rows, data_dir: Path) -> dict:
    model.eval()
    cers = []
    for row in rows:
        img = Image.open(data_dir / row["image"]).convert("RGB")
        pred = model.transcribe(img, tokenizer, decode="ctc")
        cers.append(cer(norm(str(pred)), norm(row["label"])))
    model.train()
    return {
        "lines": len(cers),
        "median_cer": round(statistics.median(cers), 4) if cers else None,
        "mean_cer": round(statistics.mean(cers), 4) if cers else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("/home/agamya/.cache/telugu-ocr-ft/data"))
    ap.add_argument("--out", type=Path, default=Path("/home/agamya/.cache/telugu-ocr-ft/model"))
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=5e-5)
    ap.add_argument(
        "--mode",
        choices=["ctc", "full"],
        default="ctc",
        help="ctc fine-tunes the 20M encoder only; full also trains the decoder",
    )
    ap.add_argument("--min-similarity", type=float, default=0.55)
    ap.add_argument("--max-per-book", type=int, default=300)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    random.seed(1337)
    torch.manual_seed(1337)
    torch.set_num_threads(8)

    rows = [
        json.loads(line)
        for line in (args.data / "aligned.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = [r for r in rows if r.get("similarity", 0) >= args.min_similarity]
    # Keep the CTC target shorter than the encoder frames even for very wide lines.
    rows = [r for r in rows if 3 <= len(r["label"]) <= 120]
    test_rows = [r for r in rows if r["split"] == "test"]
    by_book: dict[str, list[dict]] = {}
    for row in rows:
        if row["split"] == "train":
            by_book.setdefault(row["book"], []).append(row)
    train_rows = []
    for book_rows in by_book.values():
        random.shuffle(book_rows)
        train_rows.extend(book_rows[: args.max_per_book])
    if args.limit:
        train_rows = train_rows[: args.limit]
    random.shuffle(train_rows)
    print(f"train={len(train_rows)} test={len(test_rows)} (similarity>={args.min_similarity})", file=sys.stderr)

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModel.from_pretrained(args.model, trust_remote_code=True).eval()
    model.model.ctc_loss_weight = 0.3
    model.model.encoder_no_grad = False

    baseline = evaluate(model, tokenizer, test_rows[: min(250, len(test_rows))], args.data)
    print("baseline", baseline, file=sys.stderr)

    dataset = LineDataset(
        train_rows,
        args.data,
        tokenizer,
        train=True,
        vocab_limit=model.config.decoder_config["vocab_size"],
    )
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        drop_last=True,
        collate_fn=lambda batch: batch,
    )
    params = model.model.encoder_model.parameters() if args.mode == "ctc" else model.parameters()
    optimizer = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.01)
    total_steps = max(1, len(loader) * args.epochs)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=total_steps)

    model.train()
    step = 0
    started = time.time()
    for epoch in range(1, args.epochs + 1):
        losses = []
        for batch in loader:
            images = [item[0] for item in batch]
            input_ids = [item[1] for item in batch]
            ctc_ids = [item[2] for item in batch]
            pixel, ids, lengths, mask, ctc, ctc_lengths = pad_batch(model, images, input_ids, ctc_ids)
            if args.mode == "ctc":
                encoder_output, _ = model.model.encoder_model.encode(pixel, lengths)
                ctc_logits = model.model.encoder_model.ctc_head(encoder_output)
                log_probs = ctc_logits.float().log_softmax(dim=-1)
                loss = model.model.encoder_model.ctc_loss(
                    log_probs.permute(1, 0, 2),
                    ctc,
                    lengths,
                    ctc_lengths,
                )
            else:
                out = model.model(
                    pixel,
                    ids,
                    input_lengths=lengths,
                    text_padding_mask=mask,
                    ctc_labels=ctc,
                    ctc_label_lengths=ctc_lengths,
                )
                loss = out.loss
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            step += 1
            losses.append(float(loss.detach()))
            if step % 25 == 0:
                print(
                    f"epoch {epoch} step {step}/{total_steps} loss={statistics.mean(losses[-25:]):.4f} "
                    f"{(time.time() - started) / 60:.1f}min",
                    file=sys.stderr,
                )
        test = evaluate(model, tokenizer, test_rows[:300], args.data)
        print(f"epoch {epoch} test {test}", file=sys.stderr)
        args.out.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(args.out)
        # save_pretrained keeps the source repo's auto_map prefix; point it at
        # the local modules so HF_HUB_OFFLINE=1 can load the checkpoint.
        config_path = args.out / "config.json"
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
        config_data["auto_map"] = {
            "AutoConfig": "configuration_telugu_ocr.TeluguOCRConfig",
            "AutoModel": "modeling_telugu_ocr.TeluguOCRModel",
        }
        config_data["_name_or_path"] = str(args.out)
        config_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
        # The custom tokenizer's save_vocabulary() cannot serialize its
        # AddedToken keys, so copy the original tokenizer/code files instead.
        from huggingface_hub import snapshot_download

        snapshot = Path(snapshot_download(args.model))
        for name in (
            "configuration_telugu_ocr.py",
            "modeling_telugu_ocr.py",
            "tokenization_telugu_ocr.py",
            "vocab.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
        ):
            src = snapshot / name
            if src.exists():
                shutil.copyfile(src, args.out / name)
        (args.out / "training_log.json").write_text(
            json.dumps(
                {
                    "baseline": baseline,
                    "final": test,
                    "epoch": epoch,
                    "train_lines": len(train_rows),
                    "test_lines": len(test_rows),
                    "batch_size": args.batch_size,
                    "lr": args.lr,
                    "ctc_loss_weight": 0.3,
                    "elapsed_min": round((time.time() - started) / 60, 1),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    final = evaluate(model, tokenizer, test_rows, args.data)
    print(f"final {final}; model: {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
