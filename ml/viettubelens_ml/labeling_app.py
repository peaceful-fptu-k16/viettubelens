"""Streamlit interface for independent human review of pseudo-labelled comments."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from dataset_schema import CommentAnnotation, LabelSource, SentimentLabel

from .data import read_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--annotator-id", required=True)
    parser.add_argument("--all", action="store_true", help="Review all, not only priority records")
    return parser.parse_args()


def priority(record: CommentAnnotation) -> bool:
    confidence = record.label_confidences
    return (
        confidence.get("sentiment", 1) < 0.72
        or confidence.get("toxicity", 1) < 0.8
        or record.toxicity is True
        or record.relevance is False
    )


def uncertainty(record: CommentAnnotation) -> float:
    return min(record.label_confidences.values(), default=1)


def completed_ids(path: Path) -> set[str]:
    if not path.exists() or path.stat().st_size == 0:
        return set()
    return {record.comment_id for record in read_jsonl(path)}


def append_human_label(
    path: Path,
    source: CommentAnnotation,
    annotator_id: str,
    sentiment: SentimentLabel,
    toxicity: bool,
    relevance: bool,
) -> None:
    record = CommentAnnotation.model_validate(
        source.model_copy(
            update={
                "sentiment": sentiment,
                "toxicity": toxicity,
                "relevance": relevance,
                "label_source": LabelSource.HUMAN,
                "label_confidences": {},
                "labeling_models": {},
                "annotator_ids": [annotator_id],
                "adjudicated": False,
            }
        ).model_dump()
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(record.model_dump_json(exclude_none=True) + "\n")


def label_index(value: Any, options: list[Any]) -> int:
    try:
        return options.index(value)
    except ValueError:
        return 0


def main() -> None:
    import streamlit as st

    args = parse_args()
    records = read_jsonl(args.input)
    candidates = records if args.all else [record for record in records if priority(record)]
    candidates.sort(key=uncertainty)
    done = completed_ids(args.output)
    remaining = [record for record in candidates if record.comment_id not in done]

    st.set_page_config(page_title="VietTubeLens Label Studio", page_icon="🔎", layout="centered")
    st.title("VietTubeLens · Human Review")
    st.caption(
        f"Annotator: {args.annotator_id} · Completed: {len(done)} / {len(candidates)}"
    )
    st.progress(min(1.0, len(done) / max(1, len(candidates))))
    if not remaining:
        st.success("Queue complete. Use a second annotator before adjudication.")
        return

    record = remaining[0]
    st.markdown(f"### {record.topic}")
    st.caption(f"Video: {record.video_title or record.video_id}")
    st.info(record.text)
    st.caption(
        f"Suggested confidence · sentiment {record.label_confidences.get('sentiment', 0):.2f} · "
        f"toxicity {record.label_confidences.get('toxicity', 0):.2f} · "
        f"relevance {record.label_confidences.get('relevance', 0):.2f}"
    )
    sentiment_options = list(SentimentLabel)
    boolean_options = [False, True]
    with st.form("annotation", clear_on_submit=False):
        sentiment = st.radio(
            "Sentiment",
            sentiment_options,
            index=label_index(record.sentiment, sentiment_options),
            format_func=lambda value: value.value,
            horizontal=True,
        )
        toxicity = st.radio(
            "Toxicity",
            boolean_options,
            index=label_index(record.toxicity, boolean_options),
            format_func=lambda value: "toxic" if value else "clean",
            horizontal=True,
        )
        relevance = st.radio(
            "Relevance",
            boolean_options,
            index=label_index(record.relevance, boolean_options),
            format_func=lambda value: "relevant" if value else "irrelevant",
            horizontal=True,
        )
        submitted = st.form_submit_button("Save & next", type="primary", use_container_width=True)
    if submitted:
        append_human_label(
            args.output,
            record,
            args.annotator_id,
            sentiment,
            toxicity,
            relevance,
        )
        st.rerun()


if __name__ == "__main__":
    main()
