from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_status_unauth():
    r = client.get("/health")
    assert r.status_code == 200

def test_predict_no_auth():
    with open("tests/test.jpg", "rb") as img:
        r = client.post("/predict", files={"file": img})
        assert r.status_code == 200
        assert r.json()["prediction_uid"]

def test_predict_with_auth():
    with open("tests/test.jpg", "rb") as img:
        r = client.post("/predict", files={"file": img}, auth=("user1", "pass1"))
        assert r.status_code == 200
        assert r.json()["prediction_uid"]

def test_protected_endpoint_no_auth():
    r = client.get("/labels")
    assert r.status_code == 401
