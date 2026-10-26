"""Shared ViSoBERT encoder with sentiment, toxicity and relevance heads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import torch
from torch import Tensor, nn
from torch.nn import functional as F

IGNORE_LABEL = -100


@dataclass
class MultiTaskOutput:
    sentiment_logits: Tensor
    toxicity_logits: Tensor
    relevance_logits: Tensor
    embedding: Tensor
    loss: Tensor | None = None
    task_losses: dict[str, Tensor] | None = None


class MultiTaskModel(nn.Module):
    """One encoder and three task heads with masked partial-label losses."""

    def __init__(
        self,
        encoder: nn.Module,
        hidden_size: int,
        *,
        dropout: float = 0.15,
        task_weights: dict[str, float] | None = None,
    ) -> None:
        super().__init__()
        self.encoder = encoder
        self.hidden_size = hidden_size
        self.dropout_rate = dropout
        self.dropout = nn.Dropout(dropout)
        self.sentiment_head = nn.Linear(hidden_size, 3)
        self.toxicity_head = nn.Linear(hidden_size, 1)
        self.relevance_head = nn.Linear(hidden_size, 1)
        self.task_weights = task_weights or {
            "sentiment": 1.0,
            "toxicity": 1.0,
            "relevance": 1.0,
        }

    @classmethod
    def from_pretrained(
        cls,
        model_name: str,
        *,
        dropout: float = 0.15,
        task_weights: dict[str, float] | None = None,
    ) -> MultiTaskModel:
        from transformers import AutoModel

        encoder = AutoModel.from_pretrained(model_name)
        hidden_size = int(encoder.config.hidden_size)
        return cls(
            encoder,
            hidden_size,
            dropout=dropout,
            task_weights=task_weights,
        )

    @classmethod
    def from_checkpoint(cls, checkpoint_dir: Path, device: str = "cpu") -> MultiTaskModel:
        import json

        config = json.loads((checkpoint_dir / "multitask_config.json").read_text("utf-8"))
        model = cls.from_pretrained(
            config["base_model"],
            dropout=float(config["dropout"]),
            task_weights=config["task_weights"],
        )
        state = torch.load(checkpoint_dir / "model.pt", map_location=device, weights_only=True)
        model.load_state_dict(state)
        return model.to(device)

    def save_checkpoint(self, output_dir: Path, *, base_model: str) -> None:
        import json

        output_dir.mkdir(parents=True, exist_ok=True)
        torch.save(self.state_dict(), output_dir / "model.pt")
        config = {
            "architecture": "shared-encoder-multitask-v1",
            "base_model": base_model,
            "hidden_size": self.hidden_size,
            "dropout": self.dropout_rate,
            "task_weights": self.task_weights,
            "label_order": {
                "sentiment": ["negative", "neutral", "positive"],
                "toxicity": ["non_toxic", "toxic"],
                "relevance": ["irrelevant", "relevant"],
            },
        }
        (output_dir / "multitask_config.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    def _pooled(self, encoded: Any, attention_mask: Tensor | None) -> Tensor:
        pooler = getattr(encoded, "pooler_output", None)
        if pooler is not None:
            return cast(Tensor, pooler)
        hidden: Tensor = encoded.last_hidden_state
        if attention_mask is None:
            return hidden[:, 0]
        mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
        return (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1)

    @staticmethod
    def _binary_loss(logits: Tensor, labels: Tensor) -> Tensor | None:
        mask = labels != IGNORE_LABEL
        if not bool(mask.any()):
            return None
        return F.binary_cross_entropy_with_logits(logits[mask], labels[mask].float())

    def forward(
        self,
        input_ids: Tensor,
        attention_mask: Tensor | None = None,
        token_type_ids: Tensor | None = None,
        sentiment_labels: Tensor | None = None,
        toxicity_labels: Tensor | None = None,
        relevance_labels: Tensor | None = None,
    ) -> MultiTaskOutput:
        encoder_inputs: dict[str, Tensor] = {"input_ids": input_ids}
        if attention_mask is not None:
            encoder_inputs["attention_mask"] = attention_mask
        if token_type_ids is not None:
            encoder_inputs["token_type_ids"] = token_type_ids
        encoded = self.encoder(**encoder_inputs)
        embedding = self.dropout(self._pooled(encoded, attention_mask))
        sentiment_logits = self.sentiment_head(embedding)
        toxicity_logits = self.toxicity_head(embedding).squeeze(-1)
        relevance_logits = self.relevance_head(embedding).squeeze(-1)

        losses: dict[str, Tensor] = {}
        if sentiment_labels is not None and bool((sentiment_labels != IGNORE_LABEL).any()):
            losses["sentiment"] = F.cross_entropy(
                sentiment_logits, sentiment_labels, ignore_index=IGNORE_LABEL
            )
        if toxicity_labels is not None:
            value = self._binary_loss(toxicity_logits, toxicity_labels)
            if value is not None:
                losses["toxicity"] = value
        if relevance_labels is not None:
            value = self._binary_loss(relevance_logits, relevance_labels)
            if value is not None:
                losses["relevance"] = value
        loss = None
        if losses:
            weighted = [losses[name] * self.task_weights[name] for name in losses]
            normalizer = sum(self.task_weights[name] for name in losses)
            loss = torch.stack(weighted).sum() / normalizer
        return MultiTaskOutput(
            sentiment_logits=sentiment_logits,
            toxicity_logits=toxicity_logits,
            relevance_logits=relevance_logits,
            embedding=embedding,
            loss=loss,
            task_losses=losses,
        )
