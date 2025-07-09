import os
import shutil
import unittest
from fastapi.testclient import TestClient
from app import app, DB_PATH, UPLOAD_DIR, PREDICTED_DIR, init_db

client = TestClient(app)


class TestAppEndpoints(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Clean DB and folders before tests
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        shutil.rmtree("uploads", ignore_errors=True)
        os.makedirs("uploads/original", exist_ok=True)
        os.makedirs("uploads/predicted", exist_ok=True)
        init_db()
        cls.uid = None

    def test_01_predict(self):
        with open("tests/sample.jpg", "rb") as img:
            response = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.__class__.uid = data["prediction_uid"]
        self.assertIn("labels", data)
        self.assertTrue(len(data["labels"]) > 0)

    def test_02_prediction_count(self):
        response = client.get("/predictions/count")
        self.assertEqual(response.status_code, 200)
        self.assertIn("count", response.json())

    def test_03_get_prediction_by_uid(self):
        response = client.get(f"/prediction/{self.__class__.uid}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["uid"], self.__class__.uid)

    def test_04_get_labels(self):
        response = client.get("/labels")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_05_stats(self):
        response = client.get("/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_predictions", data)
        self.assertIn("average_confidence_score", data)

    def test_06_delete_prediction(self):
        response = client.delete(f"/prediction/{self.__class__.uid}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("deleted successfully", response.json()["message"])

        # Confirm it was removed
        check = client.get(f"/prediction/{self.__class__.uid}")
        self.assertEqual(check.status_code, 404)
