from sqlalchemy.orm import Session
from models import User
import bcrypt

def create_initial_users(db: Session):
    default_users = [("admin", "admin"), ("admin2", "admin2")]

    for username, password in default_users:
        existing = db.query(User).filter_by(username=username).first()
        if not existing:
            # Store bcrypt-hashed passwords for compatibility with auth
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            user = User(username=username, password=hashed)
            db.add(user)

    db.commit()
