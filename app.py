import time
from collections import Counter
from typing_extensions import Annotated
from fastapi import Depends, FastAPI, UploadFile, File, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.responses import FileResponse, Response
from ultralytics import YOLO
from PIL import Image
import sqlite3
import os
import uuid
import shutil
from datetime import datetime, timedelta

# Disable GPU usage
import torch
torch.cuda.is_available = lambda: False

app = FastAPI()

UPLOAD_DIR = "uploads/original"
PREDICTED_DIR = "uploads/predicted"
DB_PATH = "predictions.db"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PREDICTED_DIR, exist_ok=True)

# Download the AI model (tiny model ~6MB)
model = YOLO("yolov8n.pt")  
security = HTTPBasic()


# Initialize SQLite
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        """)

        # Create the predictions main table to store the prediction session
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prediction_sessions (
                uid TEXT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                original_image TEXT,
                predicted_image TEXT,
                user_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Create the objects table to store individual detected objects in a given image
        conn.execute("""
            CREATE TABLE IF NOT EXISTS detection_objects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_uid TEXT,
                label TEXT,
                score REAL,
                box TEXT,
                FOREIGN KEY (prediction_uid) REFERENCES prediction_sessions (uid)
            )
        """)
        
        # Insert default users if not exist
        existing_usernames = {row["username"] for row in conn.execute("SELECT username FROM users")}

        for username, password in [("user1", "pass1"), ("user2", "pass2")]:
            if username not in existing_usernames:
                conn.execute("INSERT INTO users (user_id, username, password) VALUES (?, ?, ?)",
                             (str(uuid.uuid4()), username, password))

        # Indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_prediction_uid ON detection_objects (prediction_uid)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_label ON detection_objects (label)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_score ON detection_objects (score)")


init_db()

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("""
            SELECT user_id FROM users WHERE username = ? AND password = ?
        """, (credentials.username, credentials.password)).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return row[0]  # return user_id
    

def save_prediction_session(uid, original_image, predicted_image, user_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO prediction_sessions (uid, original_image, predicted_image, user_id)
            VALUES (?, ?, ?, ?)
        """, (uid, original_image, predicted_image, user_id))

def save_detection_object(prediction_uid, label, score, box):
    """
    Save detection object to database
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO detection_objects (prediction_uid, label, score, box)
            VALUES (?, ?, ?, ?)
        """, (prediction_uid, label, score, str(box)))

