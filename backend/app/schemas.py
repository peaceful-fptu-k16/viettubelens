from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class AnalysisStatus(StrEnum):
    READY = "ready"
    QUEUED = "queued"
    INSUFFICIENT_DATA = "insufficient_data"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class Sentiment(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class ConfidenceTier(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DataSource(StrEnum):
    YOUTUBE = "youtube"
    DEMO = "demo"


class OpinionPattern(StrEnum):
    CONSENSUS = "consensus"
    BALANCED = "balanced"
    POLARIZED = "polarized"
    UNCERTAIN = "uncertain"


class SentimentDistribution(BaseModel):
    positive: float = Field(ge=0, le=1)
    neutral: float = Field(ge=0, le=1)
    negative: float = Field(ge=0, le=1)


class Evidence(BaseModel):
    comment_id: str
    text: str
    sentiment: Sentiment
    score: float = Field(ge=0, le=1)
    url: str | None = None


class AnalysisResult(BaseModel):
    video_id: str
    status: AnalysisStatus
    sample_size: int = 0
    relevant_count: int = 0
    sentiment_distribution: SentimentDistribution = SentimentDistribution(
        positive=0, neutral=1, negative=0
    )
    toxicity_rate: float = Field(default=0, ge=0, le=1)
    overall_reaction: Sentiment = Sentiment.NEUTRAL
    confidence_score: float = Field(default=0, ge=0, le=1)
    confidence_tier: ConfidenceTier = ConfidenceTier.LOW
    abstained: bool = False
    abstention_reasons: list[str] = []
    evidence: list[Evidence] = []
    opinion_pattern: OpinionPattern = OpinionPattern.UNCERTAIN
    polarization_score: float = Field(default=0, ge=0, le=1)
    minority_evidence: Evidence | None = None
    cache_hit: bool = False
    model_version: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: DataSource
    message: str | None = None


class BatchRequest(BaseModel):
    video_ids: list[str] = Field(min_length=1, max_length=6)
    max_comments: int = Field(default=30, ge=10, le=100)
    refresh: bool = False

    @field_validator("video_ids")
    @classmethod
    def validate_video_ids(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for video_id in value:
            item = video_id.strip()
            if not 6 <= len(item) <= 20 or not all(char.isalnum() or char in "_-" for char in item):
                raise ValueError(f"Invalid YouTube video ID: {video_id!r}")
            if item not in cleaned:
                cleaned.append(item)
        return cleaned


class BatchResponse(BaseModel):
    items: list[AnalysisResult]


class StatusRequest(BaseModel):
    video_ids: list[str] = Field(min_length=1, max_length=12)

    @field_validator("video_ids")
    @classmethod
    def validate_video_ids(cls, value: list[str]) -> list[str]:
        return BatchRequest.validate_video_ids(value)


class Comment(BaseModel):
    id: str
    text: str
    like_count: int = 0
    url: str | None = None
