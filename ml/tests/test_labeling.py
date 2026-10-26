from pathlib import Path

from dataset_schema import CommentAnnotation, DatasetSplit, LabelSource, SentimentLabel
from viettubelens_ml.labeling_app import append_human_label, priority
from viettubelens_ml.merge import merge_records


def pseudo(comment_id: str, text: str, confidence: float = 0.9) -> CommentAnnotation:
    return CommentAnnotation(
        video_id="video001",
        comment_id=comment_id,
        channel_id="channel-a",
        topic="technology",
        text=text,
        sentiment=SentimentLabel.POSITIVE,
        toxicity=False,
        relevance=True,
        label_source=LabelSource.PSEUDO,
        label_confidences={
            "sentiment": confidence,
            "toxicity": 0.95,
            "relevance": 0.9,
        },
        labeling_models={"sentiment": "test-model"},
        split=DatasetSplit.TRAIN,
    )


def test_priority_selects_uncertain_records() -> None:
    assert priority(pseudo("a", "Nhãn chưa chắc chắn", 0.6))
    assert not priority(pseudo("b", "Nhãn đã khá chắc chắn", 0.9))


def test_human_review_preserves_record_and_clears_model_provenance(tmp_path: Path) -> None:
    output = tmp_path / "human.jsonl"
    append_human_label(
        output,
        pseudo("a", "Bình luận cần kiểm duyệt"),
        "annotator-a",
        SentimentLabel.NEGATIVE,
        True,
        False,
    )
    reviewed = CommentAnnotation.model_validate_json(output.read_text("utf-8").strip())
    assert reviewed.label_source == LabelSource.HUMAN
    assert reviewed.annotator_ids == ["annotator-a"]
    assert reviewed.sentiment == SentimentLabel.NEGATIVE
    assert reviewed.label_confidences == {}
    assert reviewed.labeling_models == {}


def test_merge_prefers_human_label_for_duplicate_text() -> None:
    automatic = pseudo("a", "Cùng một bình luận")
    human = automatic.model_copy(
        update={
            "comment_id": "b",
            "label_source": LabelSource.HUMAN,
            "annotator_ids": ["annotator-a"],
            "labeling_models": {},
            "label_confidences": {},
        }
    )
    merged = merge_records([[automatic], [CommentAnnotation.model_validate(human.model_dump())]])
    assert len(merged) == 1
    assert merged[0].label_source == LabelSource.HUMAN
