"""Dependency-light metrics for multi-task validation and calibration."""

from __future__ import annotations

from collections.abc import Sequence


def macro_f1(targets: Sequence[int], predictions: Sequence[int], classes: int) -> float:
    if len(targets) != len(predictions):
        raise ValueError("targets and predictions must have equal length")
    scores = []
    for label in range(classes):
        pairs = list(zip(targets, predictions, strict=True))
        true_positive = sum(t == label and p == label for t, p in pairs)
        false_positive = sum(t != label and p == label for t, p in pairs)
        false_negative = sum(t == label and p != label for t, p in pairs)
        precision_denominator = true_positive + false_positive
        recall_denominator = true_positive + false_negative
        precision = true_positive / precision_denominator if precision_denominator else 0
        recall = true_positive / recall_denominator if recall_denominator else 0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0)
    return sum(scores) / classes


def binary_pr_auc(targets: Sequence[int], probabilities: Sequence[float]) -> float:
    """Average precision, a step-wise PR-AUC suitable for imbalanced labels."""

    if len(targets) != len(probabilities):
        raise ValueError("targets and probabilities must have equal length")
    positives = sum(targets)
    if positives == 0:
        return 0.0
    ranked = sorted(zip(probabilities, targets, strict=True), reverse=True)
    true_positive = 0
    false_positive = 0
    previous_recall = 0.0
    area = 0.0
    for _, target in ranked:
        if target:
            true_positive += 1
        else:
            false_positive += 1
        recall = true_positive / positives
        precision = true_positive / (true_positive + false_positive)
        area += (recall - previous_recall) * precision
        previous_recall = recall
    return area


def brier_score(targets: Sequence[int], probabilities: Sequence[float]) -> float:
    if not targets or len(targets) != len(probabilities):
        raise ValueError("non-empty targets and equal-length probabilities are required")
    squared_errors = (
        (probability - target) ** 2
        for target, probability in zip(targets, probabilities, strict=True)
    )
    return sum(squared_errors) / len(targets)


def expected_calibration_error(
    correctness: Sequence[int], confidence: Sequence[float], bins: int = 10
) -> float:
    if not correctness or len(correctness) != len(confidence):
        raise ValueError("non-empty correctness and equal-length confidence are required")
    error = 0.0
    count = len(correctness)
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        members = [
            item
            for item, value in enumerate(confidence)
            if lower <= value < upper or (index == bins - 1 and value == 1)
        ]
        if not members:
            continue
        accuracy = sum(correctness[item] for item in members) / len(members)
        average_confidence = sum(confidence[item] for item in members) / len(members)
        error += len(members) / count * abs(accuracy - average_confidence)
    return error


def risk_coverage(
    correctness: Sequence[int], confidence: Sequence[float], coverages: Sequence[float]
) -> dict[str, float]:
    if not correctness or len(correctness) != len(confidence):
        raise ValueError("non-empty correctness and equal-length confidence are required")
    ranked = sorted(zip(confidence, correctness, strict=True), reverse=True)
    output: dict[str, float] = {}
    for coverage in coverages:
        keep = max(1, round(len(ranked) * coverage))
        risk = 1 - sum(item[1] for item in ranked[:keep]) / keep
        output[f"{coverage:.2f}"] = risk
    return output
