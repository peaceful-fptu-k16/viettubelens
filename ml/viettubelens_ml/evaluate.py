"""Evaluate one frozen checkpoint on the untouched gold test split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from .data import CommentDataset, MultiTaskCollator, read_jsonl
from .model import MultiTaskModel
from .train import evaluate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--test", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    from transformers import AutoTokenizer

    device = torch.device(
        "cuda" if args.device == "auto" and torch.cuda.is_available() else
        "cpu" if args.device == "auto" else args.device
    )
    records = read_jsonl(args.test)
    if any(record.split is None or record.split.value != "test" for record in records):
        raise ValueError("Every gold evaluation record must declare split=test")
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        args.checkpoint, use_fast=True
    )
    loader = DataLoader(
        CommentDataset(records),
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=MultiTaskCollator(tokenizer, args.max_length),
    )
    model = MultiTaskModel.from_checkpoint(args.checkpoint, str(device))
    metrics, predictions = evaluate(model, loader, device)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "gold_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (args.output_dir / "gold_predictions.jsonl").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        for row in predictions:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
