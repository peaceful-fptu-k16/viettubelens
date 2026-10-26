"""Export a trained multi-task checkpoint to a single ONNX graph."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import torch
from torch import Tensor, nn

from .model import MultiTaskModel


class OnnxWrapper(nn.Module):
    def __init__(self, model: MultiTaskModel) -> None:
        super().__init__()
        self.model = model

    def forward(self, input_ids: Tensor, attention_mask: Tensor) -> tuple[Tensor, ...]:
        output = self.model(input_ids=input_ids, attention_mask=attention_mask)
        return (
            output.sentiment_logits,
            output.toxicity_logits,
            output.relevance_logits,
            output.embedding,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--model-version", default="visobert-multitask-v1")
    parser.add_argument("--opset", type=int, default=18)
    args = parser.parse_args()

    from transformers import AutoTokenizer

    model = MultiTaskModel.from_checkpoint(args.checkpoint).eval()
    config = json.loads((args.checkpoint / "multitask_config.json").read_text("utf-8"))
    tokenizer = AutoTokenizer.from_pretrained(  # type: ignore[no-untyped-call]
        args.checkpoint, use_fast=True
    )
    encoded = tokenizer(
        ["Video này giải thích rõ ràng và có bằng chứng."],
        return_tensors="pt",
        padding=True,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    model_path = args.output_dir / "model.onnx"
    wrapper = OnnxWrapper(model).eval()
    torch.onnx.export(
        wrapper,
        (encoded["input_ids"], encoded["attention_mask"]),
        model_path,
        input_names=["input_ids", "attention_mask"],
        output_names=[
            "sentiment_logits",
            "toxicity_logits",
            "relevance_logits",
            "pooled_embedding",
        ],
        dynamic_axes={
            "input_ids": {0: "batch", 1: "sequence"},
            "attention_mask": {0: "batch", 1: "sequence"},
            "sentiment_logits": {0: "batch"},
            "toxicity_logits": {0: "batch"},
            "relevance_logits": {0: "batch"},
            "pooled_embedding": {0: "batch"},
        },
        opset_version=args.opset,
        do_constant_folding=True,
    )
    tokenizer.save_pretrained(args.output_dir)
    calibration = (
        json.loads(args.calibration.read_text("utf-8"))
        if args.calibration
        else {"temperature": {"sentiment": 1, "toxicity": 1, "relevance": 1}}
    )
    manifest = {
        "model_version": args.model_version,
        "created_at": datetime.now(UTC).isoformat(),
        "architecture": config["architecture"],
        "encoder": config["base_model"],
        "format": "onnx",
        "model_file": model_path.name,
        "tasks": ["sentiment", "toxicity", "relevance"],
        "label_order": config["label_order"],
        "temperature": calibration["temperature"],
        "abstention": {"minimum_relevant_comments": 10, "confidence_threshold": 0.58},
        "split_policy": "channel_grouped",
    }
    (args.output_dir / "model_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Exported {model_path}")


if __name__ == "__main__":
    main()
