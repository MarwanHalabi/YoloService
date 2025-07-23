from sqlalchemy.orm import Session
from models import PredictionSession, DetectedObjects, User


def save_prediction_session(db: Session, uid: str, original_img: str, predicted_img: str):
    row = PredictionSession(uid=uid, original_image=original_img, predicted_image=predicted_img)
    db.add(row)
    db.commit()

def get_prediction_by_uid(db: Session, uid: str):
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
