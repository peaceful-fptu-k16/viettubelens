"""Apply transparent weak-supervision rules to uncertain pseudo-labels."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

from dataset_schema import CommentAnnotation, LabelSource, SentimentLabel

from .data import read_jsonl, write_jsonl

POSITIVE = {
    "bổ ích", "cảm ơn", "cuốn", "dễ hiểu", "hay", "hữu ích", "tuyệt", "xuất sắc",
}
NEGATIVE = {
    "chán", "dở", "khó chịu", "lừa đảo", "nhảm", "sai", "tệ", "thất vọng", "vô lý",
}
TOXIC = {
    "câm", "cút", "đần", "đồ ngu", "dốt", "khốn", "óc chó", "rác rưởi",
}
IRRELEVANT = {
    "ai còn xem", "còn ai xem", "đầu tiên", "điểm danh", "đăng ký kênh", "first",
    "follow mình", "người thứ", "quay lại", "sub chéo", "xin tim",
}
TOKEN_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)


def hits(text: str, phrases: set[str]) -> int:
    return sum(phrase in text for phrase in phrases)


def review(record: CommentAnnotation) -> CommentAnnotation:
    if record.label_source != LabelSource.PSEUDO:
        return record
    text = record.text.casefold()
    tokens = TOKEN_RE.findall(text)
    positive_hits = hits(text, POSITIVE)
    negative_hits = hits(text, NEGATIVE)
    toxic_hits = hits(text, TOXIC)
    irrelevant_hits = hits(text, IRRELEVANT)
    sentiment = record.sentiment
    toxicity = record.toxicity
    relevance = record.relevance
    confidence = dict(record.label_confidences)

    if irrelevant_hits or re.fullmatch(r"\d+\s*(tháng|năm|ngày).*", text):
        relevance = False
        confidence["relevance"] = max(confidence.get("relevance", 0), 0.96)
        if not positive_hits and not negative_hits and not toxic_hits:
            sentiment = SentimentLabel.NEUTRAL
            confidence["sentiment"] = max(confidence.get("sentiment", 0), 0.86)
    if toxic_hits:
        toxicity = True
        sentiment = SentimentLabel.NEGATIVE
        confidence["toxicity"] = max(confidence.get("toxicity", 0), 0.96)
        confidence["sentiment"] = max(confidence.get("sentiment", 0), 0.86)
    if confidence.get("sentiment", 0) < 0.72:
        if positive_hits > negative_hits:
            sentiment = SentimentLabel.POSITIVE
            confidence["sentiment"] = 0.78
        elif negative_hits > positive_hits:
            sentiment = SentimentLabel.NEGATIVE
            confidence["sentiment"] = 0.78
        elif text.rstrip().endswith("?") and len(tokens) >= 4:
            sentiment = SentimentLabel.NEUTRAL
            confidence["sentiment"] = 0.74

    models = dict(record.labeling_models)
    models["review"] = "viettubelens-weak-supervision-v1"
    return CommentAnnotation.model_validate(
        record.model_copy(
            update={
                "sentiment": sentiment,
                "toxicity": toxicity,
                "relevance": relevance,
                "label_confidences": confidence,
                "labeling_models": models,
            }
        ).model_dump()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = read_jsonl(args.input)
    reviewed = [review(record) for record in source]
    write_jsonl(args.output, reviewed)
    label_changes = sum(
        (left.sentiment, left.toxicity, left.relevance)
        != (right.sentiment, right.toxicity, right.relevance)
        for left, right in zip(source, reviewed, strict=True)
    )
    summary = {
        "records": len(reviewed),
        "records_with_review_provenance": sum(
            "review" in record.labeling_models for record in reviewed
        ),
        "label_changes": label_changes,
        "sentiment": dict(
            Counter(record.sentiment.value for record in reviewed if record.sentiment)
        ),
        "toxicity": dict(Counter(str(record.toxicity).lower() for record in reviewed)),
        "relevance": dict(Counter(str(record.relevance).lower() for record in reviewed)),
        "label_source": "pseudo",
        "warning": "Silver labels are not a substitute for a human gold test set.",
    }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
