# VietTubeLens ML pipeline

This package fine-tunes one shared Vietnamese social-language encoder for
sentiment, toxicity and relevance. It is deliberately separate from the API so
training dependencies and artifacts never become part of the extension bundle.

## What is implemented

- Pydantic JSONL validation with independently optional task labels.
- Hard rejection of pseudo-labels in the gold test split.
- Deterministic channel-grouped train/validation/test splitting.
- Shared ViSoBERT encoder with three classification heads.
- Masked multi-task loss for partially labelled datasets.
- Macro-F1, toxicity PR-AUC, Brier score, ECE and risk-coverage utilities.
- Validation-only temperature scaling.
- ONNX export with dynamic batch and sequence axes.
- Reproducible manifest containing label order, temperatures and abstention policy.

The learned video-level aggregator is the next stage. Until it is trained, the
backend can consume the exported comment scores using its current relevance-aware
aggregator and evidence selector.

## Environment

```bash
cd ml
python -m venv .venv
python -m pip install -e ".[dev,export]"
```

CUDA is selected by the training command when available. A T4-class GPU is a
reasonable starting point; CPU execution is intended only for tests and smoke runs.

## Annotation format

One JSON object per line:

```json
{
  "video_id": "video001",
  "comment_id": "comment-001",
  "channel_id": "channel-01",
  "topic": "education",
  "text": "Giải thích rõ và có ví dụ dễ hiểu.",
  "like_count": 12,
  "sentiment": "positive",
  "toxicity": false,
  "relevance": true,
  "label_source": "human",
  "annotator_ids": ["annotator-a"],
  "adjudicated": true
}
```

At least one of `sentiment`, `toxicity` or `relevance` is required. Missing task
labels are masked during training. Human labels require `annotator_ids`.

## 1. Validate and split by channel

```bash
python -m viettubelens_ml.prepare \
  --input data/raw/comments.jsonl \
  --output-dir data/processed \
  --seed 42
```

For a pipeline smoke test, replace the input with
`examples/comments.sample.jsonl`. This sample only verifies plumbing and must
never be used to report model quality.

Outputs `train.jsonl`, `validation.jsonl`, `test.jsonl` and
`split_summary.json`. A channel can occur in exactly one split.

## 2. Fine-tune the multi-task encoder

```bash
python -m viettubelens_ml.train \
  --train data/processed/train.jsonl \
  --validation data/processed/validation.jsonl \
  --output-dir runs/visobert-multitask-v1 \
  --base-model uitnlp/visobert \
  --epochs 4 \
  --batch-size 16 \
  --learning-rate 2e-5
```

The best checkpoint is selected by the mean of available validation Macro-F1
scores. The trainer saves raw validation logits for calibration; it never reads
the gold test split.

## 3. Calibrate on validation only

```bash
python -m viettubelens_ml.calibrate \
  --predictions runs/visobert-multitask-v1/validation_predictions.jsonl \
  --output runs/visobert-multitask-v1/calibration.json
```

## 4. Export a deployable ONNX model

```bash
python -m viettubelens_ml.export \
  --checkpoint runs/visobert-multitask-v1 \
  --calibration runs/visobert-multitask-v1/calibration.json \
  --output-dir artifacts/visobert-multitask-v1 \
  --model-version visobert-multitask-v1
```

The artifact directory contains `model.onnx`, tokenizer files and
`model_manifest.json`. The canonical sentiment label order is:

```text
0 = negative, 1 = neutral, 2 = positive
```

## 5. Evaluate the frozen model once on gold test

Only run this after the checkpoint, calibration and thresholds are frozen:

```bash
python -m viettubelens_ml.evaluate \
  --checkpoint runs/visobert-multitask-v1 \
  --test data/processed/test.jsonl \
  --output-dir runs/visobert-multitask-v1/gold
```

The command refuses records that are not explicitly marked `split=test`; the
schema separately rejects pseudo-labelled gold records.

## Quality gates

```bash
python -m pytest
python -m ruff check .
python -m mypy dataset_schema.py viettubelens_ml
```

For final experiments, run at least three seeds and report mean ± standard
deviation. Do not select temperatures, thresholds or checkpoints using the gold
test set. Pseudo-labels may augment training only.
