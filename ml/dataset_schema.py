"""Dataset validation types shared by annotation and training scripts."""

from enum import StrEnum

from pydantic import BaseModel, Field


class SentimentLabel(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class CommentAnnotation(BaseModel):
    video_id: str
    comment_id: str
    channel_id: str
    topic: str
    text: str = Field(min_length=1)
    sentiment: SentimentLabel
    toxicity: bool
    relevance: bool
    annotator_ids: list[str] = Field(min_length=1)
    adjudicated: bool = False
    split: str | None = None


class VideoAnnotation(BaseModel):
    video_id: str
    channel_id: str
    topic: str
    overall_reaction: str
    sufficient_data: bool
    evidence_comment_ids: list[str] = Field(default_factory=list, max_length=3)
    annotator_ids: list[str] = Field(min_length=1)
