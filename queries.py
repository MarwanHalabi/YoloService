from sqlalchemy.orm import Session
from models import PredictionSession, DetectedObjects, User, DetectionObject


def save_prediction_session(db: Session, uid: str, original_img: str, predicted_img: str, user_id: str):
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
    return db.query(PredictionSession).filter_by(id=uid).first()
     
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
    db.query(DetectionObject).filter_by(prediction_uid=uid).delete()

def query_delete_prediction_session(db: Session, uid: str):
    db.query(PredictionSession).filter_by(uid=uid).delete()

def query_count_predictions_since(db: Session, since: datetime) -> int:
    return db.query(PredictionSession).filter(PredictionSession.timestamp >= since).count()

def query_get_scores_since(db: Session, since: datetime) -> list[float]:
    return (
        db.query(DetectionObject.score)
        .join(PredictionSession, DetectionObject.prediction_uid == PredictionSession.uid)
        .filter(PredictionSession.timestamp >= since)
        .all()
    )

def query_get_labels_since(db: Session, since: datetime) -> list[str]:
    return (
        db.query(DetectionObject.label)
        .join(PredictionSession, DetectionObject.prediction_uid == PredictionSession.uid)
        .filter(PredictionSession.timestamp >= since)
        .all()
    )
