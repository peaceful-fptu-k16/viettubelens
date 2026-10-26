"""Validated annotation records used by training and evaluation."""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class SentimentLabel(StrEnum):
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"


class LabelSource(StrEnum):
    HUMAN = "human"
    PSEUDO = "pseudo"
    IMPORTED = "imported"


class DatasetSplit(StrEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class CommentAnnotation(BaseModel):
    """One comment with one or more independently optional task labels."""

    video_id: str = Field(min_length=6, max_length=20)
    comment_id: str = Field(min_length=1)
    channel_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    text: str = Field(min_length=1)
    like_count: int = Field(default=0, ge=0)
    sentiment: SentimentLabel | None = None
    toxicity: bool | None = None
    relevance: bool | None = None
    label_source: LabelSource = LabelSource.HUMAN
    annotator_ids: list[str] = Field(default_factory=list)
    adjudicated: bool = False
    split: DatasetSplit | None = None

    @model_validator(mode="after")
    def validate_annotation(self) -> "CommentAnnotation":
        if self.sentiment is None and self.toxicity is None and self.relevance is None:
            raise ValueError("At least one task label is required")
        if self.label_source == LabelSource.HUMAN and not self.annotator_ids:
            raise ValueError("Human labels require at least one annotator_id")
        if (
            self.split in {DatasetSplit.VALIDATION, DatasetSplit.TEST}
            and self.label_source == LabelSource.PSEUDO
        ):
            raise ValueError("Pseudo-labels are allowed in the training split only")
        return self


class VideoAnnotation(BaseModel):
    video_id: str = Field(min_length=6, max_length=20)
    channel_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    overall_reaction: SentimentLabel
    sufficient_data: bool
    evidence_comment_ids: list[str] = Field(default_factory=list, max_length=3)
    annotator_ids: list[str] = Field(min_length=1)
    split: DatasetSplit | None = None
