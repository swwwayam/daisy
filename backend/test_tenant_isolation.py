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
