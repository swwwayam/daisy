import numpy as np
import pandas as pd

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
    assert stats["features"]["x"]["mean"] == raw.loc[train, "x"].mean()
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
