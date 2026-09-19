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
import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.app.bandit import ThompsonSampler
from backend.app.db import get_db, init_db, SessionLocal
from llm.service import generate_scenario, generate_feedback, generate_report_analysis
from backend.app.models import Company, ClientAdmin, Employee, Round, Scenario, Session as DbSession, TrainingAssignment, TrainingReport
from backend.app.auth import create_token, hash_password, verify_password, require_role, optional_user
from backend.app.classifier import score_response
from backend.app.random_selector import RandomSelector
from backend.app.reward import TACTICS, get_detection_reward, get_safety_score
from backend.app.config import benchmark_config
from backend.app.schemas import (
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
    RegisterRequest, LoginRequest, AuthResponse, AdminSettingsRequest, AssignmentCreateRequest, AssignmentResponse,
)
from backend.app.simulator import SimulatedEmployee, sample_response
from data.seed_employees import seed_employees

BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"

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
    from backend.app.classifier import load_classifier
    load_classifier()
    try:
        from rag.retriever import get_retriever
        get_retriever()
    except Exception as exc:
        print(f"[Startup Warning] RAG retriever init failed: {exc}")
    db = next(get_db())
    try:
        company = db.query(Company).first()
        if not company:
            company_name = os.environ.get("COMPANY_NAME", "").strip()
            if not company_name:
                raise RuntimeError("COMPANY_NAME must be set before creating the first company")
            company = Company(name=company_name, settings={"training_frequency_days": 7, "active_tactics": list(TACTICS)})
            db.add(company); db.commit(); db.refresh(company)
        for employee in db.query(Employee).filter(Employee.company_id == None).all():  # noqa: E711
            employee.company_id = company.id
        db.commit()
    finally:
        db.close()


@app.get("/api/classifier/info")
def api_classifier_info(user=Depends(require_role("client_admin", "super_admin"))):
    """Return model health metrics and diagnostics for administrators."""
    from backend.app.classifier import get_classifier_info
    return get_classifier_info()


@app.post("/auth/register", response_model=AuthResponse, status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == req.company_id).first() if req.company_id else db.query(Company).first()
    if not company: raise HTTPException(400, "Company not found")
    if db.query(Employee).filter(Employee.email == req.email).first() or db.query(ClientAdmin).filter(ClientAdmin.email == req.email).first():
        raise HTTPException(409, "Email already registered")
    if req.role == "client_admin":
        user = ClientAdmin(company_id=company.id, email=req.email, name=req.name, hashed_password=hash_password(req.password))
        db.add(user); db.commit(); db.refresh(user); user_id = user.id
    else:
        user = Employee(company_id=company.id, email=req.email, name=req.name, role=req.employee_role, department=req.department,
                        susceptibility={t: 0.5 for t in TACTICS}, hashed_password=hash_password(req.password))
        db.add(user); db.commit(); db.refresh(user); user_id = user.id
    return AuthResponse(access_token=create_token({"sub": str(user_id), "role": req.role, "company_id": company.id}), role=req.role, company_id=company.id, user_id=user_id)


@app.post("/auth/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.email == req.email).first()
    admin = db.query(ClientAdmin).filter(ClientAdmin.email == req.email).first()
    user, role = (employee, "employee") if employee else (admin, "client_admin")
    if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password): raise HTTPException(401, "Invalid credentials")
    return AuthResponse(access_token=create_token({"sub": str(user.id), "role": role, "company_id": user.company_id}), role=role, company_id=user.company_id, user_id=user.id)


@app.get("/employee/me")
def employee_me(user=Depends(require_role("employee")), db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == int(user["sub"]), Employee.company_id == user["company_id"]).first()
    if not employee: raise HTTPException(404, "Employee not found")
    sessions = db.query(DbSession).filter(DbSession.employee_id == employee.id).all()
    latest = sessions[-1].bandit_state if sessions else {t: {"mean": .5} for t in TACTICS}
    return {"id": employee.id, "name": employee.name, "email": employee.email, "role": employee.role, "department": employee.department, "posteriors": {t: v.get("mean", .5) for t,v in latest.items()}}


def make_initial_bandit_state() -> Dict[str, dict]:
    return {
        arm: {"alpha": 1.0, "beta": 1.0, "pulls": 0, "mean": 0.5}
        for arm in TACTICS
    }


def assignment_payload(assignment: TrainingAssignment) -> dict:
    sessions = list(assignment.sessions or [])
    session = sessions[-1] if sessions else None
    completed = sum(1 for item in sessions for r in item.rounds if r.response is not None)
    return {"id": assignment.id, "employee_id": assignment.employee_id, "title": assignment.title,
            "total_rounds": assignment.total_rounds, "completed_rounds": completed,
            "active_tactics": assignment.active_tactics, "scheduled_at": assignment.scheduled_at,
            "started_at": assignment.started_at, "completed_at": assignment.completed_at,
            "status": assignment.status, "report": assignment.report.summary if assignment.report else None}


