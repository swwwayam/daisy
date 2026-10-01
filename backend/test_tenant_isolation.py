"""API regressions using two valid sessions to test resource authorization."""
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import main
from resource_access import ResourceOwners


class TenantIsolationTests(unittest.TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(main.app))
        self.enterContext(patch.object(
            main, "validate_access_token", new=AsyncMock(side_effect=lambda token: {"id": token})
        ))
        self.enterContext(patch.object(main, "DATASET_OWNERS", ResourceOwners()))
        for store in (main.DATASETS, main.DATASET_PARENTS, main.DATASET_TRANSFORMS, main.PIPELINE_CONTEXT):
            self.enterContext(patch.dict(store, {}, clear=True))
        self.user_a = {"Authorization": "Bearer user-a"}
        self.user_b = {"Authorization": "Bearer user-b"}

    def upload(self, headers=None):
        response = self.client.post(
            "/upload-dataset", headers=headers or self.user_a,
            files={"file": ("sample.csv", "value,target\n1,0\n2,1\n3,0\n", "text/csv")},
            data={"owner_id": "user-b"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["dataset_id"]

    def test_upload_owner_can_read_and_download_their_dataset(self):
        dataset_id = self.upload()
        self.assertTrue(main.DATASET_OWNERS.permits(dataset_id, "user-a"))
        for endpoint in ("summary", "download"):
            response = self.client.get(f"/dataset/{dataset_id}/{endpoint}", headers=self.user_a)
            self.assertEqual(response.status_code, 200, response.text)

    def test_other_user_cannot_read_or_download_even_with_the_exact_id(self):
        dataset_id = self.upload()
        for endpoint in ("summary", "download"):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(f"/dataset/{dataset_id}/{endpoint}", headers=self.user_b)
                missing = self.client.get(f"/dataset/missing/{endpoint}", headers=self.user_b)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), missing.json())
                self.assertNotIn("value", response.text)

    def test_legacy_dataset_without_an_owner_is_inaccessible(self):
        main.DATASETS["legacy"] = main.pd.DataFrame({"secret": [42]})
        response = self.client.get("/dataset/legacy/summary", headers=self.user_a)
        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_cannot_upload_or_read(self):
        dataset_id = self.upload()
        self.assertEqual(self.client.get(f"/dataset/{dataset_id}/summary").status_code, 401)
        self.assertEqual(self.client.post("/upload-dataset").status_code, 401)

    def test_foreign_dataset_is_rejected_before_cleaning_or_eda_work(self):
        dataset_id = self.upload()
        with patch.object(main, "generate_ai_text") as ai, patch.object(main.agents, "profile_for_eda") as eda:
            for endpoint in ("data-cleaning", "eda"):
                response = self.client.post(
                    f"/agents/{endpoint}", headers=self.user_b, json={"dataset_id": dataset_id}
                )
                self.assertEqual(response.status_code, 404)
            ai.assert_not_called()
            eda.assert_not_called()

    def test_cleaning_outputs_inherit_ownership_and_do_not_overwrite_previous_runs(self):
        dataset_id = self.upload()
        outputs = []
        with patch.object(main, "ai_client", object()), patch.object(
            main, "generate_ai_text", return_value=json.dumps({"summary": "No changes", "actions": []})
        ):
            for _ in range(2):
                response = self.client.post(
                    "/agents/data-cleaning", headers=self.user_a, json={"dataset_id": dataset_id}
                )
                self.assertEqual(response.status_code, 200, response.text)
                outputs.append(response.json()["cleaned_dataset_id"])
        self.assertNotEqual(outputs[0], outputs[1])
        for child in outputs:
            self.assertTrue(main.DATASET_OWNERS.permits(child, "user-a"))
            self.assertEqual(main.DATASET_PARENTS[child], dataset_id)
            self.assertEqual(self.client.get(f"/dataset/{child}/download", headers=self.user_b).status_code, 404)
            self.assertEqual(self.client.post("/agents/eda", headers=self.user_b, json={"dataset_id": child}).status_code, 404)
        with patch.object(main, "ai_client", None):
            response = self.client.post("/agents/eda", headers=self.user_a, json={"dataset_id": outputs[0]})
        self.assertEqual(response.status_code, 200, response.text)

    def test_foreign_dataset_cannot_reach_feature_engineering_or_model_selection(self):
        dataset_id = self.upload()
        with patch.object(main, "generate_ai_text") as ai:
            for endpoint in ("feature-engineering", "model-selection"):
                response = self.client.post(
                    f"/agents/{endpoint}", headers=self.user_b,
                    json={"dataset_id": dataset_id, "target_column": "target"},
                )
                self.assertEqual(response.status_code, 404)
            ai.assert_not_called()

    def test_engineered_outputs_keep_the_owner_and_unique_identity(self):
        dataset_id = self.upload()
        outputs = []
        with patch.object(main, "ai_client", object()), patch.object(
            main, "generate_ai_text", return_value=json.dumps({"summary": "Keep features", "actions": []})
        ):
            for _ in range(2):
                response = self.client.post(
                    "/agents/feature-engineering", headers=self.user_a,
                    json={"dataset_id": dataset_id, "target_column": "target"},
                )
                self.assertEqual(response.status_code, 200, response.text)
                outputs.append(response.json()["engineered_dataset_id"])
        self.assertNotEqual(*outputs)
        for child in outputs:
            self.assertTrue(main.DATASET_OWNERS.permits(child, "user-a"))
            self.assertEqual(main.DATASET_PARENTS[child], dataset_id)
            self.assertEqual(self.client.get(f"/dataset/{child}/summary", headers=self.user_b).status_code, 404)

    def training_requests(self, dataset_id, headers):
        for endpoint, fields in (
            ("model-training", {"candidate_models": ["LogisticRegression"]}),
            ("evaluation", {"model_name": "LogisticRegression"}),
        ):
            yield self.client.post(
                f"/agents/{endpoint}", headers=headers,
                json={"dataset_id": dataset_id, "target_column": "target", **fields},
            )

    def test_foreign_dataset_cannot_be_trained_or_evaluated(self):
        dataset_id = self.upload()
        with patch.object(main.model_training, "train_and_evaluate") as train, patch.object(
            main.evaluation, "evaluate_model"
        ) as evaluate:
            for response in self.training_requests(dataset_id, self.user_b):
                self.assertEqual(response.status_code, 404)
            train.assert_not_called()
            evaluate.assert_not_called()

    def test_lineage_cannot_cross_an_owner_boundary_or_use_a_missing_parent(self):
        parent = self.upload(self.user_b)
        child = self.upload()
        with patch.object(main.model_training, "train_and_evaluate") as train, patch.object(
            main.evaluation, "evaluate_model"
        ) as evaluate:
            for invalid_parent in (parent, "missing"):
                main.DATASET_PARENTS[child] = invalid_parent
                for response in self.training_requests(child, self.user_a):
                    self.assertEqual(response.status_code, 404)
            train.assert_not_called()
            evaluate.assert_not_called()

    def test_cyclic_lineage_fails_before_training(self):
        dataset_id = self.upload()
        main.DATASET_PARENTS[dataset_id] = dataset_id
        for response in self.training_requests(dataset_id, self.user_a):
            self.assertEqual(response.status_code, 409)

    def test_chat_does_not_send_foreign_data_or_history_to_the_provider(self):
        dataset_id = self.upload()
        main.PIPELINE_CONTEXT[dataset_id] = {"model_training": {"private": "owner-only-result"}}
        with patch.object(main, "generate_ai_text") as ai, patch.object(main, "build_schema_report") as schema:
            for configured in (None, object()):
                with patch.object(main, "ai_client", configured):
                    foreign = self.client.post("/chat", headers=self.user_b, json={"message": "Explain", "dataset_id": dataset_id})
                    missing = self.client.post("/chat", headers=self.user_b, json={"message": "Explain", "dataset_id": "missing"})
                    self.assertEqual(foreign.status_code, 404)
                    self.assertEqual(foreign.json(), missing.json())
            ai.assert_not_called()
            schema.assert_not_called()

    def test_chat_authorizes_history_ancestors_and_allows_owner_or_no_dataset(self):
        dataset_id = self.upload()
        parent = self.upload(self.user_b)
        with patch.object(main, "ai_client", object()), patch.object(main, "generate_ai_text", return_value="Real provider reply") as ai:
            for dataset in (None, dataset_id):
                response = self.client.post("/chat", headers=self.user_a, json={"message": "hi", "dataset_id": dataset})
                self.assertEqual(response.json(), {"reply": "Real provider reply"})
            self.assertEqual(ai.call_count, 2)
            ai.reset_mock()
            main.DATASET_PARENTS[dataset_id] = parent
            response = self.client.post("/chat", headers=self.user_a, json={"message": "Explain history", "dataset_id": dataset_id})
            self.assertEqual(response.status_code, 404)
            ai.assert_not_called()

    def test_every_dataset_agent_rejects_foreign_missing_and_anonymous_requests(self):
        dataset_id = self.upload()
        for endpoint, fields in (
            ("data-cleaning", {}), ("eda", {}),
            ("feature-engineering", {"target_column": "target"}),
            ("model-selection", {"target_column": "target"}),
            ("model-training", {"target_column": "target", "candidate_models": ["logistic_regression"]}),
            ("evaluation", {"target_column": "target", "model_name": "logistic_regression"}),
        ):
            with self.subTest(endpoint=endpoint):
                payload = {"dataset_id": dataset_id, **fields}
                foreign = self.client.post(f"/agents/{endpoint}", headers=self.user_b, json=payload)
                missing = self.client.post(f"/agents/{endpoint}", headers=self.user_b, json={**payload, "dataset_id": "missing"})
                self.assertEqual(foreign.status_code, 404)
                self.assertEqual(foreign.json(), missing.json())
                self.assertEqual(self.client.post(f"/agents/{endpoint}", json=payload).status_code, 401)
        self.assertEqual(self.client.post("/chat", json={"message": "hi"}).status_code, 401)
