import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .config import Settings
from .schemas import (
    AnalysisResult,
    AnalysisStatus,
    Comment,
    ConfidenceTier,
    DataSource,
    Evidence,
    OpinionPattern,
    Sentiment,
    SentimentDistribution,
)

TOKEN_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)
POSITIVE = {
    "hay",
    "tốt",
    "hữu ích",
    "dễ hiểu",
    "chất lượng",
    "cảm ơn",
    "thuyết phục",
    "cuốn",
    "đầy đủ",
    "rõ",
}
NEGATIVE = {
    "tệ",
    "khó nghe",
    "phóng đại",
    "thiếu",
    "vội",
    "quảng cáo",
    "không đồng ý",
    "khó chịu",
    "sai",
    "ồn",
}
TOXIC = {"ngu", "dốt", "cút", "rác", "đừng làm", "khó chịu", "vô lý"}
IRRELEVANT = {"ai còn xem", "đến đây từ", "người thứ", "năm nay", "bao nhiêu phút"}


@dataclass(slots=True)
class CommentScore:
    comment: Comment
    positive: float
    neutral: float
    negative: float
    toxicity: float
    relevance: float

    @property
    def sentiment(self) -> Sentiment:
        values = {
            Sentiment.POSITIVE: self.positive,
            Sentiment.NEUTRAL: self.neutral,
            Sentiment.NEGATIVE: self.negative,
        }
        return max(values, key=values.get)  # type: ignore[arg-type]


def _contains(text: str, lexicon: set[str]) -> int:
    return sum(phrase in text for phrase in lexicon)


def _softmax(
    values: tuple[float, float, float], temperature: float = 1.15
) -> tuple[float, float, float]:
    shifted = [math.exp((value - max(values)) / temperature) for value in values]
    total = sum(shifted)
    return tuple(value / total for value in shifted)  # type: ignore[return-value]


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text)}


