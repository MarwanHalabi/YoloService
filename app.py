import time
from collections import Counter
from fastapi.concurrency import asynccontextmanager
from typing_extensions import Annotated
from fastapi import Depends, FastAPI, UploadFile, File, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, Response
from ultralytics import YOLO
import torch
from PIL import Image
import sqlite3
import os
import uuid
import shutil
from datetime import datetime, timedelta
from db import get_db, SessionLocal
from queries import *
from sqlalchemy.orm import Session
from init_db import create_initial_users
from base import Base
from db import engine


torch.cuda.is_available = lambda: False


UPLOAD_DIR = "uploads/original"
PREDICTED_DIR = "uploads/predicted"
DB_PATH = "predictions.db"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PREDICTED_DIR, exist_ok=True)

# Download the AI model (tiny model ~6MB)
model = YOLO("yolov8n.pt")  
security = HTTPBasic()


# Initialize default users ONCE
def init_data():
    db = SessionLocal()
    try:
        create_initial_users(db)
    finally:
        db.close()


def get_current_user(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    user = authenticate_user(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user.user_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Seed initial data
    db = SessionLocal()
    try:
        create_initial_users(db)
    finally:
        db.close()

    yield

app = FastAPI(lifespan=lifespan)

@app.post("/predict")
def predict(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    start_time = time.time()
    ext = os.path.splitext(file.filename)[1]
    uid = str(uuid.uuid4())
    original_path = os.path.join(UPLOAD_DIR, uid + ext)
    predicted_path = os.path.join(PREDICTED_DIR, uid + ext)

    
    with open(original_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    results = model(original_path, device="cpu")

    annotated_frame = results[0].plot()  # NumPy image with boxes
    annotated_image = Image.fromarray(annotated_frame)
    annotated_image.save(predicted_path)

    save_prediction_session(db, uid, original_path, predicted_path, user_id)
    
    detected_labels = []
    for box in results[0].boxes:
        label_idx = int(box.cls[0].item())
        label = model.names[label_idx]
        score = float(box.conf[0])
        bbox = box.xyxy[0].tolist()
        save_detection_object(db, uid, label, score, bbox)
        detected_labels.append(label)

    processing_time = round(time.time() - start_time, 2)

    return {
        "prediction_uid": uid, 
        "detection_count": len(results[0].boxes),
        "labels": detected_labels,
        "time_took": processing_time
    }

@app.get("/prediction/{uid}")
def get_prediction_by_uid(uid: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    prediction = query_prediction_by_uid(db, uid)
    
    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    
    if prediction.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return {
        "uid": prediction.uid,
        "timestamp": prediction.timestamp,
        "original_image": prediction.original_image,
        "predicted_image": prediction.predicted_image # TODO fix test detection_objects is REMOVED
    }

@app.get("/predictions/count")
def get_prediction_count_last_week(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get total number of predictions made in the last 7 days
    """
    
    one_week_ago = datetime.now() - timedelta(days=7)
    count = count_predictions_by_user(db, user_id, timestamp=one_week_ago.isoformat())
    return {"count": count}

@app.get("/predictions/label/{label}")
def get_predictions_by_label(label: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get prediction sessions containing objects with specified label
    """
    return query_predictions_by_label(db, label, user_id)

@app.get("/predictions/score/{min_score}")
def get_predictions_by_score(min_score: float, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get prediction sessions containing objects with score >= min_score
    """
   
    predictions = query_predictions_by_score(db, min_score, user_id)
    return predictions

@app.get("/image/{type}/{filename}")
def get_image(file_type: str, filename: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get image by type and filename
    """
    path = os.path.join("uploads", file_type, filename)
    file = query_image_by_type_and_filename(db, file_type, path)
    if not file:
        raise HTTPException(status_code=403, detail="Access denied")
    return FileResponse(file)

@app.get("/prediction/{uid}/image")
def get_prediction_image(uid: str, request: Request, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get prediction image by uid
    """
    accept = request.headers.get("accept", "")

    session = query_prediction_image_by_uid(db, uid)

    if not session:
            raise HTTPException(status_code=404, detail="Prediction not found")

    if session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    image_path = session.predicted_image

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Predicted image file not found")

    elif "image/jpeg" in accept or "image/jpg" in accept:
        return FileResponse(image_path, media_type="image/jpeg")
    else:
        # If the client doesn't accept image, respond with 406 Not Acceptable
        raise HTTPException(status_code=406, detail="Client does not accept an image format")

@app.get("/labels")
def get_labels_last_week(user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):
    one_week_ago = datetime.now() - timedelta(days=7)
    labels_last_week = query_last_Week_labels(db, user_id, timestamp=one_week_ago.isoformat())
    return labels_last_week

@app.delete("/prediction/{uid}")
def delete_prediction(uid: str, user_id: str = Depends(get_current_user), db: Session = Depends(get_db)):

    prediction = query_get_prediction_by_uid(db, uid)

    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")
    
    if prediction.user_id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete images
    for path in [prediction.original_image, prediction.predicted_image]:
        if os.path.exists(path):
            os.remove(path)

    # Delete DB entries
    query_delete_prediction_objects(db, uid)
    query_delete_prediction_session(db, uid)


    return {"message": f"Prediction {uid} deleted successfully"}


@app.get("/stats")
def get_prediction_stats(db: Session = Depends(get_db)):
    since = datetime.now() - timedelta(days=7)

    total_predictions = query_count_predictions_since(db, since.isoformat())

    scores = query_get_scores_since(db, since.isoformat())
    score_values = [s.score for s in scores]
    avg_score = round(sum(score_values) / len(score_values), 4) if score_values else 0.0

    labels = query_get_labels_since(db, since.isoformat())
    label_values = [l.label for l in labels]
    label_counts = Counter(label_values)

    return {
        "total_predictions": total_predictions,
        "average_confidence_score": avg_score,
        "most_common_labels": dict(label_counts.most_common())
    }

@app.get("/health")
def health():
    """
    Health check endpoint
    """
    return {"status": "ok good!!"}

if __name__ == "__main__": # pragma: no cover
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
