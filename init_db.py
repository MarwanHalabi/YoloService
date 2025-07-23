from sqlalchemy.orm import Session
from models import User
import uuid

def create_initial_users(db: Session):
    default_users = [("admin", "admin"), ("admin2", "admin2")]

    for username, password in default_users:
        existing = db.query(User).filter_by(username=username).first()
        if not existing:
            user = User(user_id=str(uuid.uuid4()), username=username, password=password)
            db.add(user)

    db.commit()
