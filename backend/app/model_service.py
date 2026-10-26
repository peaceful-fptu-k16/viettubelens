import asyncio
import json
import logging
import math
import threading
from importlib import import_module
from pathlib import Path
from typing import Any

from .analyzer import CommentScore, ReactionAnalyzer
from .config import Settings
from .schemas import AnalysisResult, Comment, DataSource

logger = logging.getLogger(__name__)


class PretrainedModelService:
    """Lazy, batched inference over two Vietnamese social-language checkpoints."""

    def __init__(self, settings: Settings, fallback: ReactionAnalyzer) -> None:
        self.settings = settings
        self.fallback = fallback
        self.state = "disabled" if not settings.use_pretrained_models else "lazy"
        self.device = "not-loaded"
        self._torch: Any = None
        self._multitask_tokenizer: Any = None
        self._multitask_session: Any = None
        self._temperatures = {"sentiment": 1.0, "toxicity": 1.0, "relevance": 1.0}
        self._active_model_version = settings.model_version
        self._sentiment_tokenizer: Any = None
        self._sentiment_model: Any = None
        self._toxicity_tokenizer: Any = None
        self._toxicity_session: Any = None
        self._load_error: str | None = None
        self._load_lock = threading.Lock()

    async def warmup(self) -> None:
        if not self.settings.use_pretrained_models or self.state in {"ready", "fallback"}:
            return
        try:
            await asyncio.to_thread(self._ensure_loaded)
        except Exception as error:
            self.state = "fallback"
            self._load_error = type(error).__name__
            logger.warning(
                "Model warm-up failed (%s); fallback remains available", self._load_error
            )

    async def analyze(
        self, video_id: str, comments: list[Comment], source: DataSource
    ) -> AnalysisResult:
        results = await self.analyze_many([(video_id, comments, source)])
        return results[0]

    async def analyze_many(
        self, items: list[tuple[str, list[Comment], DataSource]]
    ) -> list[AnalysisResult]:
        if not self.settings.use_pretrained_models:
            return [
                self.fallback.analyze(video_id, comments, source)
                for video_id, comments, source in items
            ]
        if self.state == "fallback":
            return self._fallback_many(items)
        try:
            return await asyncio.to_thread(self._analyze_many_sync, items)
        except Exception as error:
            self.state = "fallback"
            self._load_error = type(error).__name__
            logger.warning(
                "Pretrained models unavailable (%s); using explicit heuristic fallback",
                self._load_error,
            )
            return self._fallback_many(items)

    async def analyze_adaptive_many(
        self, items: list[tuple[str, list[Comment], DataSource]]
    ) -> list[AnalysisResult]:
        initial_size = self.settings.adaptive_initial_comments
        initial_items = [
            (video_id, comments[:initial_size], source)
            for video_id, comments, source in items
        ]
        initial_results = await self.analyze_many(initial_items)
        refine_indices = [
            index
            for index, (result, (_, comments, _)) in enumerate(
                zip(initial_results, items, strict=True)
            )
            if len(comments) > initial_size
            and (
                result.abstained
                or result.confidence_score < self.settings.adaptive_expand_confidence
            )
        ]
        if not refine_indices:
            return initial_results
        refined = await self.analyze_many([items[index] for index in refine_indices])
        for index, result in zip(refine_indices, refined, strict=True):
            initial_results[index] = result
        return initial_results

    def _fallback_many(
        self, items: list[tuple[str, list[Comment], DataSource]]
    ) -> list[AnalysisResult]:
        return [
            self.fallback.analyze_scored(
                video_id,
                comments,
                source,
                [self.fallback.score_comment(comment) for comment in comments],
                model_version="signal-prism-heuristic-fallback-v1",
            )
            for video_id, comments, source in items
        ]

    def health(self) -> dict[str, str]:
        payload = {
            "model_status": self.state,
            "model_device": self.device,
            "model_version": self._active_model_version,
        }
        if self.settings.multitask_model_path:
            payload["model_backend"] = "local-multitask-onnx"
            payload["model_path"] = str(self.settings.multitask_model_path)
        else:
            payload["model_backend"] = "legacy-dual-model"
            payload["sentiment_model"] = self.settings.sentiment_model_name
            payload["toxicity_model"] = self.settings.toxicity_model_name
        if self._load_error:
            payload["fallback_reason"] = self._load_error
        return payload

    def _ensure_loaded(self) -> None:
        if self.state == "ready":
            return
        with self._load_lock:
            if self.state == "ready":
                return
            self.state = "loading"
            transformers = import_module("transformers")
            onnxruntime = import_module("onnxruntime")
            auto_tokenizer = transformers.AutoTokenizer
            if self.settings.multitask_model_path:
                model_dir = Path(self.settings.multitask_model_path)
                manifest_path = model_dir / "model_manifest.json"
                if not manifest_path.is_file():
                    raise FileNotFoundError(f"Missing model manifest: {manifest_path}")
                manifest = json.loads(manifest_path.read_text("utf-8"))
                model_path = model_dir / str(manifest["model_file"])
                if not model_path.is_file():
                    raise FileNotFoundError(f"Missing ONNX model: {model_path}")
                self._multitask_tokenizer = auto_tokenizer.from_pretrained(
                    model_dir, use_fast=True
                )
                self._multitask_session = onnxruntime.InferenceSession(
                    str(model_path), providers=["CPUExecutionProvider"]
                )
                self._temperatures = {
                    name: float(value)
                    for name, value in manifest.get("temperature", {}).items()
                }
                self._active_model_version = str(manifest["model_version"])
                self.device = "onnx-cpu"
                self.state = "ready"
                return

            torch = import_module("torch")
            huggingface_hub = import_module("huggingface_hub")
            auto_model = transformers.AutoModelForSequenceClassification
            if self.settings.model_device == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                device = self.settings.model_device
            self._sentiment_tokenizer = auto_tokenizer.from_pretrained(
                self.settings.sentiment_model_name, use_fast=True
            )
            self._sentiment_model = auto_model.from_pretrained(
                self.settings.sentiment_model_name
            ).to(device)
            self._toxicity_tokenizer = auto_tokenizer.from_pretrained(
                self.settings.toxicity_model_name, use_fast=True
            )
            toxicity_path = huggingface_hub.hf_hub_download(
                repo_id=self.settings.toxicity_model_name, filename="model.onnx"
            )
            self._toxicity_session = onnxruntime.InferenceSession(
                toxicity_path, providers=["CPUExecutionProvider"]
            )
            self._sentiment_model.eval()
            self._torch = torch
            self.device = device
            self.state = "ready"

    def _analyze_many_sync(
        self, items: list[tuple[str, list[Comment], DataSource]]
    ) -> list[AnalysisResult]:
        self._ensure_loaded()
        all_comments = [comment for _, comments, _ in items for comment in comments]
        texts = [comment.text for comment in all_comments]
        if self._multitask_session is not None:
            sentiment, toxicity, relevance = self._predict_multitask(texts)
        else:
            sentiment = self._predict_sentiment(texts)
            toxicity = self._predict_toxicity(texts)
            relevance = None
        results: list[AnalysisResult] = []
        offset = 0
        for video_id, comments, source in items:
            scored = []
            item_relevance = (
                relevance[offset : offset + len(comments)] if relevance is not None else None
            )
            rows = zip(
                comments,
                sentiment[offset : offset + len(comments)],
                toxicity[offset : offset + len(comments)],
                strict=True,
            )
            for index, (comment, probabilities, toxicity_probability) in enumerate(rows):
                heuristic = self.fallback.score_comment(comment)
                scored.append(
                    CommentScore(
                        comment=comment,
                        negative=probabilities[0],
                        positive=probabilities[1],
                        neutral=probabilities[2],
                        toxicity=toxicity_probability,
                        relevance=(
                            item_relevance[index]
                            if item_relevance is not None
                            else heuristic.relevance
                        ),
                    )
                )
            results.append(
                self.fallback.analyze_scored(
                    video_id,
                    comments,
                    source,
                    scored,
                    model_version=self._active_model_version,
                )
            )
            offset += len(comments)
        return results

    def _batches(self, texts: list[str]) -> list[list[str]]:
        size = self.settings.model_batch_size
        return [texts[index : index + size] for index in range(0, len(texts), size)]

    def _encoded(self, tokenizer: Any, texts: list[str]) -> dict[str, Any]:
        encoded = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors="pt",
        )
        return {name: value.to(self.device) for name, value in encoded.items()}

    def _predict_sentiment(self, texts: list[str]) -> list[tuple[float, float, float]]:
        predictions: list[tuple[float, float, float]] = []
        with self._torch.inference_mode():
            for batch in self._batches(texts):
                logits = self._sentiment_model(
                    **self._encoded(self._sentiment_tokenizer, batch)
                ).logits
                rows = self._torch.softmax(logits, dim=-1).detach().cpu().tolist()
                # The selected checkpoint defines 0=negative, 1=positive, 2=neutral.
                predictions.extend((float(row[0]), float(row[1]), float(row[2])) for row in rows)
        return predictions

    def _predict_toxicity(self, texts: list[str]) -> list[float]:
        predictions: list[float] = []
        input_names = {item.name for item in self._toxicity_session.get_inputs()}
        for batch in self._batches(texts):
            encoded = self._toxicity_tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="np",
            )
            inputs = {name: value for name, value in encoded.items() if name in input_names}
            logits = self._toxicity_session.run(None, inputs)[0]
            for row in logits:
                value = float(row[0])
                predictions.append(1 / (1 + math.exp(-value)))
        return predictions

    @staticmethod
    def _sigmoid(value: float, temperature: float) -> float:
        scaled = max(-30.0, min(30.0, value / max(0.05, temperature)))
        return 1 / (1 + math.exp(-scaled))

    @staticmethod
    def _softmax(values: list[float], temperature: float) -> list[float]:
        scaled = [value / max(0.05, temperature) for value in values]
        peak = max(scaled)
        exponentials = [math.exp(value - peak) for value in scaled]
        total = sum(exponentials)
        return [value / total for value in exponentials]

    def _predict_multitask(
        self, texts: list[str]
    ) -> tuple[list[tuple[float, float, float]], list[float], list[float]]:
        sentiment: list[tuple[float, float, float]] = []
        toxicity: list[float] = []
        relevance: list[float] = []
        input_names = {item.name for item in self._multitask_session.get_inputs()}
        for batch in self._batches(texts):
            encoded = self._multitask_tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=256,
                return_tensors="np",
            )
            inputs = {name: value for name, value in encoded.items() if name in input_names}
            outputs = self._multitask_session.run(
                ["sentiment_logits", "toxicity_logits", "relevance_logits"], inputs
            )
            for sentiment_row, toxicity_logit, relevance_logit in zip(
                outputs[0], outputs[1], outputs[2], strict=True
            ):
                probabilities = self._softmax(
                    [float(value) for value in sentiment_row],
                    self._temperatures.get("sentiment", 1.0),
                )
                # Export order: negative, neutral, positive. Aggregator order:
                # negative, positive, neutral.
                sentiment.append((probabilities[0], probabilities[2], probabilities[1]))
                toxicity.append(
                    self._sigmoid(
                        float(toxicity_logit), self._temperatures.get("toxicity", 1.0)
                    )
                )
                relevance.append(
                    self._sigmoid(
                        float(relevance_logit), self._temperatures.get("relevance", 1.0)
                    )
                )
        return sentiment, toxicity, relevance
