import uuid
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Float, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()

class EvaluationSession(Base):
    __tablename__ = 'evaluation_sessions'

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, default=lambda: str(uuid.uuid4()), unique=True, index=True)
    agent_id = Column(String, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_query = Column(String, nullable=False)
    agent_response = Column(Text, nullable=True)
    rag_context = Column(Text, nullable=True)
    agent_goal = Column(String, nullable=True)
    agent_persona = Column(String, nullable=True)
    user_feedback = Column(Text, nullable=True)
    feedback_sentiment = Column(String, nullable=True)

    # MetricResult ile ilişki
    metric_results = relationship("MetricResult", back_populates="session")


class MetricResult(Base):
    __tablename__ = 'metric_results'

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey('evaluation_sessions.id'), nullable=False)
    metric_name = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=True)

    session = relationship("EvaluationSession", back_populates="metric_results") 