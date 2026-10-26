"""JSONL loading, channel-grouped splitting and multi-task collation."""

from __future__ import annotations

import random
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import Dataset

from dataset_schema import CommentAnnotation, DatasetSplit, LabelSource, SentimentLabel

SENTIMENT_TO_ID = {
    SentimentLabel.NEGATIVE: 0,
    SentimentLabel.NEUTRAL: 1,
    SentimentLabel.POSITIVE: 2,
}
IGNORE_LABEL = -100


def read_jsonl(path: Path) -> list[CommentAnnotation]:
    records: list[CommentAnnotation] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                records.append(CommentAnnotation.model_validate_json(line))
            except Exception as error:
                raise ValueError(f"Invalid annotation at {path}:{line_number}: {error}") from error
    if not records:
        raise ValueError(f"No annotations found in {path}")
    return records


def write_jsonl(path: Path, records: Iterable[CommentAnnotation]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(record.model_dump_json(exclude_none=True) + "\n")


def channel_grouped_split(
    records: Sequence[CommentAnnotation],
    *,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> dict[DatasetSplit, list[CommentAnnotation]]:
    """Split whole channels, never individual comments, across partitions."""

    if not 0 < validation_ratio < 1 or not 0 < test_ratio < 1:
        raise ValueError("validation_ratio and test_ratio must be between 0 and 1")
    if validation_ratio + test_ratio >= 1:
        raise ValueError("validation_ratio + test_ratio must be below 1")
    channels = sorted({record.channel_id for record in records})
    if len(channels) < 3:
        raise ValueError("At least three channels are required for grouped splitting")
    pseudo_channels = {
        record.channel_id for record in records if record.label_source == LabelSource.PSEUDO
    }
    evaluation_channels = [channel for channel in channels if channel not in pseudo_channels]
    if len(evaluation_channels) < 2:
        raise ValueError("At least two fully human/imported channels are required for evaluation")
    random.Random(seed).shuffle(evaluation_channels)

    validation_count = max(1, round(len(evaluation_channels) * validation_ratio))
    test_count = max(1, round(len(evaluation_channels) * test_ratio))
    if validation_count + test_count >= len(evaluation_channels):
        validation_count = test_count = 1
    test_channels = set(evaluation_channels[:test_count])
    validation_channels = set(
        evaluation_channels[test_count : test_count + validation_count]
    )
    split_records: dict[DatasetSplit, list[CommentAnnotation]] = {
        DatasetSplit.TRAIN: [],
        DatasetSplit.VALIDATION: [],
        DatasetSplit.TEST: [],
    }
    for record in records:
        split = (
            DatasetSplit.TEST
            if record.channel_id in test_channels
            else DatasetSplit.VALIDATION
            if record.channel_id in validation_channels
            else DatasetSplit.TRAIN
        )
        payload = CommentAnnotation.model_validate(
            record.model_copy(update={"split": split}).model_dump()
        )
        split_records[split].append(payload)
    assert_disjoint_channels(split_records)
    return split_records


def assert_disjoint_channels(
    splits: Mapping[DatasetSplit, Sequence[CommentAnnotation]],
) -> None:
    channel_sets = {
        name: {record.channel_id for record in records} for name, records in splits.items()
    }
    names = list(channel_sets)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            overlap = channel_sets[left] & channel_sets[right]
            if overlap:
                raise ValueError(f"Channel leakage between {left} and {right}: {sorted(overlap)}")


class CommentDataset(Dataset[CommentAnnotation]):
    def __init__(self, records: Sequence[CommentAnnotation]) -> None:
        self.records = list(records)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> CommentAnnotation:
        return self.records[index]


class MultiTaskCollator:
    def __init__(self, tokenizer: Any, max_length: int = 256) -> None:
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __call__(self, records: Sequence[CommentAnnotation]) -> dict[str, Any]:
        encoded: dict[str, Any] = dict(
            self.tokenizer(
                [record.text for record in records],
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
        )
        encoded["sentiment_labels"] = torch.tensor(
            [
                SENTIMENT_TO_ID[record.sentiment]
                if record.sentiment is not None
                else IGNORE_LABEL
                for record in records
            ],
            dtype=torch.long,
        )
        encoded["toxicity_labels"] = torch.tensor(
            [
                int(record.toxicity) if record.toxicity is not None else IGNORE_LABEL
                for record in records
            ],
            dtype=torch.long,
        )
        encoded["relevance_labels"] = torch.tensor(
            [
                int(record.relevance) if record.relevance is not None else IGNORE_LABEL
                for record in records
            ],
            dtype=torch.long,
        )
        encoded["metadata"] = [
            {
                "video_id": record.video_id,
                "comment_id": record.comment_id,
                "channel_id": record.channel_id,
                "like_count": record.like_count,
            }
            for record in records
        ]
        return encoded
