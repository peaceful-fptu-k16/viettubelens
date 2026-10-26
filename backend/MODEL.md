# Local multi-task model

The backend prefers the fine-tuned VietTubeLens ONNX artifact when
`MULTITASK_MODEL_PATH` is configured. Model binaries are intentionally ignored
by Git; `model-lock.json` records their expected hashes and provenance.

Expected local layout:

```text
backend/models/visobert-multitask-silver-v1/
├── model.onnx
├── model.onnx.data
├── model_manifest.json
├── tokenizer.json
├── tokenizer_config.json
└── special_tokens_map.json
```

Export a downloaded training checkpoint from the repository root:

```powershell
backend\.venv\Scripts\python.exe -m viettubelens_ml.export `
  --checkpoint D:\path\to\visobert-multitask-silver-v1 `
  --output-dir backend\models\visobert-multitask-silver-v1 `
  --model-version visobert-multitask-silver-v1 `
  --opset 18
```

The current artifact uses identity temperatures because a human-labelled
calibration set is not available yet. Do not describe silver-development scores
as gold accuracy.
