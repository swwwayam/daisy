import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main
from ai_privacy import MemoryBudget, SQLiteBudget, private_profile, restore_names


def test_raw_examples_sensitive_statistics_and_column_names_are_removed():
    profile = {"columns": [{"name": "customer_email", "dtype": "object", "top_values": {"alice@example.com": 1}, "null_count": 2}, {"name": "phone", "dtype": "int64", "min": 9876543210, "max": 9876543211, "null_count": 0}, {"name": "amount", "dtype": "float64", "mean": 25}], "preview": [{"phone": 9876543210}], "class_balance": {"Private customer": 0.9}}
    safe, aliases = private_profile(profile, ["customer_email", "phone", "amount"])
    payload = json.dumps(safe)
    for secret in ("alice@example.com", "9876543210", "Private customer", "customer_email", '"phone"'):
        assert secret not in payload
    assert safe["columns"][2]["mean"] == 25
    assert restore_names({"column": "field_3", "summary": "Use field_3"}, aliases) == {"column": "amount", "summary": "Use amount"}


def test_durable_budget_is_shared_and_cannot_be_reset_by_restart():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "state.db"
        first = SQLiteBudget(path)
        identifier = first.reserve("a", 150000)
        second = SQLiteBudget(path)
        with pytest.raises(HTTPException) as exc:
            second.reserve("a", 60000)
        assert exc.value.status_code == 429
        second.settle(identifier, "b", 0)
        with pytest.raises(HTTPException): second.reserve("a", 60000)
        second.settle(identifier, "a", 100)
        second.reserve("a", 60000)
        second.reserve("b", 60000)


def test_request_quota_counts_calls_even_when_the_provider_fails():
    meter = MemoryBudget()
    for _ in range(100): meter.reserve("a", 1)
    with pytest.raises(HTTPException): meter.reserve("a", 1)


def test_budget_rejection_precedes_the_provider_call():
    client = MagicMock()
    meter = MagicMock()
    meter.reserve.side_effect = HTTPException(status_code=429, detail="budget reached")
    with patch.object(main, "ai_client", client), patch.object(main, "ai_budget", meter):
        with pytest.raises(HTTPException): main.generate_ai_text("hello", owner_id="a")
    client.chat.completions.create.assert_not_called()


def test_provider_usage_settles_the_reserved_token_budget():
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(usage=SimpleNamespace(total_tokens=31, completion_tokens=3), choices=[SimpleNamespace(message=SimpleNamespace(content="Hello"), finish_reason="stop")])
    meter = MagicMock()
    meter.reserve.return_value = "request"
    with patch.object(main, "ai_client", client), patch.object(main, "ai_budget", meter):
        main.generate_ai_text("hello", max_tokens=512, owner_id="a")
    meter.settle.assert_called_once_with("request", "a", 31)


def test_ai_disabled_pipeline_works_without_provider_and_preserves_zero():
    with patch.dict(main.USER_AI_SETTINGS, {}, clear=True), patch.object(main, "validate_access_token", AsyncMock(side_effect=lambda token: {"id": token})), patch.object(main, "ai_client", None), patch.object(main, "generate_ai_text") as ai, TestClient(main.app) as client:
        headers = {"Authorization": "Bearer privacy-user"}
        assert client.put("/ai-settings", headers=headers, json={"enabled": False}).status_code == 200
        csv = "amount,city,target\n" + "\n".join(f"{i if i != 2 else ''},Pune,{i % 2}" for i in range(60))
        original = client.post("/upload-dataset", headers=headers, files={"file": ("data.csv", csv, "text/csv")}).json()["dataset_id"]
        assert client.put(f"/ai-settings?dataset_id={original}", headers={"Authorization": "Bearer other"}, json={"enabled": False}).status_code == 404
        cleaned_response = client.post("/agents/data-cleaning", headers=headers, json={"dataset_id": original})
        assert cleaned_response.status_code == 200, cleaned_response.text
        cleaned = cleaned_response.json()["cleaned_dataset_id"]
        assert main.DATASETS[cleaned].loc[0, "amount"] == 0
        featured_response = client.post("/agents/feature-engineering", headers=headers, json={"dataset_id": cleaned, "target_column": "target"})
        assert featured_response.status_code == 200, featured_response.text
        featured = featured_response.json()["engineered_dataset_id"]
        selection = client.post("/agents/model-selection", headers=headers, json={"dataset_id": featured, "target_column": "target"})
        assert selection.status_code == 200, selection.text
        training = client.post("/agents/model-training", headers=headers, json={"dataset_id": featured, "target_column": "target", "candidate_models": ["logistic_regression"]})
        assert training.status_code == 200, training.text
        evaluation = client.post("/agents/evaluation", headers=headers, json={"dataset_id": featured, "target_column": "target", "model_name": "logistic_regression"})
        assert evaluation.status_code == 200, evaluation.text
        assert "Rule-based" in evaluation.json()["reasoning"]
        reply = client.post("/chat", headers=headers, json={"message": "hi", "dataset_id": featured}).json()["reply"]
        assert "disabled" in reply
        ai.assert_not_called()


def test_api_cleaning_uses_masked_profile_and_restores_real_action_column():
    with patch.object(main, "validate_access_token", AsyncMock(return_value={"id": "privacy-mask"})), patch.object(main, "ai_client", object()), patch.object(main, "generate_ai_text", return_value=json.dumps({"summary": "Fill field_1", "actions": [{"type": "impute", "column": "field_1", "strategy": "median"}]})) as ai, TestClient(main.app) as client:
        headers = {"Authorization": "Bearer token"}
        csv = "amount,email,target\n" + "\n".join(f"{i if i != 2 else ''},alice@example.com,{i % 2}" for i in range(60))
        identifier = client.post("/upload-dataset", headers=headers, files={"file": ("data.csv", csv, "text/csv")}).json()["dataset_id"]
        response = client.post("/agents/data-cleaning", headers=headers, json={"dataset_id": identifier})
        assert response.status_code == 200, response.text
        prompt = ai.call_args.args[0]
        assert "alice@example.com" not in prompt
        assert '"name": "email"' not in prompt
        assert response.json()["steps"][0]["column"] == "amount"
