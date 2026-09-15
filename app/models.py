"""SQLAlchemy relational models: Employee, Session, Scenario, Round."""

from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db import Base


class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    settings = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    employees = relationship("Employee", back_populates="company")
    admins = relationship("ClientAdmin", back_populates="company")


class ClientAdmin(Base):
    __tablename__ = "client_admins"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(50), default="client_admin", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    company = relationship("Company", back_populates="admins")


class Employee(Base):
    """Represents a synthetic or live employee with a susceptibility profile."""

    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)
    role = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    susceptibility = Column(JSON, nullable=False)  # {"urgency": 0.2, "authority": 0.3, "invoice": 0.8, "credential": 0.4}
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    company = relationship("Company", back_populates="employees")

    sessions = relationship("Session", back_populates="employee", cascade="all, delete-orphan")
    assignments = relationship("TrainingAssignment", back_populates="employee", cascade="all, delete-orphan")


class TrainingAssignment(Base):
    __tablename__ = "training_assignments"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    created_by_admin_id = Column(Integer, ForeignKey("client_admins.id"), nullable=True)
    title = Column(String(200), nullable=False, default="Security awareness training")
    total_rounds = Column(Integer, nullable=False, default=10)
    active_tactics = Column(JSON, nullable=False, default=list)
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(30), nullable=False, default="scheduled")
    notification_seen = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company")
    employee = relationship("Employee", back_populates="assignments")
    sessions = relationship("Session", back_populates="assignment", cascade="all, delete-orphan")
    report = relationship("TrainingReport", back_populates="assignment", uselist=False, cascade="all, delete-orphan")


class Session(Base):
    """Represents a multi-round training session for an employee."""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    assignment_id = Column(Integer, ForeignKey("training_assignments.id"), nullable=True, index=True)
    selector = Column(String(50), default="thompson", nullable=False)  # "thompson" | "random"
    mode = Column(String(50), default="simulated", nullable=False)      # "simulated" | "live"
    status = Column(String(50), default="active", nullable=False)       # "active" | "completed"
    bandit_state = Column(JSON, nullable=False)                         # Alpha, Beta, Pulls per arm
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="sessions")
    assignment = relationship("TrainingAssignment", back_populates="sessions")
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
    source = Column(String(20), nullable=False, default="fallback")
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
    feedback_text = Column(Text, nullable=True)
    classifier_score = Column(Float, nullable=True)
    presented_at = Column(DateTime, nullable=True)
    response_time_seconds = Column(Float, nullable=True)
    bandit_state_after = Column(JSON, nullable=True)              # Snapshot after update
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("Session", back_populates="rounds")
    scenario = relationship("Scenario", back_populates="rounds")


class TrainingReport(Base):
    __tablename__ = "training_reports"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("training_assignments.id"), nullable=False, unique=True, index=True)
    summary = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    assignment = relationship("TrainingAssignment", back_populates="report")
