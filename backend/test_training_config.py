import json
from unittest.mock import AsyncMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import main
import model_training
from training_config import configured_partitions


def frame():
    rng = np.random.default_rng(22)
    return pd.DataFrame({"x": rng.normal(size=100), "entity": np.repeat(np.arange(20), 5),
                         "date": pd.date_range("2025-01-01", periods=100).astype(str), "target": [0, 1] * 50})


def configuration(strategy):
    return {"target_column": "target", "problem_type": "classification", "split_strategy": strategy,
            "group_column": "entity" if strategy == "group" else None, "time_column": "date" if strategy == "time" else None,
            "primary_metric": "f1_macro", "duplicate_policy": "keep"}


@pytest.mark.parametrize("strategy", ["random", "stratified", "group", "time"])
def test_configured_splits_are_disjoint_and_repeatable(strategy):
    source = frame()
    config = configuration(strategy)
    _, train, validation, test = configured_partitions(source, config)
    assert not set(train) & set(validation) and not set(train) & set(test) and not set(validation) & set(test)
    assert set(train) | set(validation) | set(test) == set(source.index)
    assert train.equals(configured_partitions(source, config)[1])
    if strategy == "group":
        assert not set(source.loc[train, "entity"]) & set(source.loc[test, "entity"])
        assert not set(source.loc[validation, "entity"]) & set(source.loc[test, "entity"])
        assert not set(source.loc[train, "entity"]) & set(source.loc[validation, "entity"])
    if strategy == "time":
        assert source.loc[train, "date"].max() < source.loc[validation, "date"].min()
        assert source.loc[validation, "date"].max() < source.loc[test, "date"].min()
    if strategy == "stratified":
        assert source.loc[test, "target"].mean() == .5
    assert set(model_training.planning_frame(source, configuration=config).index) == set(train)


def test_time_ties_never_cross_folds():
    source = frame()
    source["date"] = np.repeat(pd.date_range("2025-01-01", periods=10).astype(str), 10)
    _, train, validation, test = configured_partitions(source, configuration("time"))
    assert not set(source.loc[train, "date"]) & set(source.loc[validation, "date"])
    assert not set(source.loc[test, "date"]) & set(source.loc[validation, "date"])


def test_quantity_target_can_override_classification_heuristic():
    source = frame().drop(columns=["entity", "date"])
    source["target"] = [1, 2, 3, 4] * 25
    config = {"target_column": "target", "problem_type": "regression", "split_strategy": "random", "primary_metric": "mae"}
    result = model_training.train_and_evaluate(source, "target", ["linear_regression", "ridge_regression"], raw_df=source, configuration=config)
    assert result["problem_type"] == "regression" and result["primary_metric"] == "mae"


def test_review_freezes_study_and_protects_target_and_groups():
    source = frame()
    config = configuration("group")
    with patch.object(main, "validate_access_token", AsyncMock(return_value={"id": "a"})), TestClient(main.app) as client:
        headers = {"Authorization": "Bearer a"}
        uploaded = client.post("/upload-dataset", headers=headers, files={"file": ("source.csv", source.to_csv(index=False), "text/csv")}).json()["dataset_id"]
        response = client.post(f"/dataset/{uploaded}/review", headers=headers, json={"training_config": config})
        assert response.status_code == 200, response.text
        identifier = response.json()["dataset_id"]
        assert "entity" not in main.DATASETS[identifier]
        assert main.dataset_training_config(identifier, "a", "target")["split_strategy"] == "group"
        with pytest.raises(main.HTTPException) as error:
            main.dataset_training_config(identifier, "a", "x")
        assert error.value.status_code == 409
        plan = {"summary": "Unsafe suggestion", "actions": [{"type": "drop_column", "column": "target"}]}
        with patch.object(main, "ai_client", object()), patch.object(main, "generate_ai_text", return_value=json.dumps(plan)):
            cleaned = client.post("/agents/data-cleaning", headers=headers, json={"dataset_id": identifier})
        assert cleaned.status_code == 200, cleaned.text
        assert "target" in main.DATASETS[cleaned.json()["cleaned_dataset_id"]]
        assert cleaned.json()["steps"][-1]["status"] == "skipped"
