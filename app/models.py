"""SQLAlchemy relational models: Employee, Session, Scenario, Round."""

from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db import Base


class Employee(Base):
    """Represents a synthetic or live employee with a susceptibility profile."""

    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    role = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    susceptibility = Column(JSON, nullable=False)  # {"urgency": 0.2, "authority": 0.3, "invoice": 0.8, "credential": 0.4}
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sessions = relationship("Session", back_populates="employee", cascade="all, delete-orphan")


class Session(Base):
    """Represents a multi-round training session for an employee."""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    selector = Column(String(50), default="thompson", nullable=False)  # "thompson" | "random"
    mode = Column(String(50), default="simulated", nullable=False)      # "simulated" | "live"
    status = Column(String(50), default="active", nullable=False)       # "active" | "completed"
    bandit_state = Column(JSON, nullable=False)                         # Alpha, Beta, Pulls per arm
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="sessions")
    rounds = relationship("Round", back_populates="session", cascade="all, delete-orphan", order_by="Round.round_number")


class Scenario(Base):
    """Represents a generated phishing scenario."""

    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, index=True)
    tactic = Column(String(50), nullable=False)
    sender_name = Column(String(100), nullable=False)
    sender_email = Column(String(150), nullable=False)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    indicators = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    rounds = relationship("Round", back_populates="scenario")


class Round(Base):
    """Represents one round in a training session."""

    __tablename__ = "rounds"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    round_number = Column(Integer, nullable=False)
    tactic_selected = Column(String(50), nullable=False)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=True)
    response = Column(String(50), nullable=True)                  # "ignore", "report", "click", "credentials"
    detection_reward = Column(Float, nullable=True)               # [0.0, 1.0] drives bandit
    safety_score = Column(Float, nullable=True)                   # [0.0, 1.0] reported only
    bandit_state_after = Column(JSON, nullable=True)              # Snapshot after update
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("Session", back_populates="rounds")
    scenario = relationship("Scenario", back_populates="rounds")
