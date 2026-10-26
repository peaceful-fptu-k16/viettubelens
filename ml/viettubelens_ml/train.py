"""Fine-tune a shared ViSoBERT encoder for three comment-level tasks."""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path
from typing import Any

import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader

from dataset_schema import DatasetSplit

from .data import CommentDataset, MultiTaskCollator, read_jsonl
from .metrics import (
    binary_pr_auc,
    brier_score,
    expected_calibration_error,
    macro_f1,
    risk_coverage,
)
from .model import IGNORE_LABEL, MultiTaskModel


def seed_everything(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def move_batch(
    batch: dict[str, Any], device: torch.device
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    metadata = batch.pop("metadata")
    return (
        {
            key: value.to(device) if isinstance(value, torch.Tensor) else value
            for key, value in batch.items()
        },
        metadata,
    )


@torch.inference_mode()
def evaluate(
    model: MultiTaskModel,
    loader: DataLoader[Any],
    device: torch.device,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    model.eval()
    sentiment_targets: list[int] = []
    sentiment_predictions: list[int] = []
    sentiment_confidence: list[float] = []
    toxicity_targets: list[int] = []
    toxicity_probabilities: list[float] = []
    relevance_targets: list[int] = []
    relevance_probabilities: list[float] = []
    rows: list[dict[str, Any]] = []

    for raw_batch in loader:
        batch, metadata = move_batch(raw_batch, device)
        output = model(**batch)
        sentiment_probs = output.sentiment_logits.softmax(dim=-1)
        toxicity_probs = output.toxicity_logits.sigmoid()
        relevance_probs = output.relevance_logits.sigmoid()
        for index, item in enumerate(metadata):
            sentiment_label = int(batch["sentiment_labels"][index])
            toxicity_label = int(batch["toxicity_labels"][index])
            relevance_label = int(batch["relevance_labels"][index])
            sentiment_row = sentiment_probs[index].detach().cpu().tolist()
            sentiment_prediction = int(sentiment_probs[index].argmax())
            toxicity_probability = float(toxicity_probs[index])
            relevance_probability = float(relevance_probs[index])
            if sentiment_label != IGNORE_LABEL:
                sentiment_targets.append(sentiment_label)
                sentiment_predictions.append(sentiment_prediction)
                sentiment_confidence.append(max(sentiment_row))
            if toxicity_label != IGNORE_LABEL:
                toxicity_targets.append(toxicity_label)
                toxicity_probabilities.append(toxicity_probability)
            if relevance_label != IGNORE_LABEL:
                relevance_targets.append(relevance_label)
                relevance_probabilities.append(relevance_probability)
            rows.append(
                {
                    **item,
                    "sentiment_label": None if sentiment_label == IGNORE_LABEL else sentiment_label,
                    "sentiment_logits": output.sentiment_logits[index].detach().cpu().tolist(),
                    "toxicity_label": None if toxicity_label == IGNORE_LABEL else toxicity_label,
                    "toxicity_logit": float(output.toxicity_logits[index]),
                    "relevance_label": None if relevance_label == IGNORE_LABEL else relevance_label,
                    "relevance_logit": float(output.relevance_logits[index]),
                }
            )

    metrics: dict[str, float] = {}
    if sentiment_targets:
        correctness = [
            int(a == b)
            for a, b in zip(sentiment_targets, sentiment_predictions, strict=True)
        ]
        metrics["sentiment_macro_f1"] = macro_f1(sentiment_targets, sentiment_predictions, 3)
        metrics["sentiment_ece"] = expected_calibration_error(
            correctness, sentiment_confidence
        )
        for coverage, risk in risk_coverage(
            correctness, sentiment_confidence, [0.5, 0.7, 0.9, 1.0]
        ).items():
            metrics[f"sentiment_risk_at_{coverage}_coverage"] = risk
    if toxicity_targets:
        toxicity_predictions = [int(value >= 0.5) for value in toxicity_probabilities]
        metrics["toxicity_macro_f1"] = macro_f1(toxicity_targets, toxicity_predictions, 2)
        metrics["toxicity_pr_auc"] = binary_pr_auc(
            toxicity_targets, toxicity_probabilities
        )
        metrics["toxicity_brier"] = brier_score(toxicity_targets, toxicity_probabilities)
    if relevance_targets:
        relevance_predictions = [int(value >= 0.5) for value in relevance_probabilities]
        metrics["relevance_macro_f1"] = macro_f1(relevance_targets, relevance_predictions, 2)
        metrics["relevance_brier"] = brier_score(relevance_targets, relevance_probabilities)
    return metrics, rows


def selection_score(metrics: dict[str, float]) -> float:
    values = [value for key, value in metrics.items() if key.endswith("macro_f1")]
    return sum(values) / len(values) if values else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-model", default="uitnlp/visobert")
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--dropout", type=float, default=0.15)
    parser.add_argument("--gradient-accumulation", type=int, default=1)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    from transformers import AutoTokenizer, get_linear_schedule_with_warmup

    seed_everything(args.seed)
    if args.epochs < 1 or args.batch_size < 1 or args.gradient_accumulation < 1:
        raise ValueError("epochs, batch-size and gradient-accumulation must be positive")
    device = torch.device(
        "cuda" if args.device == "auto" and torch.cuda.is_available() else
        "cpu" if args.device == "auto" else args.device
    )
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        args.base_model, use_fast=True
    )
    collator = MultiTaskCollator(tokenizer, max_length=args.max_length)
    train_records = read_jsonl(args.train)
    validation_records = read_jsonl(args.validation)
    if any(record.split != DatasetSplit.TRAIN for record in train_records):
        raise ValueError("Every training record must declare split=train")
    if any(record.split != DatasetSplit.VALIDATION for record in validation_records):
        raise ValueError("Every validation record must declare split=validation")
    train_loader = DataLoader(
        CommentDataset(train_records),
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=collator,
    )
    validation_loader = DataLoader(
        CommentDataset(validation_records),
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=collator,
    )
    model = MultiTaskModel.from_pretrained(args.base_model, dropout=args.dropout).to(device)
    optimizer = AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    update_steps = max(
        1,
        math.ceil(len(train_loader) / args.gradient_accumulation) * args.epochs,
    )
    scheduler = get_linear_schedule_with_warmup(  # type: ignore[no-untyped-call]
        optimizer,
        num_warmup_steps=round(update_steps * args.warmup_ratio),
        num_training_steps=update_steps,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    best_score = -1.0
    history: list[dict[str, Any]] = []
    optimizer.zero_grad(set_to_none=True)

    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        for step, raw_batch in enumerate(train_loader, start=1):
            batch, _ = move_batch(raw_batch, device)
            output = model(**batch)
            if output.loss is None:
                raise RuntimeError("Training batch contains no labels")
            loss = output.loss / args.gradient_accumulation
            loss.backward()
            running_loss += float(output.loss.detach())
            if step % args.gradient_accumulation == 0 or step == len(train_loader):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)

        metrics, predictions = evaluate(model, validation_loader, device)
        record = {
            "epoch": epoch,
            "train_loss": running_loss / max(1, len(train_loader)),
            **metrics,
        }
        history.append(record)
        print(json.dumps(record, ensure_ascii=False))
        score = selection_score(metrics)
        if score > best_score:
            best_score = score
            model.save_checkpoint(args.output_dir, base_model=args.base_model)
            tokenizer.save_pretrained(args.output_dir)
            with (args.output_dir / "validation_predictions.jsonl").open(
                "w", encoding="utf-8", newline="\n"
            ) as handle:
                for row in predictions:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            (args.output_dir / "best_metrics.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

    (args.output_dir / "training_history.json").write_text(
        json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Best validation score: {best_score:.4f}; artifacts: {args.output_dir}")


if __name__ == "__main__":
    main()
