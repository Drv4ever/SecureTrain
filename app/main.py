"""FastAPI application for Adaptive AI Security Awareness Trainer.

All API routes registered here in a single service:
- POST /api/employees/seed
- GET  /api/employees
- POST /api/session/start
- POST /api/session/{id}/round
- PATCH /api/session/{id}/round/{n}
- GET  /api/session/{id}/state
- POST /api/session/{id}/batch
- GET  /healthz
"""

import os
import random
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.bandit import ThompsonSampler
from app.db import get_db, init_db
from app.llm import generate_scenario
from app.models import Employee, Round, Scenario, Session as DbSession
from app.random_selector import RandomSelector
from app.reward import TACTICS, get_detection_reward, get_safety_score
from app.schemas import (
    BatchRunRequest,
    BatchRunResponse,
    EmployeeOut,
    HistoryPoint,
    HumanResponseRequest,
    RoundOut,
    ScenarioOut,
    SessionOut,
    SessionStartRequest,
    SessionStateResponse,
)
from app.simulator import SimulatedEmployee, sample_response
from data.seed_employees import seed_employees

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Adaptive AI Security Awareness Trainer", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


def make_initial_bandit_state() -> Dict[str, dict]:
    return {
        arm: {"alpha": 1.0, "beta": 1.0, "pulls": 0, "mean": 0.5}
        for arm in TACTICS
    }


# ---------- API Routes ----------


@app.get("/healthz")
def healthz(db: Session = Depends(get_db)):
    return {"status": "ok", "service": "Adaptive AI Security Awareness Trainer"}


@app.post("/api/employees/seed", response_model=List[EmployeeOut])
def api_seed_employees(db: Session = Depends(get_db)):
    """Seed default employees into SQLite database."""
    employees = seed_employees(db, force=True)
    return employees


@app.get("/api/employees", response_model=List[EmployeeOut])
def api_list_employees(db: Session = Depends(get_db)):
    """List all available employees (auto-seeds if database is empty)."""
    employees = db.query(Employee).all()
    if not employees:
        employees = seed_employees(db, force=False)
    return employees


