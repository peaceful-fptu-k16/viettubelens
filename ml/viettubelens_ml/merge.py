"""Merge annotation JSONL files with deterministic text-level deduplication."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from dataset_schema import CommentAnnotation, LabelSource

from .data import read_jsonl, write_jsonl


def fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.casefold()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def preference(record: CommentAnnotation) -> tuple[int, float]:
    source_priority = {
        LabelSource.PSEUDO: 0,
        LabelSource.IMPORTED: 1,
        LabelSource.HUMAN: 2,
    }
    confidence = min(record.label_confidences.values(), default=1.0)
    return source_priority[record.label_source], confidence


def merge_records(groups: list[list[CommentAnnotation]]) -> list[CommentAnnotation]:
    selected: dict[str, CommentAnnotation] = {}
    for records in groups:
        for record in records:
            key = fingerprint(record.text)
            existing = selected.get(key)
            if existing is not None and existing.split != record.split:
                raise ValueError(
                    f"Duplicate text crosses splits: {existing.split} and {record.split}"
                )
            if existing is None or preference(record) > preference(existing):
                selected[key] = record
    return sorted(selected.values(), key=lambda item: (item.topic, item.video_id, item.comment_id))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    groups = [read_jsonl(path) for path in args.input]
    merged = merge_records(groups)
    write_jsonl(args.output, merged)
    summary = {
        "input_records": sum(map(len, groups)),
        "output_records": len(merged),
        "duplicates_removed": sum(map(len, groups)) - len(merged),
        "sources": dict(Counter(record.label_source.value for record in merged)),
        "topics": dict(Counter(record.topic for record in merged)),
    }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
