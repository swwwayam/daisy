import numpy as np
import pandas as pd
import pytest
import json

from input_shift import compare_inputs, training_reference
import model_training


def test_reference_uses_transformed_training_fold_only():
    raw = pd.DataFrame({"x": np.arange(100, dtype=float), "target": np.arange(100) * 4.2})
    _, train, validation, test = model_training.reserved_partitions(raw)
    raw.loc[validation.union(test), "x"] = 1000000
    result = model_training.train_and_evaluate(raw, "target", ["linear_regression"], raw_df=raw, finalize_test=False)
    stats = result["training_reference"]
    assert stats["scope"] == "transformed_training_only" and stats["rows"] == len(train)
    assert stats["features"]["x"]["max"] < 100
    assert stats["features"]["x"]["mean"] == pytest.approx(raw.loc[train, "x"].mean())
    # Legacy globally preprocessed runs cannot claim a training-only reference.
    assert model_training.train_and_evaluate(raw, "target", ["linear_regression"], finalize_test=False)["training_reference"] is None


def test_shift_checks_same_distribution_and_changed_inputs_without_mutating_rows():
    frame = pd.DataFrame({"x": np.linspace(-1, 1, 100), "constant": np.ones(100)})
    reference = training_reference(frame)
    assert compare_inputs(reference, frame)["status"] == "no_flags"
    changed = frame.assign(x=frame.x + 10, constant=2)
    original = changed.copy()
    report = compare_inputs(reference, changed)
    assert report["status"] == "review_inputs" and report["flagged_feature_count"] == 2
    constant = next(row for row in report["flagged_features"] if row["feature"] == "constant")
    assert constant["mean_shift_in_training_std"] is None and constant["outside_training_range_fraction"] == 1
    pd.testing.assert_frame_equal(changed, original)
    assert compare_inputs(reference, frame.head(29))["status"] == "insufficient_rows"
    assert compare_inputs(None, frame)["status"] == "unavailable"
    assert training_reference(pd.DataFrame(np.zeros((30, 1001))))["available"] is False


def test_large_finite_values_produce_finite_serializable_summaries_and_shift():
    frame = pd.DataFrame({"x": [1e308, -1e308] * 20, "constant": [1e308] * 40})
    with np.errstate(over="raise", invalid="raise"):
        reference = training_reference(frame)
        assert reference["features"]["x"]["mean"] == pytest.approx(0)
        assert reference["features"]["x"]["std"] == pytest.approx(1e308)
        assert reference["features"]["constant"]["std"] == 0
        report = compare_inputs(reference, frame.assign(constant=-1e308))
        assert report["status"] == "review_inputs"
        assert report["flagged_features"][0]["feature"] == "constant"
        json.dumps({"reference": reference, "report": report}, allow_nan=False)


def test_unrepresentable_mean_shift_is_flagged_without_invalid_json():
    reference = training_reference(pd.DataFrame({"x": [0.0, 1.0] * 20}))
    report = compare_inputs(reference, pd.DataFrame({"x": [1.7e308] * 40}))
    row = report["flagged_features"][0]
    assert row["mean_shift_exceeds_numeric_range"] and row["mean_shift_in_training_std"] is None
    assert row["outside_training_range_fraction"] == 1
    json.dumps(report, allow_nan=False)
