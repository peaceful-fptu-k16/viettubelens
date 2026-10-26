"""Fit per-task temperature scaling using validation logits only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch
from torch.nn import functional as F


def read_predictions(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def fit_multiclass(logits: torch.Tensor, labels: torch.Tensor) -> float:
    log_temperature = torch.zeros((), requires_grad=True)
    optimizer = torch.optim.LBFGS([log_temperature], lr=0.05, max_iter=80)

    def closure() -> torch.Tensor:
        optimizer.zero_grad()
        temperature = log_temperature.exp().clamp(0.05, 20)
        loss = F.cross_entropy(logits / temperature, labels)
        loss.backward()  # type: ignore[no-untyped-call]
        return loss

    optimizer.step(closure)  # type: ignore[no-untyped-call]
    return float(log_temperature.detach().exp().clamp(0.05, 20))


def fit_binary(logits: torch.Tensor, labels: torch.Tensor) -> float:
    log_temperature = torch.zeros((), requires_grad=True)
    optimizer = torch.optim.LBFGS([log_temperature], lr=0.05, max_iter=80)

    def closure() -> torch.Tensor:
        optimizer.zero_grad()
        temperature = log_temperature.exp().clamp(0.05, 20)
        loss = F.binary_cross_entropy_with_logits(logits / temperature, labels.float())
        loss.backward()  # type: ignore[no-untyped-call]
        return loss

    optimizer.step(closure)  # type: ignore[no-untyped-call]
    return float(log_temperature.detach().exp().clamp(0.05, 20))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = read_predictions(args.predictions)

    sentiment_rows = [row for row in rows if row["sentiment_label"] is not None]
    toxicity_rows = [row for row in rows if row["toxicity_label"] is not None]
    relevance_rows = [row for row in rows if row["relevance_label"] is not None]
    if not sentiment_rows or not toxicity_rows or not relevance_rows:
        raise ValueError("Validation predictions must contain labels for all three tasks")

    calibration = {
        "source": "validation_only",
        "temperature": {
            "sentiment": fit_multiclass(
                torch.tensor([row["sentiment_logits"] for row in sentiment_rows]),
                torch.tensor([row["sentiment_label"] for row in sentiment_rows]),
            ),
            "toxicity": fit_binary(
                torch.tensor([row["toxicity_logit"] for row in toxicity_rows]),
                torch.tensor([row["toxicity_label"] for row in toxicity_rows]),
            ),
            "relevance": fit_binary(
                torch.tensor([row["relevance_logit"] for row in relevance_rows]),
                torch.tensor([row["relevance_label"] for row in relevance_rows]),
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(calibration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(calibration, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
