"""Pydantic schemas for API request and response validation."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class EmployeeOut(BaseModel):
    id: int
    name: str
    role: str
    department: str
    susceptibility: Dict[str, float]
    created_at: datetime
    email: Optional[str] = None
    company_id: Optional[int] = None

    class Config:
        from_attributes = True


class SessionStartRequest(BaseModel):
    employee_id: int
    selector: str = Field(default="thompson", pattern="^(thompson|random)$")
    mode: str = Field(default="simulated", pattern="^(simulated|live)$")


class SessionOut(BaseModel):
    id: int
    employee_id: int
    selector: str
    mode: str
    status: str
    bandit_state: Dict[str, dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ScenarioOut(BaseModel):
    id: int
    tactic: str
    sender_name: str
    sender_email: str
    subject: str
    body: str
    indicators: List[str]
    source: Optional[str] = "fallback"
    created_at: datetime

    class Config:
        from_attributes = True


class RoundOut(BaseModel):
    id: int
    session_id: int
    round_number: int
    tactic_selected: str
    scenario: Optional[ScenarioOut] = None
    response: Optional[str] = None
    detection_reward: Optional[float] = None
    safety_score: Optional[float] = None
    bandit_state_after: Optional[Dict[str, dict]] = None
    feedback_text: Optional[str] = None
    feedback_indicators: Optional[List[Dict]] = None
    classifier_score: Optional[float] = None
    presented_at: Optional[datetime] = None
    response_time_seconds: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


class HumanResponseRequest(BaseModel):
    response: str = Field(pattern="^(ignore|report|click|credentials)$")


class BatchRunRequest(BaseModel):
    rounds: int = Field(default=50, ge=1, le=500)


class BatchRunResponse(BaseModel):
    session_id: int
    rounds_run: int
    total_rounds: int
    final_posteriors: Dict[str, float]
    cumulative_reward: float


class HistoryPoint(BaseModel):
    round_number: int
    tactic: str
    response: Optional[str]
    detection_reward: Optional[float]
    safety_score: Optional[float]
    cumulative_reward: float


class SessionStateResponse(BaseModel):
    session_id: int
    employee_id: int
    employee_name: str
    selector: str
    mode: str
    status: str
    posteriors: Dict[str, float]
    bandit_state: Dict[str, dict]
    total_rounds: int
    cumulative_reward: float
    history: List[HistoryPoint]
    baseline_cumulative: List[float]  # Random baseline comparison points


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str
    role: str = Field(default="employee", pattern="^(employee|client_admin)$")
    company_id: Optional[int] = None
    department: str = "General"
    employee_role: str = "Employee"


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    company_id: int
    user_id: int


class AdminSettingsRequest(BaseModel):
    training_frequency_days: int = Field(default=7, ge=1, le=365)
    active_tactics: List[str] = Field(default_factory=lambda: ["urgency", "authority", "invoice", "credential"])


class AssignmentCreateRequest(BaseModel):
    employee_id: int
    title: str = "Security awareness training"
    total_rounds: int = Field(default=10, ge=1, le=100)
    active_tactics: List[str] = Field(default_factory=lambda: ["urgency", "authority", "invoice", "credential"])
    scheduled_at: Optional[datetime] = None


class AssignmentResponse(BaseModel):
    id: int
    employee_id: int
    title: str
    total_rounds: int
    completed_rounds: int
    active_tactics: List[str]
    scheduled_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    status: str
    report: Optional[Dict] = None


class CompanySettingsOut(BaseModel):
    company_id: int
    company_name: str
    training_frequency_days: int
    active_tactics: List[str]