def build_assignment_report(assignment: TrainingAssignment, session: DbSession) -> dict:
    rounds = [r for r in session.rounds if r.response is not None]
    by_tactic = {}
    for item in rounds:
        stats = by_tactic.setdefault(item.tactic_selected, {"rounds": 0, "reports": 0, "clicks": 0, "ignores": 0, "credentials": 0, "safety_total": 0.0})
        stats["rounds"] += 1
        response_key = "credentials" if item.response == "credentials" else item.response + "s"
        stats[response_key] += 1
        stats["safety_total"] += item.safety_score or 0
    for stats in by_tactic.values():
        stats["average_safety"] = round(stats.pop("safety_total") / stats["rounds"], 3) if stats["rounds"] else 0
    safety = sum(r.safety_score or 0 for r in rounds) / len(rounds) if rounds else 0
    detection = sum(r.detection_reward or 0 for r in rounds) / len(rounds) if rounds else 0
    weakest = min(by_tactic.items(), key=lambda x: x[1]["average_safety"])[0] if by_tactic else None
    midpoint = max(1, len(rounds) // 2)
    first, second = rounds[:midpoint], rounds[midpoint:]
    first_score = sum(r.safety_score or 0 for r in first) / len(first) if first else 0
    second_score = sum(r.safety_score or 0 for r in second) / len(second) if second else first_score
    return {"assignment_id": assignment.id, "employee_id": assignment.employee_id, "rounds_completed": len(rounds),
            "total_rounds": assignment.total_rounds, "average_safety_score": round(safety, 3),
            "average_detection_reward": round(detection, 3), "improvement": round(second_score - first_score, 3),
            "weakest_tactic": weakest, "tactic_analysis": by_tactic,
            "recommendation": generate_report_analysis([
                {"round_number": r.round_number, "tactic": r.tactic_selected, "response": r.response,
                 "safety_score": r.safety_score or 0, "feedback_text": r.feedback_text} for r in rounds
            ], assignment.employee.name if assignment.employee else "Employee")}


def finalize_assignment(assignment: TrainingAssignment, session: DbSession, db: Session):
    completed = sum(1 for item in (assignment.sessions or []) for r in item.rounds if r.response is not None)
    if completed >= assignment.total_rounds:
        assignment.status = "completed"; assignment.completed_at = datetime.utcnow()
        session.status = "completed"
        if not assignment.report:
            db.add(TrainingReport(assignment_id=assignment.id, summary=build_assignment_report(assignment, session)))


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
def api_list_employees(db: Session = Depends(get_db), user=Depends(optional_user)):
    """List all available employees (auto-seeds if database is empty)."""
    query = db.query(Employee)
    if user and user.get("role") != "super_admin": query = query.filter(Employee.company_id == user.get("company_id"))
    employees = query.all()
    if not employees:
        employees = seed_employees(db, force=False)
        if user and user.get("role") != "super_admin":
            employees = [employee for employee in employees if employee.company_id == user.get("company_id")]
    return employees


@app.post("/api/session/start", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def api_start_session(req: SessionStartRequest, db: Session = Depends(get_db), user=Depends(optional_user)):
    """Start a new training session for an employee."""
    employee = db.query(Employee).filter(Employee.id == req.employee_id).first()
    if not employee or (user and user.get("role") != "super_admin" and employee.company_id != user.get("company_id")):
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
def api_run_round(session_id: int, db: Session = Depends(get_db), user=Depends(optional_user)):
    """Run or prepare one training round."""
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session or (user and user.get("role") != "super_admin" and session.employee.company_id != user.get("company_id")):
        raise HTTPException(status_code=404, detail="Session not found")

    employee = session.employee
    assignment = session.assignment

    # Check if there is already a pending live round
    pending = (
        db.query(Round)
        .filter(Round.session_id == session_id, Round.response == None)  # noqa: E711
        .first()
    )
    if pending and session.mode == "live":
        # Recover from an earlier concurrent request that created a second
        # record for a round number which was already completed. Without this
        # check the stale pending email is returned forever.
        duplicate_completed = (db.query(Round)
                               .filter(Round.session_id == session_id,
                                       Round.round_number == pending.round_number,
                                       Round.response != None,  # noqa: E711
                                       Round.id != pending.id)
                               .first())
        if duplicate_completed:
            db.delete(pending)
            db.commit()
        else:
            return pending

    round_no = (db.query(Round.round_number)
                .filter(Round.session_id == session_id)
                .order_by(Round.round_number.desc()).first())
    round_no = (round_no[0] if round_no else 0) + 1
    if assignment and assignment.status == "completed":
        raise HTTPException(400, "Training assignment is already complete")
    completed_count = (db.query(Round).join(DbSession, Round.session_id == DbSession.id)
                       .filter(DbSession.assignment_id == assignment.id, Round.response != None)  # noqa: E711
                       .count()) if assignment else 0
    if assignment and completed_count >= assignment.total_rounds:
        finalize_assignment(assignment, session, db)
        db.commit()
        raise HTTPException(400, "Training assignment round limit reached")

    # 1. Selector chooses an arm (Thompson Sampling or Random Baseline)
    if session.selector == "thompson":
        sampler = ThompsonSampler.from_state(session.bandit_state, arms=tuple(assignment.active_tactics) if assignment else TACTICS)
    else:
        sampler = RandomSelector.from_state(session.bandit_state, arms=tuple(assignment.active_tactics) if assignment else TACTICS)

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
        source=scen_data.get("source", "fallback"),
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
            presented_at=datetime.utcnow(),
        )
        db.add(round_rec)
        db.commit()
        db.refresh(round_rec)
        # Access the relationship before returning so direct endpoint reuse
        # (employee training start) includes the generated email payload.
        _ = round_rec.scenario
        return round_rec

    # Simulated mode: Sample response from employee model
    sim_emp = SimulatedEmployee(
        name=employee.name,
        role=employee.role,
        department=employee.department,
        susceptibility=employee.susceptibility,
    )
    resp = sample_response(sim_emp, chosen_tactic)
    prev_round = (
        db.query(Round)
        .filter(Round.session_id == session.id, Round.tactic_selected == chosen_tactic, Round.response != None)  # noqa: E711
        .order_by(Round.round_number.desc())
        .first()
    )
    last_resp = prev_round.response if prev_round else "none"
    tactic_times_seen = (
        db.query(Round)
        .filter(Round.session_id == session.id, Round.tactic_selected == chosen_tactic, Round.response != None)  # noqa: E711
        .count()
    )
    det_reward = score_response(
        chosen_tactic,
        session.employee.role,
        session.employee.department,
        last_response=last_resp,
        times_seen=tactic_times_seen,
        round_no=round_no,
        current_response=resp,
    )
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
        presented_at=datetime.utcnow(),
    )
    db.add(round_rec)
    db.commit()
    db.refresh(round_rec)
    _ = round_rec.scenario
    return round_rec


