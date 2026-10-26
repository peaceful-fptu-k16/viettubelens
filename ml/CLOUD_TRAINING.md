# Fine-tune VietTubeLens on Colab or Kaggle

The local export contains silver/pseudo labels. It is suitable for pipeline
development and an initial checkpoint, but not for claiming final quality. Keep
an independently human-labelled validation and gold test set for calibration
and reporting.

## Local package

The generated archive is `data/exports/viettubelens-silver-2026-10-26.zip` and
contains channel-disjoint `silver-train.jsonl` and
`silver-development.jsonl`. The development labels remain pseudo labels.

## Google Colab

1. Create a private notebook and choose **Runtime → Change runtime type → T4 GPU**.
2. Upload the silver ZIP to the Colab session. Do not publish it as a shared file.
3. Run:

```python
!git clone https://github.com/peaceful-fptu-k16/viettubelens.git
%cd viettubelens/ml
!python -m pip install -e .
!unzip -q /content/viettubelens-silver-2026-10-26.zip -d /content/vtl-data

!python -m viettubelens_ml.train \
  --train /content/vtl-data/silver-train.jsonl \
  --validation /content/vtl-data/silver-development.jsonl \
  --allow-silver-validation \
  --output-dir /content/vtl-runs/visobert-multitask-silver-v1 \
  --base-model uitnlp/visobert \
  --epochs 3 \
  --batch-size 16 \
  --gradient-accumulation 2 \
  --learning-rate 2e-5 \
  --max-length 192 \
  --device cuda
```

Download the checkpoint:

```python
!cd /content/vtl-runs && zip -qr visobert-multitask-silver-v1.zip visobert-multitask-silver-v1
from google.colab import files
files.download("/content/vtl-runs/visobert-multitask-silver-v1.zip")
```

## Kaggle

1. Create a **private** Kaggle Dataset from the local ZIP.
2. Create a notebook, attach that private dataset, then select a GPU accelerator.
3. Internet must be enabled once to clone the repository and download ViSoBERT.
4. Replace `DATA_DIR` with the mounted Kaggle dataset directory and run:

```python
!git clone https://github.com/peaceful-fptu-k16/viettubelens.git /kaggle/working/viettubelens
%cd /kaggle/working/viettubelens/ml
!python -m pip install -e .

DATA_DIR = "/kaggle/input/viettubelens-silver"
!python -m viettubelens_ml.train \
  --train {DATA_DIR}/silver-train.jsonl \
  --validation {DATA_DIR}/silver-development.jsonl \
  --allow-silver-validation \
  --output-dir /kaggle/working/visobert-multitask-silver-v1 \
  --base-model uitnlp/visobert \
  --epochs 3 \
  --batch-size 16 \
  --gradient-accumulation 2 \
  --learning-rate 2e-5 \
  --max-length 192 \
  --device cuda
```

Kaggle saves `/kaggle/working` when the notebook version is committed.

## Reading the result

- Use `best_metrics.json` only as a silver development signal.
- Do not calibrate confidence or choose abstention thresholds from this split.
- After human validation is available, rerun evaluation, temperature scaling,
  threshold selection and ONNX export using the frozen checkpoint.
- If CUDA runs out of memory, reduce batch size to 8 and increase gradient
  accumulation to 4; the effective batch size remains 32.
