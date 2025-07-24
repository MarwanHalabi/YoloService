import os
import shutil
import unittest
from fastapi.testclient import TestClient
from app import app, DB_PATH, UPLOAD_DIR, PREDICTED_DIR, init_data
import pytest
from base import Base
from db import engine

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

        # Recreate tables and seed users
        init_data()
        Base.metadata.create_all(bind=engine)
        # Setup client
        cls.client = TestClient(app)


        with open("tests/sample.jpg", "rb") as img:
            response = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("admin", "admin"))
            if response.status_code == 200:
                cls.uid = response.json()["prediction_uid"]
            else:
                raise Exception("Failed to predict during setup.")

    def test_predict(self):
        with open("tests/sample.jpg", "rb") as img:
            response = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("admin", "admin"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.__class__.uid = data["prediction_uid"]
        self.assertIn("labels", data)
        self.assertTrue(len(data["labels"]) > 0)

    def test_predict_invalied(self):
        with open("tests/sample.jpg", "rb") as img:
            response = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("invalid_user", "badpass"))
        self.assertEqual(response.status_code, 401)

    def test_prediction_count(self):
        response = client.get("/predictions/count", auth=("admin", "admin"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("count", response.json())

    def test_get_labels(self):
        response = client.get("/labels", auth=("admin", "admin"))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_stats(self):
        response = client.get("/stats", auth=("admin", "admin"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_predictions", data)
        self.assertIn("average_confidence_score", data)

    def test_delete_prediction(self):
        response = client.delete(f"/prediction/{self.__class__.uid}", auth=("admin", "admin"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("deleted successfully", response.json()["message"])

        # Confirm it was removed
        check = client.get(f"/prediction/{self.__class__.uid}", auth=("admin", "admin"))
        self.assertEqual(check.status_code, 404)

    def test_full_prediction_flow(self):
        # Upload image
        with open("tests/sample.jpg", "rb") as img:
            res = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("admin", "admin"))
        self.assertEqual(res.status_code, 200)
        uid = res.json()["prediction_uid"]

        # Get prediction
        res = client.get(f"/prediction/{uid}", auth=("admin", "admin"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["uid"], uid)

        # Delete prediction
        res = client.delete(f"/prediction/{uid}", auth=("admin", "admin"))
        self.assertEqual(res.status_code, 200)
        self.assertIn("deleted successfully", res.json()["message"])

        # Confirm deletion
        res = client.get(f"/prediction/{uid}", auth=("admin", "admin"))
        self.assertEqual(res.status_code, 404)
    
    def test_predict_unauthorized(self):
        with open("tests/sample.jpg", "rb") as img:
            res = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")})
        self.assertEqual(res.status_code, 401)
    
    def test_predict_missing_file(self):
        res = client.post("/predict", files={}, auth=("admin", "admin"))
        self.assertEqual(res.status_code, 422)
    
    def test_prediction_not_found(self):
        uid = "non-existent-uid"
        res = client.get(f"/prediction/{uid}", auth=("admin", "admin"))
        self.assertEqual(res.status_code, 404)

    def test_delete_wrong_user(self):
    # Upload as admin
        with open("tests/sample.jpg", "rb") as img:
            res = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("admin2", "admin2"))
        uid = res.json()["prediction_uid"]

        # Try delete as admin
        res = client.delete(f"/prediction/{uid}", auth=("admin", "admin"))
        self.assertEqual(res.status_code, 403)


    def test_upload_no_file(self):
        response = client.post("/predict", files={}, auth=("admin", "admin"))
        self.assertEqual(response.status_code, 422)


    def test_get_prediction_not_found(self):
        response = client.get("/prediction/nonexistent-uid", auth=("admin", "admin"))
        self.assertEqual(response.status_code, 404)

    # def test_predict_invalid_image_format(self):
    #     # Create a dummy text file
    #     invalid_path = "tests/bad.txt"
    #     with open(invalid_path, "w") as f:
    #         f.write("notanimage")

    #     with open(invalid_path, "rb") as bad_file:
    #         response = client.post(
    #             "/predict",
    #             files={"file": ("bad.txt", bad_file, "text/plain")},
    #             auth=("admin", "admin")
    #         )

    #     os.remove(invalid_path)
    #     self.assertEqual(response.status_code, 400)


    def test_delete_other_user_prediction(self):
        # Predict as admin
        with open("tests/sample.jpg", "rb") as img:
            res = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("admin2", "admin2"))
        self.assertEqual(res.status_code, 200)
        uid = res.json()["prediction_uid"]

        # Try to delete as admin
        res = client.delete(f"/prediction/{uid}", auth=("admin", "admin"))
        self.assertEqual(res.status_code, 403)

    def test_get_other_user_prediction(self):
        # Predict as admin
        with open("tests/sample.jpg", "rb") as img:
            res = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("admin2", "admin2"))
        self.assertEqual(res.status_code, 200)
        uid = res.json()["prediction_uid"]

        # Try to access as admin
        res = client.get(f"/prediction/{uid}", auth=("admin", "admin"))
        self.assertEqual(res.status_code, 403)

    def test_stats_no_predictions(self):
        # Clean predictions
        shutil.rmtree("uploads", ignore_errors=True)
        os.makedirs("uploads/original", exist_ok=True)
        os.makedirs("uploads/predicted", exist_ok=True)
        init_data()

        res = client.get("/stats", auth=("admin", "admin"))
        self.assertEqual(res.status_code, 200)
        self.assertIn("total_predictions", res.json())

    def test_stats_multiple_predictions(self):
        for _ in range(2):
            with open("tests/sample.jpg", "rb") as img:
                client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("admin", "admin"))

        res = client.get("/stats", auth=("admin", "admin"))
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(res.json()["total_predictions"], 2)

    def test_unknown_route(self):
        res = client.get("/not-a-real-endpoint", auth=("admin", "admin"))
        self.assertEqual(res.status_code, 404)

    def test_get_predictions_by_label(self):
    # Upload an image to create a prediction with label 'sheep'
        with open("tests/sample.jpg", "rb") as img:
            predict_res = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("admin", "admin"))
            self.assertEqual(predict_res.status_code, 200)
            uid = predict_res.json()["prediction_uid"]

        # Get predictions by label
        label_res = client.get("/predictions/label/sheep", auth=("admin", "admin"))
        self.assertEqual(label_res.status_code, 200)
        data = label_res.json()

        self.assertTrue(any(pred["uid"] == uid for pred in data))
        self.assertTrue(all("uid" in pred and "timestamp" in pred for pred in data))

    def test_get_predictions_by_score(self):
        # Upload an image to create prediction with confidence scores
        with open("tests/sample.jpg", "rb") as img:
            res = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("admin", "admin"))
            self.assertEqual(res.status_code, 200)
            uid = res.json()["prediction_uid"]

        # Call the score filter endpoint
        score_res = client.get("/predictions/score/0.1", auth=("admin", "admin"))
        self.assertEqual(score_res.status_code, 200)
        data = score_res.json()

        self.assertTrue(any(pred["uid"] == uid for pred in data))
        self.assertTrue(all("uid" in pred and "timestamp" in pred for pred in data))

   
    def test_get_prediction_image(self):
        # Upload image to get prediction UID
        with open("tests/sample.jpg", "rb") as img:
            res = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("admin", "admin"))
            self.assertEqual(res.status_code, 200)
            uid = res.json()["prediction_uid"]

        # Get image with Accept header for JPEG
        headers = {"accept": "image/jpeg"}
        img_res = client.get(f"/prediction/{uid}/image", headers=headers, auth=("admin", "admin"))
        self.assertEqual(img_res.status_code, 200)
        self.assertIn(img_res.headers["content-type"], ["image/jpeg", "image/png"])

    def test_health_check(self):
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"status": "ok good!!"})

    def test_prediction_image_invalid_uid(self):
        headers = {"accept": "image/jpeg"}
        res = client.get("/prediction/invalid-uid/image", headers=headers, auth=("admin", "admin"))
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"], "Prediction not found")

    def test_prediction_image_wrong_user(self):
        # Predict as admin
        with open("tests/sample.jpg", "rb") as img:
            res = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("admin", "admin"))
        uid = res.json()["prediction_uid"]

        # Try to fetch as admin
        headers = {"accept": "image/jpeg"}
        res = client.get(f"/prediction/{uid}/image", headers=headers, auth=("admin2", "admin2"))
        self.assertEqual(res.status_code, 403)

    def test_prediction_image_not_acceptable(self):
        with open("tests/sample.jpg", "rb") as img:
            res = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("admin", "admin"))
        uid = res.json()["prediction_uid"]

        headers = {"accept": "application/json"}
        res = client.get(f"/prediction/{uid}/image", headers=headers, auth=("admin", "admin"))
        self.assertEqual(res.status_code, 406)

    def test_get_labels_last_week(self):
        res = client.get("/labels", auth=("admin", "admin"))
        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json(), list)

    def test_delete_prediction_invalid_uid(self):
        res = client.delete("/prediction/invalid", auth=("admin", "admin"))
        self.assertEqual(res.status_code, 404)

    def test_delete_prediction_wrong_user(self):
        with open("tests/sample.jpg", "rb") as img:
            res = client.post("/predict", files={"file": ("sample.jpg", img, "image/jpeg")}, auth=("admin", "admin"))
        uid = res.json()["prediction_uid"]

        res = client.delete(f"/prediction/{uid}", auth=("admin2", "admin2"))
        self.assertEqual(res.status_code, 403)
