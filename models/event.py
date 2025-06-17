# models/event.py
from sqlalchemy import Column, String, Boolean, Integer, Float, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
import datetime
import uuid

Base = declarative_base()

class Event(Base):
    __tablename__ = 'events'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    is_outdoor = Column(Boolean, default=False)
    priority = Column(Integer, default=3)
    flexibility = Column(Float, default=0.5)
    weather_risk = Column(Float, default=0.0)
    suggested_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