@app.patch("/api/session/{session_id}/round/{round_number}", response_model=RoundOut)
def api_complete_human_round(
    session_id: int,
    round_number: int,
    req: HumanResponseRequest,
    db: Session = Depends(get_db),
    user=Depends(optional_user),
):
    """Complete a pending human-mode round with user response."""
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session or (user and user.get("role") != "super_admin" and session.employee.company_id != user.get("company_id")):
        raise HTTPException(status_code=404, detail="Session not found")

    round_rec = (
        db.query(Round)
        .filter(Round.session_id == session_id, Round.round_number == round_number)
        .first()
    )
    if not round_rec:
        raise HTTPException(status_code=404, detail="Round not found")

    if round_rec.response is not None:
        # Browsers can deliver a second click while the first request is still
        # being processed. The round has one authoritative answer; return it
        # idempotently instead of turning the follow-up click into a 400.
        return round_rec

    resp = req.response
    prev_round = (
        db.query(Round)
        .filter(Round.session_id == session_id, Round.tactic_selected == round_rec.tactic_selected, Round.response != None)  # noqa: E711
        .order_by(Round.round_number.desc())
        .first()
    )
    last_resp = prev_round.response if prev_round else "none"
    tactic_times_seen = (
        db.query(Round)
        .filter(Round.session_id == session_id, Round.tactic_selected == round_rec.tactic_selected, Round.response != None)  # noqa: E711
        .count()
    )
    classifier = score_response(
        round_rec.tactic_selected,
        session.employee.role,
        session.employee.department,
        last_response=last_resp,
        times_seen=tactic_times_seen,
        round_no=round_rec.round_number,
        current_response=resp,
    )
    det_reward = get_detection_reward(resp, classifier)
    safe_score = get_safety_score(resp)

    # Update bandit
    if session.selector == "thompson":
        sampler = ThompsonSampler.from_state(session.bandit_state)
    else:
        sampler = RandomSelector.from_state(session.bandit_state)

    sampler.update(round_rec.tactic_selected, det_reward)
    session.bandit_state = sampler.get_state()

    round_rec.response = resp
    round_rec.response_time_seconds = max(0.0, (datetime.utcnow() - (round_rec.presented_at or datetime.utcnow())).total_seconds())
    round_rec.detection_reward = det_reward
    round_rec.classifier_score = classifier
    round_rec.safety_score = safe_score
    if round_rec.scenario:
        try:
            from rag.retriever import get_retriever
            _retriever = get_retriever()
        except Exception:
            _retriever = None
        fb_text, fb_indicators = generate_feedback(
            round_rec.tactic_selected, resp, round_rec.scenario.indicators, retriever=_retriever
        )
        round_rec.feedback_text = fb_text
        round_rec.feedback_indicators = [
            {"title": d.get("title"), "source": d.get("source"), "snippet": d.get("snippet", d.get("text", ""))[:200]}
            for d in (fb_indicators or [])
        ]
    round_rec.bandit_state_after = sampler.get_state()
    if session.assignment:
        finalize_assignment(session.assignment, session, db)

    db.commit()
    db.refresh(round_rec)
    return round_rec


