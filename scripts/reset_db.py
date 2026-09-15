"""Reset local demo data and seed exactly five clean employees.

Run deliberately before a demo: ``python scripts/reset_db.py``.
The target is the configured DATABASE_PATH, never a hand-edited SQLite file.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import Base, SessionLocal, engine, init_db
from app.models import Company, ClientAdmin, Employee, Round, Scenario, Session, TrainingAssignment, TrainingReport
from app.auth import hash_password
from data.seed_employees import seed_employees


def main() -> None:
    init_db()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        company = Company(name="SecureTrain Demo", settings={"training_frequency_days": 7, "active_tactics": ["urgency", "authority", "invoice", "credential"]})
        db.add(company)
        db.flush()
        db.add(ClientAdmin(company_id=company.id, email="admin@demo.securetrain.test", name="Demo Admin", hashed_password=hash_password("AdminDemo123!")))
        employees = seed_employees(db, force=True)
        for employee in employees:
            employee.company_id = company.id
            employee.email = employee.email or f"{employee.name.split()[0].lower()}@demo.securetrain.test"
            employee.hashed_password = hash_password("EmployeeDemo123!")
        db.commit()
        print(f"Reset complete: {len(employees)} employees, 0 assignments, 0 sessions, 0 rounds")
    finally:
        db.close()


if __name__ == "__main__":
    main()
