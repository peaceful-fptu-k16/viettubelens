from dataset_schema import CommentAnnotation, DatasetSplit, LabelSource, SentimentLabel
from viettubelens_ml.auto_review import review


def record(text: str) -> CommentAnnotation:
    return CommentAnnotation(
        video_id="video001",
        comment_id="comment-1",
        channel_id="channel-a",
        topic="science",
        video_title="Video khoa học",
        text=text,
        sentiment=SentimentLabel.POSITIVE,
        toxicity=False,
        relevance=True,
        label_source=LabelSource.PSEUDO,
        label_confidences={"sentiment": 0.4, "toxicity": 0.9, "relevance": 0.7},
        labeling_models={"sentiment": "test-model"},
        split=DatasetSplit.TRAIN,
    )


def test_review_marks_attendance_comment_irrelevant_and_neutral() -> None:
    reviewed = review(record("4 tháng sau quay lại"))
    assert reviewed.relevance is False
    assert reviewed.sentiment == SentimentLabel.NEUTRAL
    assert reviewed.labeling_models["review"] == "viettubelens-weak-supervision-v1"


def test_review_marks_explicit_abuse_toxic_and_negative() -> None:
    reviewed = review(record("Đồ ngu, video rác rưởi"))
    assert reviewed.toxicity is True
    assert reviewed.sentiment == SentimentLabel.NEGATIVE


def test_review_keeps_pseudo_provenance() -> None:
    reviewed = review(record("Video rất hay và hữu ích"))
    assert reviewed.label_source == LabelSource.PSEUDO
    assert reviewed.split == DatasetSplit.TRAIN
