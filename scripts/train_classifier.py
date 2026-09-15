"""Train the Behavior Classifier offline and save artifact to data/classifier.pkl.

Features are STRICTLY observable-only (never hidden susceptibility):
- one-hot tactic
- one-hot employee role & department
- tactic exposure count (times seen)
- previous response to this tactic
- current round number
"""

import os
import pickle
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
import sys
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.reward import RESPONSES, TACTICS
from app.simulator import SimulatedEmployee, get_default_employees, sample_response

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
MODEL_PATH = DATA_DIR / "classifier.pkl"

ROLES: Tuple[str, ...] = (
    "Accountant",
    "Software Engineer",
    "HR Specialist",
    "Sales Executive",
    "Operations Manager",
    "General",
)

DEPARTMENTS: Tuple[str, ...] = (
    "Finance",
    "Engineering",
    "People",
    "Sales",
    "Operations",
    "General",
)

HISTORY_STATES: Tuple[str, ...] = ("none", "ignore", "report", "click", "credentials")


def one_hot(value: str, categories: Tuple[str, ...]) -> List[float]:
    return [1.0 if value == cat else 0.0 for cat in categories]


def extract_features(
    tactic: str,
    role: str,
    department: str,
    times_seen: int,
    last_response: Optional[str],
    round_no: int,
) -> List[float]:
    """Build observable-only feature vector (23 dimensions)."""
    r_val = role if role in ROLES else "General"
    d_val = department if department in DEPARTMENTS else "General"
    last_val = last_response if last_response in HISTORY_STATES else "none"

    return (
        one_hot(tactic, TACTICS)
        + one_hot(r_val, ROLES)
        + one_hot(d_val, DEPARTMENTS)
        + [min(times_seen, 20) / 20.0]
        + one_hot(last_val, HISTORY_STATES)
        + [min(round_no, 50) / 50.0]
    )


def generate_dataset(n_samples: int = 5000, seed: int = 42) -> Tuple[List[list], List[str]]:
    """Generate synthetic (features, response) pairs by playing simulated rounds."""
    rng = random.Random(seed)
    employees = get_default_employees()

    X, y = [], []
    for emp in employees:
        times_seen = {t: 0 for t in TACTICS}
        last_resp = {t: "none" for t in TACTICS}

        rounds_for_emp = n_samples // len(employees)
        for r_no in range(1, rounds_for_emp + 1):
            tactic = rng.choice(TACTICS)
            feats = extract_features(
                tactic=tactic,
                role=emp.role,
                department=emp.department,
                times_seen=times_seen[tactic],
                last_response=last_resp[tactic],
                round_no=r_no,
            )
            resp = sample_response(emp, tactic, rng=rng)
            X.append(feats)
            y.append(resp)

            times_seen[tactic] += 1
            last_resp[tactic] = resp

    return X, y


def train_and_save():
    print("Generating observable training data from employee simulator...")
    X, y = generate_dataset(n_samples=5000, seed=42)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    print(f"Training Logistic Regression classifier on {len(X_train)} samples...")
    model = LogisticRegression(
        multi_class="multinomial",
        solver="lbfgs",
        max_iter=1000,
        random_state=42,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="macro")
    cm = confusion_matrix(y_test, y_pred, labels=list(RESPONSES))

    print(f"\nHeld-Out Test Split Metrics (n={len(y_test)}):")
    print(f"  Accuracy: {acc * 100:.2f}%")
    print(f"  Macro F1: {f1:.4f}")
    print("  Confusion Matrix (rows: True, cols: Pred [ignore, report, click, credentials]):")
    print(cm)

    artifact = {
        "model": model,
        "classes": list(model.classes_),
        "roles": ROLES,
        "departments": DEPARTMENTS,
        "tactics": TACTICS,
        "history_states": HISTORY_STATES,
        "metrics": {
            "accuracy": round(float(acc), 4),
            "macro_f1": round(float(f1), 4),
            "confusion_matrix": cm.tolist(),
            "classes": list(RESPONSES),
            "n_test": len(y_test),
            "n_train": len(X_train),
        },
    }

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(artifact, f)

    print(f"\nSaved classifier artifact to: {MODEL_PATH}")


if __name__ == "__main__":
    train_and_save()
