from app.analyzer import CommentScore, ReactionAnalyzer
from app.config import Settings
from app.model_service import PretrainedModelService
from app.schemas import Comment, DataSource


class FakeOnnxInput:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeMultitaskTokenizer:
    def __call__(self, texts, **kwargs):
        import numpy as np

        del kwargs
        return {
            "input_ids": np.ones((len(texts), 3), dtype=np.int64),
            "attention_mask": np.ones((len(texts), 3), dtype=np.int64),
        }


class FakeMultitaskSession:
    def get_inputs(self):
        return [FakeOnnxInput("input_ids"), FakeOnnxInput("attention_mask")]

    def run(self, output_names, inputs):
        import numpy as np

        assert output_names == [
            "sentiment_logits",
            "toxicity_logits",
            "relevance_logits",
        ]
        batch = inputs["input_ids"].shape[0]
        return [
            np.tile(np.array([[0.0, 1.0, 3.0]], dtype=np.float32), (batch, 1)),
            np.full((batch,), 2.0, dtype=np.float32),
            np.full((batch,), -2.0, dtype=np.float32),
        ]


def test_analyzer_returns_grounded_result(tmp_path):
    settings = Settings(cache_path=tmp_path / "test.db", min_relevant_comments=3)
    analyzer = ReactionAnalyzer(settings)
    comments = [
        Comment(id="1", text="Nội dung rất hay và dễ hiểu", like_count=20),
        Comment(id="2", text="Video chất lượng, cảm ơn tác giả", like_count=10),
        Comment(id="3", text="Giải thích rõ và hữu ích", like_count=5),
        Comment(id="4", text="Ai còn xem năm nay?"),
    ]
    result = analyzer.analyze("abc123xyz00", comments, DataSource.DEMO)
    assert result.status == "ready"
    assert result.relevant_count == 3
    assert result.sentiment_distribution.positive > result.sentiment_distribution.negative
    assert 1 <= len(result.evidence) <= 3
    assert result.opinion_pattern in {"consensus", "balanced"}


def test_analyzer_abstains_on_small_sample(tmp_path):
    settings = Settings(cache_path=tmp_path / "test.db", min_relevant_comments=10)
    result = ReactionAnalyzer(settings).analyze(
        "abc123xyz00", [Comment(id="1", text="Nội dung hay")], DataSource.DEMO
    )
    assert result.abstained is True
    assert result.status == "insufficient_data"


def test_analyzer_surfaces_polarization_and_minority_evidence(tmp_path):
    settings = Settings(cache_path=tmp_path / "test.db", min_relevant_comments=3)
    analyzer = ReactionAnalyzer(settings)
    comments = [
        Comment(id=str(index), text=f"Bình luận có lập luận {index}")
        for index in range(24)
    ]
    scored = [
        CommentScore(comment, 0.9, 0.05, 0.05, 0.02, 0.9)
        if index < 12
        else CommentScore(comment, 0.05, 0.05, 0.9, 0.02, 0.9)
        for index, comment in enumerate(comments)
    ]
    result = analyzer.analyze_scored("polarized01", comments, DataSource.DEMO, scored)
    assert result.opinion_pattern == "polarized"
    assert result.polarization_score >= 0.7
    assert result.minority_evidence is not None


async def test_adaptive_analysis_stops_early_for_clear_signal(tmp_path):
    settings = Settings(
        cache_path=tmp_path / "test.db",
        min_relevant_comments=3,
        use_pretrained_models=False,
        adaptive_initial_comments=16,
    )
    analyzer = ReactionAnalyzer(settings)
    service = PretrainedModelService(settings, analyzer)
    comments = [
        Comment(id=str(index), text="Video rất hay, hữu ích và dễ hiểu")
        for index in range(30)
    ]
    [result] = await service.analyze_adaptive_many(
        [("adaptive001", comments, DataSource.DEMO)]
    )
    assert result.status == "ready"
    assert result.sample_size == 16


async def test_adaptive_analysis_expands_uncertain_signal(tmp_path):
    settings = Settings(
        cache_path=tmp_path / "test.db",
        min_relevant_comments=3,
        use_pretrained_models=False,
        adaptive_initial_comments=16,
    )
    analyzer = ReactionAnalyzer(settings)
    service = PretrainedModelService(settings, analyzer)
    comments = [
        Comment(
            id=str(index),
            text="Video rất hay và hữu ích" if index % 2 == 0 else "Nội dung tệ và sai",
        )
        for index in range(30)
    ]
    [result] = await service.analyze_adaptive_many(
        [("adaptive002", comments, DataSource.DEMO)]
    )
    assert result.sample_size == 30


def test_multitask_onnx_output_is_mapped_to_aggregator_order(tmp_path):
    settings = Settings(cache_path=tmp_path / "test.db", use_pretrained_models=True)
    service = PretrainedModelService(settings, ReactionAnalyzer(settings))
    service._multitask_tokenizer = FakeMultitaskTokenizer()
    service._multitask_session = FakeMultitaskSession()
    sentiment, toxicity, relevance = service._predict_multitask(["Bình luận thử nghiệm"])
    negative, positive, neutral = sentiment[0]
    assert positive > neutral > negative
    assert toxicity[0] > 0.5
    assert relevance[0] < 0.5