class ReactionAnalyzer:
    """Deployable fallback model with the same contract as the future ViSoBERT adapter."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def score_comment(self, comment: Comment) -> CommentScore:
        text = comment.text.lower()
        positive_hits, negative_hits = _contains(text, POSITIVE), _contains(text, NEGATIVE)
        positive, neutral, negative = _softmax(
            (0.4 + positive_hits * 1.35, 0.8, 0.4 + negative_hits * 1.35)
        )
        toxicity = min(0.96, 0.03 + _contains(text, TOXIC) * 0.82)
        relevance = (
            0.18
            if _contains(text, IRRELEVANT)
            else min(0.98, 0.68 + 0.05 * min(len(_tokens(text)), 5))
        )
        return CommentScore(comment, positive, neutral, negative, toxicity, relevance)

    def analyze(self, video_id: str, comments: list[Comment], source: DataSource) -> AnalysisResult:
        scored = [self.score_comment(comment) for comment in comments]
        return self.analyze_scored(video_id, comments, source, scored)

    def analyze_scored(
        self,
        video_id: str,
        comments: list[Comment],
        source: DataSource,
        scored: list[CommentScore],
        *,
        model_version: str | None = None,
    ) -> AnalysisResult:
        relevant = [item for item in scored if item.relevance >= 0.5]
        if not relevant:
            return self._insufficient(
                video_id,
                len(comments),
                0,
                source,
                "Không có bình luận phù hợp",
                model_version=model_version,
            )
        weights = [
            item.relevance * (1 + math.log1p(item.comment.like_count) * 0.08) for item in relevant
        ]
        total_weight = sum(weights)
        positive = (
            sum(item.positive * weight for item, weight in zip(relevant, weights, strict=True))
            / total_weight
        )
        neutral = (
            sum(item.neutral * weight for item, weight in zip(relevant, weights, strict=True))
            / total_weight
        )
        negative = (
            sum(item.negative * weight for item, weight in zip(relevant, weights, strict=True))
            / total_weight
        )
        toxicity = sum(
            item.toxicity >= self.settings.toxicity_threshold for item in relevant
        ) / len(relevant)
        margin = (
            sorted((positive, neutral, negative), reverse=True)[0]
            - sorted((positive, neutral, negative), reverse=True)[1]
        )
        sample_reliability = min(1.0, len(relevant) / 22)
        confidence = max(0.0, min(0.98, (0.58 + margin * 0.8) * (0.65 + sample_reliability * 0.35)))
        if positive >= max(neutral, negative):
            reaction = Sentiment.POSITIVE
        elif negative >= max(positive, neutral):
            reaction = Sentiment.NEGATIVE
        else:
            reaction = Sentiment.NEUTRAL
        if abs(positive - negative) < 0.08 and positive + negative > 0.58:
            reaction = Sentiment.MIXED
        reasons = []
        if len(relevant) < self.settings.min_relevant_comments:
            reasons.append(
                f"Chỉ có {len(relevant)} bình luận phù hợp; "
                f"cần ít nhất {self.settings.min_relevant_comments}"
            )
        if confidence < self.settings.confidence_threshold:
            reasons.append("Các tín hiệu phản ứng chưa đủ nhất quán")
        abstained = bool(reasons)
        status = (
            AnalysisStatus.INSUFFICIENT_DATA
            if len(relevant) < self.settings.min_relevant_comments
            else AnalysisStatus.READY
        )
        polarization = min(1.0, 2 * min(positive, negative)) * (1 - neutral)
        if abstained:
            opinion_pattern = OpinionPattern.UNCERTAIN
        elif positive >= 0.25 and negative >= 0.25 and polarization >= 0.4:
            opinion_pattern = OpinionPattern.POLARIZED
        elif max(positive, neutral, negative) >= 0.68:
            opinion_pattern = OpinionPattern.CONSENSUS
        else:
            opinion_pattern = OpinionPattern.BALANCED
        evidence = [] if abstained else self._select_evidence(relevant, reaction)
        minority_evidence = (
            self._select_minority_evidence(relevant, reaction)
            if opinion_pattern == OpinionPattern.POLARIZED
            else None
        )
        return AnalysisResult(
            video_id=video_id,
            status=status,
            sample_size=len(comments),
            relevant_count=len(relevant),
            sentiment_distribution=SentimentDistribution(
                positive=positive, neutral=neutral, negative=negative
            ),
            toxicity_rate=toxicity,
            overall_reaction=reaction,
            confidence_score=confidence,
            confidence_tier=self._tier(confidence),
            abstained=abstained,
            abstention_reasons=reasons,
            evidence=evidence,
            opinion_pattern=opinion_pattern,
            polarization_score=polarization,
            minority_evidence=minority_evidence,
            cache_hit=False,
            model_version=model_version or self.settings.model_version,
            updated_at=datetime.now(UTC),
            source=source,
        )

    def _select_evidence(
        self, candidates: list[CommentScore], reaction: Sentiment
    ) -> list[Evidence]:
        def representative(item: CommentScore) -> float:
            polarity = (
                item.positive
                if reaction == Sentiment.POSITIVE
                else item.negative
                if reaction == Sentiment.NEGATIVE
                else item.neutral
            )
            return min(
                1.0,
                0.5 * polarity
                + 0.35 * item.relevance
                + 0.15 * min(1, math.log1p(item.comment.like_count) / 5),
            )

        ranked = sorted(candidates, key=representative, reverse=True)
        selected: list[CommentScore] = []
        while ranked and len(selected) < 3:
            best, best_score = None, -1.0
            for candidate in ranked:
                similarity = max(
                    (self._jaccard(candidate.comment.text, item.comment.text) for item in selected),
                    default=0,
                )
                mmr = 0.78 * representative(candidate) - 0.22 * similarity
                if mmr > best_score:
                    best, best_score = candidate, mmr
            assert best is not None
            selected.append(best)
            ranked.remove(best)
        return [
            Evidence(
                comment_id=item.comment.id,
                text=item.comment.text,
                sentiment=item.sentiment,
                score=representative(item),
                url=item.comment.url,
            )
            for item in selected
        ]

    def _select_minority_evidence(
        self, candidates: list[CommentScore], reaction: Sentiment
    ) -> Evidence | None:
        if reaction == Sentiment.POSITIVE:
            target = Sentiment.NEGATIVE
        elif reaction == Sentiment.NEGATIVE:
            target = Sentiment.POSITIVE
        else:
            positive_count = sum(item.sentiment == Sentiment.POSITIVE for item in candidates)
            negative_count = sum(item.sentiment == Sentiment.NEGATIVE for item in candidates)
            target = Sentiment.POSITIVE if positive_count <= negative_count else Sentiment.NEGATIVE
        alternatives = [item for item in candidates if item.sentiment == target]
        if not alternatives:
            return None

        def score(item: CommentScore) -> float:
            polarity = item.positive if target == Sentiment.POSITIVE else item.negative
            return min(
                1.0,
                0.55 * polarity
                + 0.35 * item.relevance
                + 0.1 * min(1, math.log1p(item.comment.like_count) / 5),
            )

        selected = max(alternatives, key=score)
        return Evidence(
            comment_id=selected.comment.id,
            text=selected.comment.text,
            sentiment=selected.sentiment,
            score=score(selected),
            url=selected.comment.url,
        )

    @staticmethod
    def _jaccard(left: str, right: str) -> float:
        a, b = _tokens(left), _tokens(right)
        return len(a & b) / len(a | b) if a | b else 0

    @staticmethod
    def _tier(confidence: float) -> ConfidenceTier:
        if confidence >= 0.75:
            return ConfidenceTier.HIGH
        if confidence >= 0.58:
            return ConfidenceTier.MEDIUM
        return ConfidenceTier.LOW

    def _insufficient(
        self,
        video_id: str,
        sample_size: int,
        relevant_count: int,
        source: DataSource,
        reason: str,
        *,
        model_version: str | None = None,
    ) -> AnalysisResult:
        return AnalysisResult(
            video_id=video_id,
            status=AnalysisStatus.INSUFFICIENT_DATA,
            sample_size=sample_size,
            relevant_count=relevant_count,
            abstained=True,
            abstention_reasons=[reason],
            model_version=model_version or self.settings.model_version,
            source=source,
        )
