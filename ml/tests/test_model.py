from types import SimpleNamespace

import torch
from torch import nn

from viettubelens_ml.model import IGNORE_LABEL, MultiTaskModel


class FakeEncoder(nn.Module):
    def __init__(self, hidden_size: int = 8) -> None:
        super().__init__()
        self.embedding = nn.Embedding(32, hidden_size)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
    ) -> SimpleNamespace:
        return SimpleNamespace(last_hidden_state=self.embedding(input_ids))


def test_multitask_model_outputs_all_heads_and_masked_loss() -> None:
    model = MultiTaskModel(FakeEncoder(), hidden_size=8, dropout=0)
    output = model(
        input_ids=torch.tensor([[1, 2, 3], [4, 5, 0]]),
        attention_mask=torch.tensor([[1, 1, 1], [1, 1, 0]]),
        sentiment_labels=torch.tensor([2, IGNORE_LABEL]),
        toxicity_labels=torch.tensor([0, 1]),
        relevance_labels=torch.tensor([IGNORE_LABEL, 1]),
    )
    assert output.sentiment_logits.shape == (2, 3)
    assert output.toxicity_logits.shape == (2,)
    assert output.relevance_logits.shape == (2,)
    assert output.embedding.shape == (2, 8)
    assert output.loss is not None and torch.isfinite(output.loss)
    assert set(output.task_losses or {}) == {"sentiment", "toxicity", "relevance"}


def test_model_can_run_without_labels_for_inference() -> None:
    model = MultiTaskModel(FakeEncoder(), hidden_size=8, dropout=0)
    output = model(input_ids=torch.tensor([[1, 2]]), attention_mask=torch.ones((1, 2)))
    assert output.loss is None
