from pathlib import Path

import pytest

from dataset_schema import CommentAnnotation, DatasetSplit, LabelSource, SentimentLabel
from viettubelens_ml.data import (
    IGNORE_LABEL,
    MultiTaskCollator,
    assert_disjoint_channels,
    channel_grouped_split,
    read_jsonl,
    write_jsonl,
)


def annotation(index: int, channel: str) -> CommentAnnotation:
    return CommentAnnotation(
        video_id=f"video{index:03d}",
        comment_id=f"comment-{index}",
        channel_id=channel,
        topic="education",
        text=f"Bình luận thử nghiệm số {index}",
        sentiment=SentimentLabel.POSITIVE,
        toxicity=False,
        relevance=True,
        annotator_ids=["annotator-a"],
    )


def test_channel_grouped_split_has_no_leakage() -> None:
    records = [annotation(index, f"channel-{index // 3}") for index in range(30)]
    splits = channel_grouped_split(records, seed=7)
    assert all(splits[split] for split in DatasetSplit)
    assert_disjoint_channels(splits)
    assert sum(map(len, splits.values())) == len(records)


def test_jsonl_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "comments.jsonl"
    records = [annotation(1, "channel-a"), annotation(2, "channel-b")]
    write_jsonl(path, records)
    assert read_jsonl(path) == records


def test_gold_test_rejects_pseudo_labels() -> None:
    with pytest.raises(ValueError, match="training split only"):
        CommentAnnotation(
            video_id="video001",
            comment_id="comment-1",
            channel_id="channel-a",
            topic="music",
            text="Pseudo label không được phép ở gold test",
            sentiment=SentimentLabel.NEUTRAL,
            label_source=LabelSource.PSEUDO,
            labeling_models={"sentiment": "test-model"},
            split=DatasetSplit.TEST,
        )


def test_pseudo_labels_require_model_provenance() -> None:
    with pytest.raises(ValueError, match="model provenance"):
        CommentAnnotation(
            video_id="video001",
            comment_id="comment-1",
            channel_id="channel-a",
            topic="music",
            text="Nhãn tự động phải ghi nguồn model",
            sentiment=SentimentLabel.NEUTRAL,
            label_source=LabelSource.PSEUDO,
            split=DatasetSplit.TRAIN,
        )


def test_pseudo_label_channels_are_reserved_for_training() -> None:
    records = [annotation(index, f"channel-{index}") for index in range(6)]
    pseudo = CommentAnnotation(
        video_id="pseudo01",
        comment_id="pseudo-comment",
        channel_id="pseudo-channel",
        topic="gaming",
        text="Ví dụ pseudo label chỉ dành cho train",
        sentiment=SentimentLabel.NEUTRAL,
        label_source=LabelSource.PSEUDO,
        labeling_models={"sentiment": "test-model"},
    )
    splits = channel_grouped_split([*records, pseudo], seed=2)
    assert any(item.channel_id == "pseudo-channel" for item in splits[DatasetSplit.TRAIN])
    assert all(
        item.channel_id != "pseudo-channel"
        for split in (DatasetSplit.VALIDATION, DatasetSplit.TEST)
        for item in splits[split]
    )


class FakeTokenizer:
    def __call__(self, texts: list[str], **_: object) -> dict[str, object]:
        import torch

        return {
            "input_ids": torch.ones((len(texts), 4), dtype=torch.long),
            "attention_mask": torch.ones((len(texts), 4), dtype=torch.long),
        }


def test_collator_masks_missing_task_labels() -> None:
    partial = annotation(1, "channel-a").model_copy(
        update={"toxicity": None, "relevance": None}
    )
    batch = MultiTaskCollator(FakeTokenizer())([partial])
    assert int(batch["sentiment_labels"][0]) == 2  # type: ignore[index]
    assert int(batch["toxicity_labels"][0]) == IGNORE_LABEL  # type: ignore[index]
    assert int(batch["relevance_labels"][0]) == IGNORE_LABEL  # type: ignore[index]
