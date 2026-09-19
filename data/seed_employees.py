"""Seed script to populate SQLite with pre-built synthetic employees."""

import sys
from pathlib import Path

# Add project root to sys.path if running as a script
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy.orm import Session
from backend.app.db import SessionLocal, init_db
from backend.app.models import Employee
from backend.app.simulator import get_default_employees


def seed_employees(db: Session, force: bool = False) -> list:
    """Insert 3-5 default synthetic employees if table is empty or if forced."""
    existing_count = db.query(Employee).count()
    if existing_count > 0 and not force:
        print(f"Database already contains {existing_count} employees. Skipping seed.")
        return db.query(Employee).all()

    default_data = get_default_employees()
    if not any("Demo Employee" in item.name for item in default_data):
        from backend.app.simulator import SimulatedEmployee
        default_data.append(SimulatedEmployee(name="Demo Employee", role="Employee", department="General",
                                               susceptibility={tactic: 0.5 for tactic in ("urgency", "authority", "invoice", "credential")}))
    inserted = []
    for emp_data in default_data:
        emp = Employee(
            name=emp_data.name,
            role=emp_data.role,
            department=emp_data.department,
            susceptibility=emp_data.susceptibility,
        )
        db.add(emp)
        inserted.append(emp)

    db.commit()
    for emp in inserted:
        db.refresh(emp)

    print(f"Successfully seeded {len(inserted)} employees into database.")
    return inserted


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        employees = seed_employees(db)
        print("\nSeeded Employees:")
        for e in employees:
            print(f"  [{e.id}] {e.name} - Weakness: {e.susceptibility}")
    finally:
        db.close()

