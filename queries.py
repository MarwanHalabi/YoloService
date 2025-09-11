from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from models import PredictionSession, DetectedObjects, User


def save_prediction_session(db: Session, uid: str, original_img: str, predicted_img: str, user_id: int | None):
    row = PredictionSession(uid=uid, original_image=original_img, predicted_image=predicted_img, user_id=user_id)
    db.add(row)
    db.commit()

def query_prediction_by_uid(db: Session, uid: str):
    return db.query(PredictionSession).filter_by(uid=uid).first()

def save_detection_object(db: Session, prediction_uid: str, label: str, score: float, box: str):
    """
    Save detection object to database
    """
    row = DetectedObjects(prediction_uid=prediction_uid, label=label, score=score, box=str(box))
    db.add(row)
    db.commit()


def authenticate_user(db: Session, username: str, password: str):
    return db.query(User).filter_by(username=username, password=password).first()

def count_predictions_by_user(db: Session, user_id: int, timestamp):
    return db.query(PredictionSession).filter(
        PredictionSession.user_id == user_id,
        PredictionSession.timestamp >= timestamp
    ).count()

def query_predictions_by_label(db: Session, label: str, user_id: int):
    return db.query(PredictionSession).join(DetectedObjects).filter(
        DetectedObjects.label == label,
        PredictionSession.user_id == user_id
    ).all()

def query_predictions_by_score(db: Session, min_score: float, user_id: int):
    return db.query(PredictionSession).join(DetectedObjects).filter(
        DetectedObjects.score >= min_score,
        PredictionSession.user_id == user_id
    ).all()

def query_image_by_type_and_filename(db: Session, type: str, filename: str):
    """
    Query image by type and filename
    """
    if type not in ["original", "predicted"]:
        raise ValueError("Invalid image type")
    
    return db.query(PredictionSession).filter(
        getattr(PredictionSession, f"{type}_image") == filename
    ).first()

def query_prediction_image_by_uid(db: Session, uid: int):
    """
    Query prediction image by ID
    """
    return db.query(PredictionSession).filter_by(uid=uid).first()
     
def query_last_Week_labels(db: Session, user_id: int, timestamp):
    """
    Query all labels from DetectedObjects
    """
    
    return db.query(DetectedObjects).join(PredictionSession).filter(
        PredictionSession.user_id == user_id,
        PredictionSession.timestamp >= timestamp
    ).distinct(DetectedObjects.label).all()

def query_get_prediction_by_uid(db: Session, uid: str):
    return db.query(PredictionSession).filter_by(uid=uid).first()

def query_delete_prediction_objects(db: Session, uid: str):
    db.query(DetectedObjects).filter_by(prediction_uid=uid).delete()
    db.commit()

def query_delete_prediction_session(db: Session, uid: str):
    db.query(PredictionSession).filter_by(uid=uid).delete()
    db.commit()

def query_count_predictions_since(db: Session, since: float) -> int:
    return db.query(PredictionSession).filter(PredictionSession.timestamp >= since).count()

def query_get_scores_since(db: Session, since: float) -> list[float]:
    return (
        db.query(DetectedObjects.score)
        .join(PredictionSession, DetectedObjects.prediction_uid == PredictionSession.uid)
        .filter(PredictionSession.timestamp >= since)
        .all()
    )

def query_get_labels_since(db: Session, since: float) -> list[str]:
    return (
        db.query(DetectedObjects.label)
        .join(PredictionSession, DetectedObjects.prediction_uid == PredictionSession.uid)
        .filter(PredictionSession.timestamp >= since)
        .all()
    )

# -----------------
# New high-level helpers expected by the new app structure

def get_user(db: Session, username: str) -> User | None:
    return db.query(User).filter_by(username=username).first()

def create_user(db: Session, username: str, password_hashed: str) -> User:
    user = User(username=username, password=password_hashed)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def save_prediction(db: Session, uid: str, original_path: str, predicted_path: str, username: str | None):
    user_id = None
    if username:
        user = get_user(db, username)
        if user:
            user_id = user.user_id
    save_prediction_session(db, uid, original_path, predicted_path, user_id)

def save_detection(db: Session, uid: str, label: str, score: float, bbox):
    return save_detection_object(db, uid, label, score, str(bbox))

