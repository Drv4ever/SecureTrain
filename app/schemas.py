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