@app.post("/api/session/start", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def api_start_session(req: SessionStartRequest, db: Session = Depends(get_db)):
    """Start a new training session for an employee."""
    employee = db.query(Employee).filter(Employee.id == req.employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail=f"Employee {req.employee_id} not found")

    session = DbSession(
        employee_id=employee.id,
        selector=req.selector,
        mode=req.mode,
        status="active",
        bandit_state=make_initial_bandit_state(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@app.post("/api/session/{session_id}/round", response_model=RoundOut)
def api_run_round(session_id: int, db: Session = Depends(get_db)):
    """Run or prepare one training round."""
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    employee = session.employee
    round_no = len(session.rounds) + 1

    # Check if there is already a pending live round
    pending = (
        db.query(Round)
        .filter(Round.session_id == session_id, Round.response == None)  # noqa: E711
        .first()
    )
    if pending and session.mode == "live":
        return pending

    # 1. Selector chooses an arm (Thompson Sampling or Random Baseline)
    if session.selector == "thompson":
        sampler = ThompsonSampler.from_state(session.bandit_state)
    else:
        sampler = RandomSelector.from_state(session.bandit_state)

    chosen_tactic, _ = sampler.select()

    # 2. Create scenario record (Groq LLM with template fallback)
    scen_data = generate_scenario(
        tactic=chosen_tactic,
        role=employee.role,
        department=employee.department,
        employee_name=employee.name,
    )
    scenario = Scenario(
        tactic=chosen_tactic,
        sender_name=scen_data["sender_name"],
        sender_email=scen_data["sender_email"],
        subject=scen_data["subject"],
        body=scen_data["body"],
        indicators=scen_data["indicators"],
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)

    # 3. Handle Live vs Simulated mode
    if session.mode == "live":
        # Live human mode: Create pending round and return for user response
        round_rec = Round(
            session_id=session.id,
            round_number=round_no,
            tactic_selected=chosen_tactic,
            scenario_id=scenario.id,
            response=None,
            detection_reward=None,
            safety_score=None,
            bandit_state_after=session.bandit_state,
        )
        db.add(round_rec)
        db.commit()
        db.refresh(round_rec)
        return round_rec

    # Simulated mode: Sample response from employee model
    sim_emp = SimulatedEmployee(
        name=employee.name,
        role=employee.role,
        department=employee.department,
        susceptibility=employee.susceptibility,
    )
    resp = sample_response(sim_emp, chosen_tactic)
    det_reward = get_detection_reward(resp)
    safe_score = get_safety_score(resp)

    # Update sampler & session bandit state
    sampler.update(chosen_tactic, det_reward)
    session.bandit_state = sampler.get_state()

    round_rec = Round(
        session_id=session.id,
        round_number=round_no,
        tactic_selected=chosen_tactic,
        scenario_id=scenario.id,
        response=resp,
        detection_reward=det_reward,
        safety_score=safe_score,
        bandit_state_after=sampler.get_state(),
    )
    db.add(round_rec)
    db.commit()
    db.refresh(round_rec)
    return round_rec


@app.patch("/api/session/{session_id}/round/{round_number}", response_model=RoundOut)
def api_complete_human_round(
    session_id: int,
    round_number: int,
    req: HumanResponseRequest,
    db: Session = Depends(get_db),
):
    """Complete a pending human-mode round with user response."""
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    round_rec = (
        db.query(Round)
        .filter(Round.session_id == session_id, Round.round_number == round_number)
        .first()
    )
    if not round_rec:
        raise HTTPException(status_code=404, detail="Round not found")

    if round_rec.response is not None:
        raise HTTPException(status_code=400, detail="Round already completed")

    resp = req.response
    det_reward = get_detection_reward(resp)
    safe_score = get_safety_score(resp)

    # Update bandit
    if session.selector == "thompson":
        sampler = ThompsonSampler.from_state(session.bandit_state)
    else:
        sampler = RandomSelector.from_state(session.bandit_state)

    sampler.update(round_rec.tactic_selected, det_reward)
    session.bandit_state = sampler.get_state()

    round_rec.response = resp
    round_rec.detection_reward = det_reward
    round_rec.safety_score = safe_score
    round_rec.bandit_state_after = sampler.get_state()

    db.commit()
    db.refresh(round_rec)
    return round_rec


@app.post("/api/session/{session_id}/batch", response_model=BatchRunResponse)
def api_run_batch(
    session_id: int,
    req: BatchRunRequest,
    db: Session = Depends(get_db),
):
    """Run multiple simulated rounds rapidly using fast template scenarios."""
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    employee = session.employee
    sim_emp = SimulatedEmployee(
        name=employee.name,
        role=employee.role,
        department=employee.department,
        susceptibility=employee.susceptibility,
    )

    if session.selector == "thompson":
        sampler = ThompsonSampler.from_state(session.bandit_state)
    else:
        sampler = RandomSelector.from_state(session.bandit_state)

    current_round_no = len(session.rounds)
    for _ in range(req.rounds):
        current_round_no += 1
        chosen_tactic, _ = sampler.select()
        resp = sample_response(sim_emp, chosen_tactic)
        det_reward = get_detection_reward(resp)
        safe_score = get_safety_score(resp)
        sampler.update(chosen_tactic, det_reward)

        round_rec = Round(
            session_id=session.id,
            round_number=current_round_no,
            tactic_selected=chosen_tactic,
            scenario_id=None,
            response=resp,
            detection_reward=det_reward,
            safety_score=safe_score,
            bandit_state_after=sampler.get_state(),
        )
        db.add(round_rec)

    session.bandit_state = sampler.get_state()
    db.commit()

    all_completed = (
        db.query(Round)
        .filter(Round.session_id == session_id, Round.detection_reward != None)  # noqa: E711
        .all()
    )
    cum_reward = sum(r.detection_reward for r in all_completed if r.detection_reward)

    return BatchRunResponse(
        session_id=session.id,
        rounds_run=req.rounds,
        total_rounds=len(all_completed),
        final_posteriors=sampler.posterior_means(),
        cumulative_reward=round(cum_reward, 2),
    )


@app.get("/api/session/{session_id}/state", response_model=SessionStateResponse)
def api_get_session_state(session_id: int, db: Session = Depends(get_db)):
    """Return bandit posteriors, history points, and Random baseline comparison curve."""
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    employee = session.employee
    rounds = (
        db.query(Round)
        .filter(Round.session_id == session_id, Round.response != None)  # noqa: E711
        .order_by(Round.round_number.asc())
        .all()
    )

    history: List[HistoryPoint] = []
    cum = 0.0
    for r in rounds:
        r_val = r.detection_reward or 0.0
        cum += r_val
        history.append(
            HistoryPoint(
                round_number=r.round_number,
                tactic=r.tactic_selected,
                response=r.response,
                detection_reward=r.detection_reward,
                safety_score=r.safety_score,
                cumulative_reward=round(cum, 2),
            )
        )

    # Compute expected random baseline curve for comparison on the chart
    # E[reward_random] = mean of expected rewards across the 4 tactics
    sim_emp = SimulatedEmployee(
        name=employee.name,
        role=employee.role,
        department=employee.department,
        susceptibility=employee.susceptibility,
    )
    expected_rewards_per_tactic = [
        sum(
            prob * get_detection_reward(resp_name)
            for resp_name, prob in from_probs.items()
        )
        for t in TACTICS
        for from_probs in [
            {
                "ignore": 0.4 * (1.0 - sim_emp.get_susceptibility(t)),
                "report": 0.6 * (1.0 - sim_emp.get_susceptibility(t)),
                "click": 0.5 * sim_emp.get_susceptibility(t),
                "credentials": 0.5 * sim_emp.get_susceptibility(t),
            }
        ]
    ]
    mean_random_reward = sum(expected_rewards_per_tactic) / len(expected_rewards_per_tactic)
    baseline_cum = [round((i + 1) * mean_random_reward, 2) for i in range(len(rounds))]

    posteriors = {
        arm: float(session.bandit_state[arm]["mean"])
        for arm in TACTICS
        if arm in session.bandit_state
    }

    return SessionStateResponse(
        session_id=session.id,
        employee_id=employee.id,
        employee_name=employee.name,
        selector=session.selector,
        mode=session.mode,
        status=session.status,
        posteriors=posteriors,
        bandit_state=session.bandit_state,
        total_rounds=len(rounds),
        cumulative_reward=round(cum, 2),
        history=history,
        baseline_cumulative=baseline_cum,
    )


# ---------- Serve Frontend Dashboard ----------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Adaptive AI Security Awareness Trainer API is running. Build static UI in /static."}
