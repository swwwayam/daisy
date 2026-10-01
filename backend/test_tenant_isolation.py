"""API regressions using two valid sessions to test resource authorization."""
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