@app.get("/employee/history")
def employee_history(user=Depends(require_role("employee")), db: Session = Depends(get_db)):
    rounds = (db.query(Round).join(DbSession).filter(DbSession.employee_id == int(user["sub"]),
             DbSession.employee.has(company_id=user["company_id"]), Round.response != None)
             .order_by(Round.created_at.asc()).all())  # noqa: E711
    return [{"id": r.id, "round_number": r.round_number, "tactic": r.tactic_selected, "response": r.response,
             "detection_reward": r.detection_reward, "safety_score": r.safety_score, "feedback_text": r.feedback_text,
             "response_time_seconds": r.response_time_seconds, "created_at": r.created_at} for r in rounds]


@app.post("/admin/training-assignments", response_model=AssignmentResponse, status_code=201)
def create_training_assignment(req: AssignmentCreateRequest, user=Depends(require_role("client_admin", "super_admin")), db: Session = Depends(get_db)):
    if any(t not in TACTICS for t in req.active_tactics) or not req.active_tactics:
        raise HTTPException(400, "active_tactics must contain valid tactic names")
    employee_query = db.query(Employee).filter(Employee.id == req.employee_id)
    if user.get("role") != "super_admin": employee_query = employee_query.filter(Employee.company_id == user["company_id"])
    employee = employee_query.first()
    if not employee: raise HTTPException(404, "Employee not found")
    assignment = TrainingAssignment(company_id=employee.company_id, employee_id=employee.id,
                                    created_by_admin_id=int(user["sub"]) if user.get("role") == "client_admin" else None,
                                    title=req.title, total_rounds=req.total_rounds,
                                    active_tactics=req.active_tactics, scheduled_at=req.scheduled_at,
                                    status="scheduled")
    db.add(assignment); db.commit(); db.refresh(assignment)
    return assignment_payload(assignment)


@app.get("/admin/training-assignments", response_model=List[AssignmentResponse])
def list_training_assignments(user=Depends(require_role("client_admin", "super_admin")), db: Session = Depends(get_db)):
    query = db.query(TrainingAssignment).order_by(TrainingAssignment.created_at.desc())
    if user.get("role") != "super_admin": query = query.filter(TrainingAssignment.company_id == user["company_id"])
    return [assignment_payload(item) for item in query.all()]


@app.get("/employee/assignments", response_model=List[AssignmentResponse])
def employee_assignments(user=Depends(require_role("employee")), db: Session = Depends(get_db)):
    items = db.query(TrainingAssignment).filter(TrainingAssignment.employee_id == int(user["sub"]), TrainingAssignment.company_id == user["company_id"]).order_by(TrainingAssignment.created_at.desc()).all()
    return [assignment_payload(item) for item in items]


@app.get("/api/assignments/{assignment_id}/analysis")
def assignment_analysis(assignment_id: int, user=Depends(require_role("employee", "client_admin", "super_admin")), db: Session = Depends(get_db)):
    assignment = db.query(TrainingAssignment).filter(TrainingAssignment.id == assignment_id).first()
    if not assignment or (user.get("role") != "super_admin" and assignment.company_id != user.get("company_id")):
        raise HTTPException(404, "Assignment not found")
    if user.get("role") == "employee" and assignment.employee_id != int(user["sub"]):
        raise HTTPException(404, "Assignment not found")
    session = (db.query(DbSession).filter(DbSession.assignment_id == assignment.id)
               .order_by(DbSession.id.desc()).first())
    analysis = assignment.report.summary if assignment.report else (build_assignment_report(assignment, session) if session else {})
    return {"assignment": assignment_payload(assignment), "analysis": analysis or {}}


@app.post("/employee/assignments/{assignment_id}/start", response_model=RoundOut)
def start_assignment(assignment_id: int, user=Depends(require_role("employee")), db: Session = Depends(get_db)):
    assignment = db.query(TrainingAssignment).filter(TrainingAssignment.id == assignment_id,
                    TrainingAssignment.employee_id == int(user["sub"]), TrainingAssignment.company_id == user["company_id"]).first()
    if not assignment: raise HTTPException(404, "Training assignment not found")
    if assignment.status == "completed": raise HTTPException(400, "Training assignment is already complete")
    if assignment.scheduled_at and assignment.scheduled_at > datetime.utcnow(): raise HTTPException(400, "Training assignment is not active yet")
    session = (db.query(DbSession)
               .filter(DbSession.assignment_id == assignment.id, DbSession.status == "active")
               .order_by(DbSession.id.desc()).first())
    if not session:
        session = DbSession(employee_id=assignment.employee_id, assignment_id=assignment.id, selector="thompson", mode="live", status="active", bandit_state=make_initial_bandit_state())
        assignment.status = "active"; assignment.started_at = assignment.started_at or datetime.utcnow()
        db.add(session); db.commit(); db.refresh(session)
    return api_run_round(session.id, db, user)