def get_prediction(db: Session, uid: str, username: str) -> PredictionSession | None:
    user = get_user(db, username)
    if not user:
        return None
    return db.query(PredictionSession).filter_by(uid=uid, user_id=user.user_id).first()

def get_detections(db: Session, uid: str):
    return db.query(DetectedObjects).filter_by(prediction_uid=uid).all()

def get_predictions_by_label(db: Session, label: str, username: str):
    user = get_user(db, username)
    if not user:
        return []
    rows = db.query(PredictionSession).join(DetectedObjects).filter(
        DetectedObjects.label == label,
        PredictionSession.user_id == user.user_id,
    ).with_entities(PredictionSession.uid, PredictionSession.timestamp).distinct().all()
    # Return lightweight objects
    return [type('Row', (), {'uid': r[0], 'timestamp': r[1]}) for r in rows]

def get_predictions_by_score(db: Session, min_score: float, username: str):
    user = get_user(db, username)
    if not user:
        return []
    rows = db.query(PredictionSession).join(DetectedObjects).filter(
        DetectedObjects.score >= min_score,
        PredictionSession.user_id == user.user_id,
    ).with_entities(PredictionSession.uid, PredictionSession.timestamp).distinct().all()
    return [type('Row', (), {'uid': r[0], 'timestamp': r[1]}) for r in rows]

def is_image_owned_by_user(db: Session, path: str, username: str) -> bool:
    user = get_user(db, username)
    if not user:
        return False
    exists = db.query(PredictionSession).filter(
        PredictionSession.user_id == user.user_id,
        (PredictionSession.original_image == path) | (PredictionSession.predicted_image == path),
    ).first()
    return exists is not None

def get_predicted_image_path(db: Session, uid: str, username: str) -> str | None:
    session = get_prediction(db, uid, username)
    return session.predicted_image if session else None

def count_predictions_last_week(db: Session, username: str) -> int:
    user = get_user(db, username)
    if not user:
        return 0
    since = datetime.utcnow() - timedelta(days=7)
    return db.query(PredictionSession).filter(
        PredictionSession.user_id == user.user_id,
        PredictionSession.timestamp >= since,
    ).count()

def get_unique_labels_last_week(db: Session, username: str):
    user = get_user(db, username)
    if not user:
        return []
    since = datetime.utcnow() - timedelta(days=7)
    rows = (
        db.query(DetectedObjects.label)
        .join(PredictionSession, DetectedObjects.prediction_uid == PredictionSession.uid)
        .filter(PredictionSession.user_id == user.user_id, PredictionSession.timestamp >= since)
        .distinct()
        .all()
    )
    return [r[0] for r in rows]

def get_prediction_file_paths(db: Session, uid: str, username: str):
    session = get_prediction(db, uid, username)
    if not session:
        return None
    return session.original_image, session.predicted_image

def delete_prediction_and_detections(db: Session, uid: str, username: str):
    session = get_prediction(db, uid, username)
    if not session:
        return
    db.query(DetectedObjects).where(DetectedObjects.prediction_uid == uid).delete()
    db.query(PredictionSession).where(PredictionSession.uid == uid).delete()
    db.commit()

def get_user_prediction_stats(db: Session, username: str):
    user = get_user(db, username)
    if not user:
        return {
            "total_predictions": 0,
            "average_confidence_score": 0.0,
            "most_common_labels": {},
        }
    since = datetime.utcnow() - timedelta(days=7)

    total_predictions = db.query(PredictionSession).filter(
        PredictionSession.user_id == user.user_id,
        PredictionSession.timestamp >= since,
    ).count()

    scores = (
        db.query(DetectedObjects.score)
        .join(PredictionSession, DetectedObjects.prediction_uid == PredictionSession.uid)
        .filter(PredictionSession.user_id == user.user_id, PredictionSession.timestamp >= since)
        .all()
    )
    score_values = [s[0] for s in scores]
    avg_score = round(sum(score_values) / len(score_values), 4) if score_values else 0.0

    labels = (
        db.query(DetectedObjects.label)
        .join(PredictionSession, DetectedObjects.prediction_uid == PredictionSession.uid)
        .filter(PredictionSession.user_id == user.user_id, PredictionSession.timestamp >= since)
        .all()
    )
    from collections import Counter
    label_counts = Counter(l[0] for l in labels)
    return {
        "total_predictions": total_predictions,
        "average_confidence_score": avg_score,
        "most_common_labels": dict(label_counts.most_common()),
    }
