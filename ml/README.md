# VietTubeLens ML

This folder defines the contract for replacing the deployable heuristic adapter
with the research ViSoBERT model. The backend response contract does not change.

## Training stages

1. Validate JSONL records with `dataset_schema.py`.
2. Fine-tune one shared ViSoBERT encoder with sentiment, toxicity and relevance heads.
3. Export calibrated comment probabilities and embeddings per video.
4. Train the relevance-aware attention aggregator.
5. Fit temperature scaling on validation data only and save thresholds in the model manifest.

The gold test set must never contain pseudo-labels and must not be used for
temperature or abstention-threshold selection.
