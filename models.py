from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float as Real
from sqlalchemy.orm import relationship 
from datetime import datetime
from db import Base


class User(Base):
    __tablename__ = 'users'
    
    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    
    # Relationships
    prediction_sessions = relationship("PredictionSession", back_populates="user")


class PredictionSession(Base):
    __tablename__ = 'prediction_sessions'
    
    uid = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    original_image = Column(String)
    predicted_image = Column(String)
    user_id = Column(Integer, ForeignKey('users.user_id'))

    # Relationships
    user = relationship("User", back_populates="prediction_sessions")
    detected_objects = relationship("DetectedObjects", back_populates="prediction_session")

class DetectedObjects(Base):
    __tablename__ = 'detected_objects'
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    label = Column(String)
    box = Column(String)
    score = Column(Real)
    prediction_uid = Column(String, ForeignKey('prediction_sessions.uid'))

    # Relationships
    prediction_session = relationship("PredictionSession",back_populates="detected_objects")
