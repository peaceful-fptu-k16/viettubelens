"""Create auditable training-only pseudo-labels with pretrained Vietnamese models."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

import torch
from huggingface_hub import hf_hub_download
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from dataset_schema import CommentAnnotation, DatasetSplit, LabelSource, SentimentLabel

from .data import write_jsonl

IRRELEVANT_PATTERNS = {
    "ai còn xem", "điểm danh", "người thứ", "đến đây từ", "bao nhiêu phút",
    "sub chéo", "đăng ký kênh", "follow mình", "xin tim", "2024", "2025", "2026",
}
TOKEN_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)


def batched(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def relevance_probability(text: str, title: str) -> float:
    lowered = text.casefold()
    tokens = set(TOKEN_RE.findall(lowered))
    title_tokens = set(TOKEN_RE.findall(title.casefold()))
    overlap = len(tokens & title_tokens) / max(1, min(len(tokens), len(title_tokens)))
    score = 0.76 + min(0.12, overlap * 0.35)
    if len(tokens) < 3:
        score -= 0.28
    if any(pattern in lowered for pattern in IRRELEVANT_PATTERNS):
        score -= 0.62
    if "http://" in lowered or "https://" in lowered:
        score -= 0.3
    return min(0.98, max(0.02, score))


class PseudoLabeler:
    def __init__(
        self,
        sentiment_model: str,
        toxicity_model: str,
        device: str,
        batch_size: int,
    ) -> None:
        import onnxruntime  # type: ignore[import-untyped]

        self.sentiment_model_name = sentiment_model
        self.toxicity_model_name = toxicity_model
        self.device = torch.device(device)
        self.batch_size = batch_size
        self.sentiment_tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
            sentiment_model, use_fast=True
        )
        self.sentiment_model = AutoModelForSequenceClassification.from_pretrained(
            sentiment_model
        ).to(self.device)
        self.sentiment_model.eval()
        self.toxicity_tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
            toxicity_model, use_fast=True
        )
        toxicity_path = hf_hub_download(repo_id=toxicity_model, filename="model.onnx")
        self.toxicity_session = onnxruntime.InferenceSession(
            toxicity_path, providers=["CPUExecutionProvider"]
        )

    def sentiment(self, texts: list[str]) -> list[tuple[SentimentLabel, float]]:
        results: list[tuple[SentimentLabel, float]] = []
        labels = [SentimentLabel.NEGATIVE, SentimentLabel.POSITIVE, SentimentLabel.NEUTRAL]
        with torch.inference_mode():
            for batch in batched(texts, self.batch_size):
                encoded = self.sentiment_tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=256,
                    return_tensors="pt",
                )
                encoded = {name: value.to(self.device) for name, value in encoded.items()}
                probabilities = self.sentiment_model(**encoded).logits.softmax(dim=-1).cpu()
                for row in probabilities:
                    index = int(row.argmax())
                    results.append((labels[index], float(row[index])))
        return results

    def toxicity(self, texts: list[str]) -> list[float]:
        probabilities: list[float] = []
        input_names = {item.name for item in self.toxicity_session.get_inputs()}
        for batch in batched(texts, self.batch_size):
            encoded = self.toxicity_tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="np",
            )
            inputs = {name: value for name, value in encoded.items() if name in input_names}
            logits = self.toxicity_session.run(None, inputs)[0]
            for row in logits:
                value = float(row[0])
                probabilities.append(1 / (1 + math.exp(-max(-30, min(30, value)))))
        return probabilities


def read_raw(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    if not rows:
        raise ValueError(f"No collected comments found in {path}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--sentiment-model", default="5CD-AI/Vietnamese-Sentiment-visobert")
    parser.add_argument("--toxicity-model", default="dangvansam/vietnamese-toxicity")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--sentiment-threshold", type=float, default=0.72)
    parser.add_argument("--toxicity-threshold", type=float, default=0.8)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    if args.batch_size < 1:
        raise ValueError("batch-size must be positive")
    device = "cuda" if args.device == "auto" and torch.cuda.is_available() else (
        "cpu" if args.device == "auto" else args.device
    )
    rows = read_raw(args.input)
    texts = [str(row["text"]) for row in rows]
    labeler = PseudoLabeler(
        args.sentiment_model, args.toxicity_model, device, args.batch_size
    )
    sentiment = labeler.sentiment(texts)
    toxicity = labeler.toxicity(texts)
    annotations: list[CommentAnnotation] = []
    review_rows: list[dict[str, Any]] = []
    stats: Counter[str] = Counter()
    for row, (sentiment_label, sentiment_confidence), toxic_probability in zip(
        rows, sentiment, toxicity, strict=True
    ):
        relevance_probability_value = relevance_probability(
            str(row["text"]), str(row.get("video_title", ""))
        )
        toxicity_label = toxic_probability >= 0.5
        toxicity_confidence = max(toxic_probability, 1 - toxic_probability)
        relevance_label = relevance_probability_value >= 0.5
        relevance_confidence = max(
            relevance_probability_value, 1 - relevance_probability_value
        )
        annotations.append(
            CommentAnnotation(
                video_id=row["video_id"],
                comment_id=row["comment_id"],
                channel_id=row["channel_id"],
                topic=row["topic"],
                video_title=row.get("video_title"),
                text=row["text"],
                like_count=row.get("like_count", 0),
                sentiment=sentiment_label,
                toxicity=toxicity_label,
                relevance=relevance_label,
                label_source=LabelSource.PSEUDO,
                label_confidences={
                    "sentiment": sentiment_confidence,
                    "toxicity": toxicity_confidence,
                    "relevance": relevance_confidence,
                },
                labeling_models={
                    "sentiment": args.sentiment_model,
                    "toxicity": args.toxicity_model,
                    "relevance": "viettubelens-relevance-rules-v1",
                },
                split=DatasetSplit.TRAIN,
                collected_at=row.get("collected_at"),
                published_at=row.get("published_at"),
            )
        )
        stats[f"sentiment_{sentiment_label.value}"] += 1
        stats[f"toxicity_{str(toxicity_label).lower()}"] += 1
        stats[f"relevance_{str(relevance_label).lower()}"] += 1
        needs_review = (
            sentiment_confidence < args.sentiment_threshold
            or toxicity_confidence < args.toxicity_threshold
            or toxicity_label
            or not relevance_label
        )
        if needs_review:
            review_rows.append(
                {
                    "video_id": row["video_id"],
                    "comment_id": row["comment_id"],
                    "topic": row["topic"],
                    "text": row["text"],
                    "suggested": {
                        "sentiment": sentiment_label.value,
                        "toxicity": toxicity_label,
                        "relevance": relevance_label,
                    },
                    "confidence": {
                        "sentiment": round(sentiment_confidence, 6),
                        "toxicity": round(toxicity_confidence, 6),
                        "relevance": round(relevance_confidence, 6),
                    },
                    "human": {"sentiment": None, "toxicity": None, "relevance": None},
                }
            )

    write_jsonl(args.output, annotations)
    args.review_output.parent.mkdir(parents=True, exist_ok=True)
    with args.review_output.open("w", encoding="utf-8", newline="\n") as handle:
        for row in sorted(
            review_rows,
            key=lambda item: min(item["confidence"].values()),
        ):
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "records": len(annotations),
        "review_queue": len(review_rows),
        "device": device,
        "labels": dict(stats),
        "warning": "Pseudo-labels are training-only and must not enter validation/test.",
    }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
