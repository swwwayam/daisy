"""Real fit/export/download/reload tests; LLM planning alone is mocked."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
import zipfile

import joblib
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

import agents
import feature_engineering as fe
import main
import model_export
import model_training
from daisy_predict import predict, transform


def raw_data():
    rng = np.random.default_rng(7)
    values = rng.normal(20, 6, 80)
    frame = pd.DataFrame({"amount": values, "city": [" Pune ", " Delhi "] * 40,
                          "reference": [f"item-{i}" for i in range(80)],
                          "unused": range(80), "target": (values > 20).astype(int)})
    frame.loc[[2, 11], "amount"] = np.nan
    return frame


class ModelExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.env = patch.dict(os.environ, {"DAISY_MODEL_DIR": self.directory.name})
        self.env.start()
        self.addCleanup(self.env.stop)

    def prepared(self, raw):
        operations = []
        cleaned, _ = agents.apply_cleaning_plan(raw, [
            {"type": "impute", "column": "amount", "strategy": "median"},
            {"type": "strip_whitespace", "column": "city"},
            {"type": "drop_column", "column": "unused"},
        ], fitted_steps=operations)
        engineered, _ = fe.apply_feature_engineering_plan(cleaned, [
            {"type": "scale_numeric", "column": "amount", "strategy": "standard"},
            {"type": "encode_categorical", "column": "city", "strategy": "onehot"},
        ], "target", fitted_steps=operations)
        engineered, _ = fe.apply_fallback_encoding(engineered, "target", fitted_steps=operations)
        return engineered, operations

    def test_classification_package_reloads_and_predicts_raw_rows(self):
        raw = raw_data()
        engineered, steps = self.prepared(raw)
        fitted = {}
        result = model_training.train_and_evaluate(engineered, "target", ["logistic_regression", "random_forest_classifier"], fitted_models=fitted)
        artifact = model_export.export_model(fitted[result["best_model"]], engineered, "target", steps, result, "dataset", "run", source_df=raw)
        with zipfile.ZipFile(model_export.artifact_path(artifact["artifact_id"])) as archive:
            self.assertEqual(set(archive.namelist()), {"model.joblib", "metadata.json", "input_schema.json", "requirements.txt", "README.md", "daisy_predict.py"})
            bundle = joblib.load(io.BytesIO(archive.read("model.joblib")))
            metadata = json.loads(archive.read("metadata.json"))
            self.assertEqual(metadata["model"], result["best_model"])
            archive.extractall(Path(self.directory.name) / "standalone")
        expected = fitted[result["best_model"]].predict(engineered.drop(columns="target"))
        np.testing.assert_array_equal(predict(bundle, raw.drop(columns=["target", "unused"])), expected)
        new = raw.iloc[:3].drop(columns=["target", "unused"]).copy()
        new["amount"] = [800, np.nan, 900]
        new["city"] = "Unknown city"
        new["reference"] = "new-reference"
        transformed = transform(bundle, new)
        self.assertTrue((transformed.filter(like="city_") == 0).all().all())
        self.assertTrue((transformed["reference"] == 0).all())
        self.assertGreater(transformed["amount"].iloc[0], 50)  # saved scale, not refit to this batch
        self.assertEqual(len(predict(bundle, new)), 3)
        standalone = Path(self.directory.name) / "standalone"
        new.to_csv(standalone / "new.csv", index=False)
        completed = subprocess.run([sys.executable, "daisy_predict.py", "new.csv", "predictions.csv"], cwd=standalone, capture_output=True, text=True, timeout=45)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(pd.read_csv(standalone / "predictions.csv")), 3)

    def test_regression_roundtrip_and_column_order(self):
        raw = raw_data().drop(columns=["city", "reference", "unused"]).dropna()
        raw["target"] = raw["amount"] * 4.8 + np.arange(len(raw)) * .31
        fitted = {}
        result = model_training.train_and_evaluate(raw, "target", ["linear_regression", "ridge_regression"], fitted_models=fitted)
        artifact = model_export.export_model(fitted[result["best_model"]], raw, "target", [], result, "reg", "run", source_df=raw)
        with zipfile.ZipFile(model_export.artifact_path(artifact["artifact_id"])) as archive:
            bundle = joblib.load(io.BytesIO(archive.read("model.joblib")))
        np.testing.assert_allclose(predict(bundle, raw[["target", "amount"]]), fitted[result["best_model"]].predict(raw[["amount"]]))
        with self.assertRaisesRegex(ValueError, "Missing required"):
            predict(bundle, pd.DataFrame({"wrong": [1]}))
        with self.assertRaisesRegex(ValueError, "missing or infinite"):
            predict(bundle, pd.DataFrame({"amount": [np.nan]}))

    def test_all_encoding_scaling_and_datetime_strategies(self):
        for strategy in ["standard", "minmax", "robust"]:
            raw = pd.DataFrame({"number": [1., 3., 8., 10.], "label": ["a", "b", "a", "b"],
                                "date": ["2026-01-01", "2026-02-02", "2026-03-03", "2026-04-04"]})
            steps = []
            engineered, _ = fe.apply_feature_engineering_plan(raw, [
                {"type": "scale_numeric", "column": "number", "strategy": strategy},
                {"type": "encode_categorical", "column": "label", "strategy": "label"},
                {"type": "extract_datetime_features", "column": "date"},
            ], fitted_steps=steps)
            bundle = {"input_columns": list(raw.columns), "feature_columns": list(engineered.columns), "target_column": "target", "preprocessing": steps}
            np.testing.assert_allclose(transform(bundle, raw), engineered.to_numpy(dtype=float))

    def test_explicit_zero_policy_is_replayed_at_inference(self):
        raw = pd.DataFrame({"Glucose": [0.0, 90.0, 100.0, np.nan]})
        steps = []
        cleaned, _ = agents.apply_cleaning_plan(raw, [
            {"type": "zero_to_missing", "column": "Glucose", "reasoning": "user policy"},
            {"type": "impute", "column": "Glucose", "strategy": "median", "reasoning": "fill missing"},
        ], fitted_steps=steps)
        bundle = {
            "input_columns": ["Glucose"],
            "feature_columns": ["Glucose"],
            "target_column": "target",
            "preprocessing": steps,
        }
        replayed = transform(bundle, pd.DataFrame({"Glucose": [0.0, 110.0]}))
        self.assertEqual(replayed.loc[0, "Glucose"], cleaned["Glucose"].median())
        self.assertEqual(replayed.loc[1, "Glucose"], 110.0)

    def test_api_pipeline_download_survives_memory_reset(self):
        auth = {"Authorization": "Bearer test-session"}
        with TestClient(main.app) as client, patch.object(main, "validate_access_token", new=AsyncMock(return_value={"id": "test-user"})), patch.dict(main.DATASETS, {}, clear=True), patch.dict(main.DATASET_TRANSFORMS, {}, clear=True), patch.dict(main.DATASET_PARENTS, {}, clear=True), patch.dict(main.PIPELINE_CONTEXT, {}, clear=True):
            uploaded = client.post("/upload-dataset", headers=auth, files={"file": ("sample.csv", raw_data().to_csv(index=False), "text/csv")})
            self.assertEqual(uploaded.status_code, 200)
            dataset = uploaded.json()["dataset_id"]
            with patch.object(main, "ai_client", object()), patch.object(main, "generate_ai_text", return_value=json.dumps({"summary": "Clean", "actions": [{"type": "impute", "column": "amount", "strategy": "median", "reasoning": "Missing values"}]})):
                cleaned = client.post("/agents/data-cleaning", headers=auth, json={"dataset_id": dataset}).json()["cleaned_dataset_id"]
            with patch.object(main, "ai_client", object()), patch.object(main, "generate_ai_text", return_value=json.dumps({"summary": "Encode", "actions": []})):
                featured = client.post("/agents/feature-engineering", headers=auth, json={"dataset_id": cleaned, "target_column": "target"}).json()["engineered_dataset_id"]
            response = client.post("/agents/model-training", headers=auth, json={"dataset_id": featured, "target_column": "target", "candidate_models": ["logistic_regression"], "test_size": .2})
            self.assertEqual(response.status_code, 200, response.text)
            summary = response.json()["output_summary"]
            self.assertIsNone(summary["export_error"], summary)
            identifier = summary["model_artifact"]["artifact_id"]
            main.DATASETS.clear()
            main.DATASET_TRANSFORMS.clear()
            downloaded = client.get(f"/models/{identifier}/download", headers=auth)
            self.assertEqual(downloaded.status_code, 200)
            self.assertEqual(downloaded.headers["content-type"], "application/zip")
            self.assertIn("attachment", downloaded.headers["content-disposition"])
            self.assertTrue(zipfile.is_zipfile(io.BytesIO(downloaded.content)))
            self.assertEqual(client.get("/models/not-a-uuid/download", headers=auth).status_code, 404)
            self.assertEqual(client.get("/models/00000000-0000-0000-0000-000000000000/download", headers=auth).status_code, 404)

    def test_failed_candidates_do_not_export_or_reuse_a_winner(self):
        raw = raw_data()[["amount", "target"]].dropna()
        with patch.object(model_training, "MODEL_FACTORY", {"logistic_regression": lambda: None}):
            fitted = {}
            result = model_training.train_and_evaluate(raw, "target", ["logistic_regression"], fitted_models=fitted)
        self.assertIsNone(result["best_model"])
        self.assertFalse(fitted)
        with self.assertRaises(model_training.TrainingDataError):
            model_training.train_and_evaluate(raw, "target", [])

    def test_saved_preprocessing_mismatch_fails_export(self):
        raw = raw_data()[["amount", "target"]].dropna()
        fitted = {}
        result = model_training.train_and_evaluate(raw, "target", ["logistic_regression"], fitted_models=fitted)
        altered = raw.copy()
        altered["amount"] *= 10
        with self.assertRaises(AssertionError):
            model_export.export_model(fitted[result["best_model"]], altered, "target", [], result, "ds", "run", source_df=raw)
        self.assertFalse(list(Path(self.directory.name).glob("*.zip")))


if __name__ == "__main__":
    unittest.main()
