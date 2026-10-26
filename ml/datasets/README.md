# Dataset registry

This directory is safe to publish. It contains acquisition recipes, manifests,
licence notes and annotation guidance—not copied YouTube comment text.

## Why YouTube text is not committed

YouTube classifies comments returned by the Data API as API Data. Non-authorized
API Data may be cached for at most 30 days and must then be deleted or refreshed.
Committing comment text to permanent Git history would make deletion and refresh
unreliable. Local YouTube batches therefore stay in ignored `ml/data/` paths.

The repository publishes the reproducible collector, pseudonymization logic,
query definitions and aggregate manifest. A fresh clone can create a current
local snapshot with its own API key.

## Public human-labelled sources

See `sources.json`. Sources are downloaded from their owners at training time;
they are not vendored into this repository. Confirm each upstream licence for
the intended academic or commercial use before training.

## Manual annotation protocol

1. Read the whole comment once without looking at the suggested confidence.
2. Label sentiment toward the video/content, not the comment author's mood.
3. Mark toxicity only for abuse, attacks, threats, hate, or degrading language;
   disagreement and criticism alone are not toxic.
4. Mark relevance false for attendance checks, engagement bait, spam, unrelated
   links, or comments that do not express a reaction to the content.
5. Two annotators label the gold validation/test items independently. A third
   person adjudicates disagreements without seeing model predictions.
6. Never promote pseudo-labels to human labels without actually reviewing them.

Run the local interface from `ml/`:

```bash
python -m pip install -e ".[labeling]"
streamlit run viettubelens_ml/labeling_app.py -- \
  --input data/processed/pseudo-train-2026-10-26.jsonl \
  --output data/human/annotator-a.jsonl \
  --annotator-id annotator-a
```