@app.get("/employee/inbox")
def employee_inbox(user=Depends(require_role("employee")), db: Session = Depends(get_db)):
    session = db.query(DbSession).filter(DbSession.employee_id == int(user["sub"]), DbSession.status == "active").order_by(DbSession.id.desc()).first()
    if not session: return []
    rounds = db.query(Round).filter(Round.session_id == session.id).order_by(Round.round_number.desc()).limit(20).all()
    return [{"id": r.id, "round_number": r.round_number, "tactic": r.tactic_selected, "response": r.response,
             "scenario": r.scenario, "feedback_text": r.feedback_text} for r in rounds]


@app.post("/employee/training/start")
def employee_start_training(user=Depends(require_role("employee")), db: Session = Depends(get_db)):
    assigned = db.query(TrainingAssignment).filter(TrainingAssignment.employee_id == int(user["sub"]), TrainingAssignment.company_id == user["company_id"], TrainingAssignment.status.in_(["scheduled", "active"])).order_by(TrainingAssignment.created_at.desc()).first()
    if assigned:
        return start_assignment(assigned.id, user, db)
    employee = db.query(Employee).filter(Employee.id == int(user["sub"]), Employee.company_id == user["company_id"]).first()
    if not employee: raise HTTPException(404, "Employee not found")
    session = db.query(DbSession).filter(DbSession.employee_id == employee.id, DbSession.status == "active").order_by(DbSession.id.desc()).first()
    if not session:
        session = DbSession(employee_id=employee.id, selector="thompson", mode="live", status="active", bandit_state=make_initial_bandit_state())
        db.add(session); db.commit(); db.refresh(session)
    return api_run_round(session.id, db, user)


@app.post("/employee/round/{round_id}/respond", response_model=RoundOut)
def employee_respond(round_id: int, req: HumanResponseRequest, user=Depends(require_role("employee")), db: Session = Depends(get_db)):
    round_rec = (db.query(Round).join(DbSession).filter(Round.id == round_id, DbSession.employee_id == int(user["sub"]),
                  DbSession.employee.has(company_id=user["company_id"])).first())
    if not round_rec: raise HTTPException(404, "Round not found")
    if round_rec.response is not None:
        return round_rec
    return api_complete_human_round(round_rec.session_id, round_rec.round_number, req, db, user)


@app.get("/employee/round/{round_id}/feedback")
def employee_feedback(round_id: int, user=Depends(require_role("employee")), db: Session = Depends(get_db)):
    round_rec = (db.query(Round).join(DbSession).filter(Round.id == round_id, DbSession.employee_id == int(user["sub"])).first())
    if not round_rec: raise HTTPException(404, "Round not found")
    return {
        "round_id": round_id,
        "feedback_text": round_rec.feedback_text or "Feedback is not available until you respond.",
        "feedback_indicators": round_rec.feedback_indicators or [],
    }


@app.get("/admin/employees")
def admin_employees(user=Depends(require_role("client_admin", "super_admin")), db: Session = Depends(get_db)):
    query = db.query(Employee)
    if user.get("role") != "super_admin": query = query.filter(Employee.company_id == user["company_id"])
    result = []
    for employee in query.all():
        rounds = db.query(Round).join(DbSession).filter(DbSession.employee_id == employee.id, Round.response != None).all()  # noqa: E711
        failures = [r for r in rounds if (r.safety_score or 0) < 0.5]
        recent_tactics = [r.tactic_selected for r in rounds[-4:]]
        repeat_clicker = any(recent_tactics[i] == recent_tactics[i + 1] and (rounds[-4 + i].response in {"click", "credentials"}) and (rounds[-4 + i + 1].response in {"click", "credentials"}) for i in range(max(0, len(recent_tactics) - 1))) if len(recent_tactics) > 1 else False
        result.append({"id": employee.id, "name": employee.name, "email": employee.email, "department": employee.department,
                       "role": employee.role, "rounds": len(rounds), "risk_score": round(1 - (sum(r.safety_score or 0 for r in rounds) / len(rounds)), 3) if rounds else 0.5,
                       "repeat_clicker": repeat_clicker, "failed_rounds": len(failures)})
    return result


