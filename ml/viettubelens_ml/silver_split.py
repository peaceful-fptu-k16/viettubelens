"""Create channel-disjoint train/development files from training-only silver labels."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from dataset_schema import DatasetSplit, LabelSource

from .data import assert_disjoint_channels, read_jsonl, write_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--development-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if not 0 < args.development_ratio < 0.5:
        raise ValueError("development-ratio must be between 0 and 0.5")
    records = read_jsonl(args.input)
    if any(
        record.split != DatasetSplit.TRAIN or record.label_source != LabelSource.PSEUDO
        for record in records
    ):
        raise ValueError("Silver split accepts pseudo-labelled split=train records only")
    channels = sorted({record.channel_id for record in records})
    random.Random(args.seed).shuffle(channels)
    count = max(1, round(len(channels) * args.development_ratio))
    development_channels = set(channels[:count])
    train = [record for record in records if record.channel_id not in development_channels]
    development = [record for record in records if record.channel_id in development_channels]
    assert_disjoint_channels(
        {DatasetSplit.TRAIN: train, DatasetSplit.VALIDATION: development}
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "silver-train.jsonl", train)
    write_jsonl(args.output_dir / "silver-development.jsonl", development)
    summary = {
        "seed": args.seed,
        "train_records": len(train),
        "development_records": len(development),
        "train_channels": len({record.channel_id for record in train}),
        "development_channels": len(development_channels),
        "warning": "Development labels are pseudo labels; do not report them as gold metrics.",
    }
    (args.output_dir / "silver-split-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