@app.post("/predict")
def predict(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
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

    save_prediction_session(uid, original_path, predicted_path, user_id)
    
    detected_labels = []
    for box in results[0].boxes:
        label_idx = int(box.cls[0].item())
        label = model.names[label_idx]
        score = float(box.conf[0])
        bbox = box.xyxy[0].tolist()
        save_detection_object(uid, label, score, bbox)
        detected_labels.append(label)

    processing_time = round(time.time() - start_time, 2)

    return {
        "prediction_uid": uid, 
        "detection_count": len(results[0].boxes),
        "labels": detected_labels,
        "time_took": processing_time
    }

@app.get("/prediction/{uid}")
def get_prediction_by_uid(uid: str, user_id: str = Depends(get_current_user)):
    """
    Get prediction session by uid with all detected objects
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        # Get prediction session
        session = conn.execute("SELECT * FROM prediction_sessions WHERE uid = ?", (uid,)).fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Prediction not found")
        
        if session["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get all detection objects for this prediction
        objects = conn.execute(
            "SELECT * FROM detection_objects WHERE prediction_uid = ?", 
            (uid,)
        ).fetchall()
        
        return {
            "uid": session["uid"],
            "timestamp": session["timestamp"],
            "original_image": session["original_image"],
            "predicted_image": session["predicted_image"],
            "detection_objects": [
                {
                    "id": obj["id"],
                    "label": obj["label"],
                    "score": obj["score"],
                    "box": obj["box"]
                } for obj in objects
            ]
        }

@app.get("/predictions/count")
def get_prediction_count_last_week(user_id: str = Depends(get_current_user)):
    """
    Get total number of predictions made in the last 7 days
    """
    
    one_week_ago = datetime.now() - timedelta(days=7)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
        "SELECT COUNT(*) as count FROM prediction_sessions WHERE timestamp >= ? AND user_id = ?", 
        (one_week_ago.isoformat(), user_id)
        ).fetchone()
        return {"count": row["count"]}

@app.get("/predictions/label/{label}")
def get_predictions_by_label(label: str, user_id: str = Depends(get_current_user)):
    """
    Get prediction sessions containing objects with specified label
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT DISTINCT ps.uid, ps.timestamp
            FROM prediction_sessions ps
            JOIN detection_objects do ON ps.uid = do.prediction_uid
            WHERE do.label = ?  AND user_id = ?
        """, (label,user_id)).fetchall()
        
        return [{"uid": row["uid"], "timestamp": row["timestamp"]} for row in rows]

@app.get("/predictions/score/{min_score}")
def get_predictions_by_score(min_score: float, user_id: str = Depends(get_current_user)):
    """
    Get prediction sessions containing objects with score >= min_score
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT DISTINCT ps.uid, ps.timestamp
            FROM prediction_sessions ps
            JOIN detection_objects do ON ps.uid = do.prediction_uid
            WHERE do.score >= ? AND user_id = ?
        """, (min_score, user_id)).fetchall()
        
        return [{"uid": row["uid"], "timestamp": row["timestamp"]} for row in rows]

@app.get("/image/{type}/{filename}")
def get_image(type: str, filename: str, user_id: str = Depends(get_current_user)):
    """
    Get image by type and filename
    """
    path = os.path.join("uploads", type, filename)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        session = conn.execute(f"""
            SELECT * FROM prediction_sessions 
            WHERE {type}_image = ? AND user_id = ?
        """, (path, user_id)).fetchone()

    if not session:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(path)

@app.get("/prediction/{uid}/image")
def get_prediction_image(uid: str, request: Request, user_id: str = Depends(get_current_user)):
    """
    Get prediction image by uid
    """
    accept = request.headers.get("accept", "")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        session = conn.execute("SELECT predicted_image, user_id  FROM prediction_sessions WHERE uid = ?", (uid,)).fetchone()

    if not session:
            raise HTTPException(status_code=404, detail="Prediction not found")

    if session["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    image_path = session[0]

    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Predicted image file not found")

    elif "image/jpeg" in accept or "image/jpg" in accept:
        return FileResponse(image_path, media_type="image/jpeg")
    else:
        # If the client doesn't accept image, respond with 406 Not Acceptable
        raise HTTPException(status_code=406, detail="Client does not accept an image format")

@app.get("/labels")
def get_labels_last_week(user_id: str = Depends(get_current_user)):
    one_week_ago = datetime.now() - timedelta(days=7)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT DISTINCT do.label
            FROM detection_objects do
            JOIN prediction_sessions ps ON do.prediction_uid = ps.uid
            WHERE ps.timestamp >= ? AND ps.user_id = ?
        """, (one_week_ago.isoformat(), user_id)).fetchall()
        return [row["label"] for row in rows]

@app.delete("/prediction/{uid}")
def delete_prediction(uid: str, user_id: str = Depends(get_current_user)):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        session = conn.execute("SELECT * FROM prediction_sessions WHERE uid = ?", (uid,)).fetchone()

        if not session:
            raise HTTPException(status_code=404, detail="Prediction not found")
        
        if session["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Access denied")

        # Delete images
        for path in [session["original_image"], session["predicted_image"]]:
            if os.path.exists(path):
                os.remove(path)

        # Delete DB entries
        conn.execute("DELETE FROM detection_objects WHERE prediction_uid = ?", (uid,))
        conn.execute("DELETE FROM prediction_sessions WHERE uid = ?", (uid,))

    return {"message": f"Prediction {uid} deleted successfully"}

@app.get("/stats")
def get_prediction_stats():
    one_week_ago = datetime.now() - timedelta(days=7)
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        # Total predictions in the last week
        total_predictions = conn.execute("""
            SELECT COUNT(*) as count
            FROM prediction_sessions
            WHERE timestamp >= ?
        """, (one_week_ago.isoformat(),)).fetchone()["count"]

        # Confidence scores
        scores = conn.execute("""
            SELECT do.score
            FROM detection_objects do
            JOIN prediction_sessions ps ON do.prediction_uid = ps.uid
            WHERE ps.timestamp >= ?
        """, (one_week_ago.isoformat(),)).fetchall()
        score_values = [row["score"] for row in scores]
        avg_score = round(sum(score_values) / len(score_values), 4) if score_values else 0.0

        # Most common labels
        labels = conn.execute("""
            SELECT do.label
            FROM detection_objects do
            JOIN prediction_sessions ps ON do.prediction_uid = ps.uid
            WHERE ps.timestamp >= ?
        """, (one_week_ago.isoformat(),)).fetchall()
        label_counts = Counter(row["label"] for row in labels)

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
