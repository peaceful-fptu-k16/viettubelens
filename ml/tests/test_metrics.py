import pytest

from viettubelens_ml.metrics import (
    binary_pr_auc,
    brier_score,
    expected_calibration_error,
    macro_f1,
    risk_coverage,
)


def test_metrics_are_exact_for_perfect_predictions() -> None:
    assert macro_f1([0, 1, 2], [0, 1, 2], 3) == pytest.approx(1)
    assert binary_pr_auc([0, 1, 1], [0.1, 0.8, 0.9]) == pytest.approx(1)
    assert brier_score([0, 1], [0, 1]) == pytest.approx(0)
    assert expected_calibration_error([1, 1], [1, 1]) == pytest.approx(0)


def test_risk_decreases_when_low_confidence_errors_are_abstained() -> None:
    curve = risk_coverage([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1], [0.5, 1.0])
    assert curve["0.50"] == pytest.approx(0)
    assert curve["1.00"] == pytest.approx(0.5)
