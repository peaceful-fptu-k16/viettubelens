"""CLI for validating annotations and creating leakage-safe data splits."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from dataset_schema import DatasetSplit

from .data import channel_grouped_split, read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--validation-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    records = read_jsonl(args.input)
    splits = channel_grouped_split(
        records,
        validation_ratio=args.validation_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )
    summary: dict[str, object] = {"seed": args.seed, "total": len(records), "splits": {}}
    for split in DatasetSplit:
        items = splits[split]
        write_jsonl(args.output_dir / f"{split.value}.jsonl", items)
        summary["splits"][split.value] = {  # type: ignore[index]
            "comments": len(items),
            "channels": len({item.channel_id for item in items}),
            "topics": dict(Counter(item.topic for item in items)),
            "labels": {
                "sentiment": sum(item.sentiment is not None for item in items),
                "toxicity": sum(item.toxicity is not None for item in items),
                "relevance": sum(item.relevance is not None for item in items),
            },
        }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "split_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