@app.get("/admin/employees/{employee_id}")
def admin_employee_detail(employee_id: int, user=Depends(require_role("client_admin", "super_admin")), db: Session = Depends(get_db)):
    query = db.query(Employee).filter(Employee.id == employee_id)
    if user.get("role") != "super_admin": query = query.filter(Employee.company_id == user["company_id"])
    employee = query.first()
    if not employee: raise HTTPException(404, "Employee not found")
    rounds = (db.query(Round).join(DbSession).filter(DbSession.employee_id == employee.id, Round.response != None)
              .order_by(Round.round_number.asc()).all())  # noqa: E711
    return {"employee": {"id": employee.id, "name": employee.name, "email": employee.email,
                          "role": employee.role, "department": employee.department},
            "rounds": [{"id": r.id, "round_number": r.round_number, "tactic": r.tactic_selected,
                        "response": r.response, "detection_reward": r.detection_reward,
                        "safety_score": r.safety_score, "classifier_score": r.classifier_score,
                        "feedback_text": r.feedback_text, "response_time_seconds": r.response_time_seconds, "created_at": r.created_at} for r in rounds]}


@app.get("/admin/analytics/overview")
def admin_overview(user=Depends(require_role("client_admin", "super_admin")), db: Session = Depends(get_db)):
    employees = admin_employees(user, db)
    department = {}
    query = db.query(Round).join(DbSession).join(Employee, DbSession.employee_id == Employee.id).filter(Round.response != None)  # noqa: E711
    if user.get("role") != "super_admin": query = query.filter(Employee.company_id == user["company_id"])
    rounds = query.order_by(Round.created_at.asc()).all()
    tactic_totals = {}
    for item in rounds:
        tactic_totals.setdefault(item.tactic_selected, []).append(item.detection_reward or 0)
    trend = []
    weighted_total = 0.0
    weight_total = 0.0
    for index, item in enumerate(rounds, 1):
        risk = 1 - (item.safety_score if item.safety_score is not None else item.detection_reward or 0)
        weight = index
        weighted_total += risk * weight
        weight_total += weight
        trend.append({"round": index, "risk": round(risk, 3), "date": item.created_at.isoformat(), "department": item.session.employee.department})
        department.setdefault(item.session.employee.department, {})
        department[item.session.employee.department].setdefault(item.tactic_selected, []).append(risk)
    heatmap = {dept: {tactic: round(sum(values) / len(values), 3) for tactic, values in tactics.items()} for dept, tactics in department.items()}
    previous = rounds[:max(1, len(rounds) // 2)]
    previous_risk = sum(1 - (r.safety_score if r.safety_score is not None else r.detection_reward or 0) for r in previous) / len(previous) if previous else 0
    current_risk = weighted_total / weight_total if weight_total else 0
    reportable = sum(1 for r in rounds if r.response == "report")
    times = [r.response_time_seconds for r in rounds if r.response_time_seconds is not None]
    company = db.query(Company).filter(Company.id == user.get("company_id")).first()
    company_settings = (company.settings or {}) if company else {}
    return {"company_name": company.name if company else "All companies", "active_tactics": company_settings.get("active_tactics", list(TACTICS)), "total_employees": len(employees),
            "org_susceptibility": round(sum(e["risk_score"] for e in employees) / len(employees), 3) if employees else 0,
            "department_breakdown": {k: round(sum(v.values(), []) and sum(sum(v.values(), [])) / len(sum(v.values(), [])), 3) for k,v in department.items()},
            "heatmap": heatmap, "organization_risk_score": round(current_risk * 100, 1),
            "risk_change": round((current_risk - previous_risk) * 100, 1),
            "avg_time_to_report": round(sum(times) / len(times), 1) if times else None,
            "repeat_clickers": sum(1 for e in employees if e.get("repeat_clicker")), "completed_reports": reportable,
            "tactic_breakdown": {k: round(sum(v)/len(v), 3) for k,v in tactic_totals.items()},
            "trend": trend, "rounds_analyzed": len(rounds), "employees": employees}


@app.get("/employee/analytics/personal")
def employee_personal_analytics(user=Depends(require_role("employee")), db: Session = Depends(get_db)):
    rounds = (db.query(Round).join(DbSession).filter(DbSession.employee_id == int(user["sub"]), Round.response != None)
              .order_by(Round.created_at.asc()).all())  # noqa: E711
    all_rounds = (db.query(Round).join(DbSession).join(Employee, DbSession.employee_id == Employee.id)
                  .filter(Employee.company_id == user["company_id"], Round.response != None).all())  # noqa: E711
    risk = [1 - (r.safety_score if r.safety_score is not None else r.detection_reward or 0) for r in rounds]
    tactic = {}
    for r in rounds: tactic.setdefault(r.tactic_selected, []).append(1 - (r.safety_score if r.safety_score is not None else r.detection_reward or 0))
    group_scores = []
    for emp_id in {r.session.employee_id for r in all_rounds}:
        values = [1 - (r.safety_score if r.safety_score is not None else r.detection_reward or 0) for r in all_rounds if r.session.employee_id == emp_id]
        if values: group_scores.append(sum(values) / len(values))
    personal = sum(risk) / len(risk) if risk else 0
    percentile = round(sum(1 for score in group_scores if score >= personal) / len(group_scores) * 100) if group_scores else 0
    return {"risk_score": round(personal * 100, 1), "percentile": percentile, "trend": [{"round": r.round_number, "risk": round(1 - (r.safety_score if r.safety_score is not None else r.detection_reward or 0), 3)} for r in rounds],
            "strongest_tactic": min(tactic, key=lambda x: sum(tactic[x]) / len(tactic[x])) if tactic else None,
            "weakest_tactic": max(tactic, key=lambda x: sum(tactic[x]) / len(tactic[x])) if tactic else None,
            "history": [{"id": r.id, "tactic": r.tactic_selected, "response": r.response, "safety_score": r.safety_score, "response_time_seconds": r.response_time_seconds, "created_at": r.created_at} for r in rounds[-10:]]}


@app.get("/admin/analytics/sampling")
def admin_sampling_comparison(user=Depends(require_role("client_admin", "super_admin")), db: Session = Depends(get_db), rounds: int | None = None, repetitions: int | None = None, seed: int | None = None):
    """Return a deterministic benchmark curve for Thompson Sampling vs a random baseline.

    The comparison uses the same employee susceptibility profiles and response/reward model
    as the trainer, averaged across repeated runs. It is intentionally a benchmark view, not
    a claim that the random selector was used in each employee's live assignment.
    """
    query = db.query(Employee)
    if user.get("role") != "super_admin": query = query.filter(Employee.company_id == user["company_id"])
    employees = query.order_by(Employee.id.asc()).all()
    default_rounds, default_repetitions, default_seed = benchmark_config()
    rounds = max(1, min(rounds or default_rounds, 100))
    repetitions = max(1, min(repetitions or default_repetitions, 500))
    seed = seed if seed is not None else default_seed
    thompson_totals = [0.0] * rounds
    random_totals = [0.0] * rounds
    run_count = max(1, len(employees)) * repetitions

    for employee_index, employee in enumerate(employees or [None]):
        profile = employee.susceptibility if employee else {tactic: 0.5 for tactic in TACTICS}
        simulated = SimulatedEmployee(
            name=employee.name if employee else "Benchmark employee",
            role=employee.role if employee else "Employee",
            department=employee.department if employee else "All",
            susceptibility=profile,
        )
        for repetition in range(repetitions):
            run_seed = seed + employee_index * 1000 + repetition
            thompson = ThompsonSampler(seed=run_seed)
            random_selector = RandomSelector(seed=run_seed)
            thompson_cumulative = 0.0
            random_cumulative = 0.0
            thompson_rng = random.Random(run_seed + 17)
            random_rng = random.Random(run_seed + 31)
            for index in range(rounds):
                thompson_tactic, _ = thompson.select()
                thompson_reward = get_detection_reward(sample_response(simulated, thompson_tactic, thompson_rng))
                thompson.update(thompson_tactic, thompson_reward)
                thompson_cumulative += thompson_reward
                random_tactic, _ = random_selector.select()
                random_reward = get_detection_reward(sample_response(simulated, random_tactic, random_rng))
                random_selector.update(random_tactic, random_reward)
                random_cumulative += random_reward
                thompson_totals[index] += thompson_cumulative
                random_totals[index] += random_cumulative

    points = []
    for index in range(rounds):
        thompson_value = thompson_totals[index] / run_count
        random_value = random_totals[index] / run_count
        points.append({"round": index + 1, "thompson": round(thompson_value, 3),
                       "random": round(random_value, 3),
                       "difference": round(thompson_value - random_value, 3)})
    final = points[-1]
    return {"rounds": points, "repetitions": repetitions, "employees_in_benchmark": len(employees),
            "final_difference": final["difference"], "winner": "Thompson Sampling" if final["difference"] >= 0 else "Random baseline"}


@app.get("/admin/settings")
def get_admin_settings(user=Depends(require_role("client_admin", "super_admin")), db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == user.get("company_id")).first()
    if not company: raise HTTPException(404, "Company not found")
    settings = company.settings or {}
    return {"company_id": company.id, "company_name": company.name,
            "training_frequency_days": settings.get("training_frequency_days", 7),
            "active_tactics": settings.get("active_tactics", list(TACTICS))}


@app.get("/admin/config/tactics")
def admin_tactics(user=Depends(require_role("client_admin", "super_admin")), db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == user.get("company_id")).first()
    return {"tactics": list((company.settings or {}).get("active_tactics", TACTICS)) if company else list(TACTICS)}


@app.put("/admin/settings")
def admin_settings(req: AdminSettingsRequest, user=Depends(require_role("client_admin", "super_admin"))):
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.id == user.get("company_id")).first()
        if not company: raise HTTPException(404, "Company not found")
        company.settings = {"training_frequency_days": req.training_frequency_days, "active_tactics": req.active_tactics}
        db.commit()
        return {"company_id": company.id, **company.settings}
    finally:
        db.close()


@app.get("/admin/reports/export")
def export_report(format: str = "csv", mode: str = "full", employee_id: int | None = None, user=Depends(require_role("client_admin", "super_admin")), db: Session = Depends(get_db)):
    if format not in {"csv", "pdf"}: raise HTTPException(400, "format must be csv or pdf")
    query = db.query(Round, DbSession, Employee, Scenario).join(DbSession, Round.session_id == DbSession.id).join(Employee, DbSession.employee_id == Employee.id).outerjoin(Scenario, Round.scenario_id == Scenario.id)
    if user.get("role") != "super_admin": query = query.filter(Employee.company_id == user["company_id"])
    if employee_id is not None: query = query.filter(Employee.id == employee_id)
    rows = query.order_by(Round.created_at.asc()).all()
    if format == "csv":
        output = io.StringIO(); writer = csv.writer(output)
        writer.writerow(["employee", "department", "round", "tactic", "response", "detection_reward", "safety_score", "classifier_score", "created_at"])
        for r, _, e, _ in rows: writer.writerow([e.name, e.department, r.round_number, r.tactic_selected, r.response, r.detection_reward, r.safety_score, r.classifier_score, r.created_at.isoformat()])
        return Response(output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=securetrain-report.csv"})
    company = db.query(Company).filter(Company.id == user.get("company_id")).first()
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen.canvas import Canvas
        pdf = io.BytesIO(); canvas = Canvas(pdf, pagesize=letter)
        canvas.setTitle("SecureTrain Analysis Report")
        y = 760
        canvas.setFont("Helvetica-Bold", 16); canvas.drawString(48, y, f"SecureTrain Analysis Report - {company.name if company else 'All Companies'}")
        y -= 24; canvas.setFont("Helvetica", 9); canvas.drawString(48, y, f"Generated: {__import__('datetime').datetime.utcnow().isoformat()}Z")
        y -= 28
        if mode == "executive":
            completed = len(rows)
            safe = sum((r.safety_score or 0) for r, _, _, _ in rows) / completed if completed else 0
            canvas.setFont("Helvetica-Bold", 12); canvas.drawString(48, y, "Executive Summary")
            y -= 24; canvas.setFont("Helvetica", 11); canvas.drawString(48, y, f"Organization risk score: {round((1 - safe) * 100, 1)}/100")
            y -= 20; canvas.drawString(48, y, f"Completed rounds: {completed}   Reports: {sum(1 for r, _, _, _ in rows if r.response == 'report')}")
            y -= 30; canvas.drawString(48, y, "This summary focuses on organization-level risk and training progress.")
            canvas.save()
            return Response(pdf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=securetrain-executive-summary.pdf"})
        canvas.setFont("Helvetica-Bold", 10); canvas.drawString(48, y, "Employee / Department / Round / Tactic / Response / Detection / Safety")
        canvas.setFont("Helvetica", 8)
        for r, _, e, _ in rows:
            y -= 14
            if y < 48: canvas.showPage(); y = 760; canvas.setFont("Helvetica", 8)
            line = f"{e.name[:22]} / {e.department[:14]} / {r.round_number} / {r.tactic_selected} / {r.response or '-'} / {r.detection_reward or 0:.2f} / {r.safety_score or 0:.2f}"
            canvas.drawString(48, y, line[:115])
        canvas.save()
        return Response(pdf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=securetrain-report.pdf"})
    except ImportError:
        return Response("PDF generation dependency unavailable", status_code=503)


@app.post("/api/session/{session_id}/batch", response_model=BatchRunResponse)
def api_run_batch(
    session_id: int,
    req: BatchRunRequest,
    db: Session = Depends(get_db),
    user=Depends(optional_user),
):
    """Run multiple simulated rounds rapidly using fast template scenarios."""
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session or (user and user.get("role") != "super_admin" and session.employee.company_id != user.get("company_id")):
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
def api_get_session_state(session_id: int, db: Session = Depends(get_db), user=Depends(optional_user)):
    """Return bandit posteriors, history points, and Random baseline comparison curve."""
    session = db.query(DbSession).filter(DbSession.id == session_id).first()
    if not session or (user and user.get("role") != "super_admin" and session.employee.company_id != user.get("company_id")):
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

if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


@app.get("/")
def serve_index():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Adaptive AI Security Awareness Trainer API is running. Build the React UI with npm run build."}


