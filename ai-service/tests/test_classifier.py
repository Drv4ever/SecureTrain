import random

import pytest
from sklearn.linear_model import LogisticRegression

from classifier import (
    CLASSES,
    features_for,
    generate_training_data,
    one_hot,
)
from employee_simulator import (
    TACTICS,
    generate_population,
    sample_response,
)
from reward import RESPONSES


def test_one_hot_is_exclusive():
    assert one_hot("a", ("a", "b", "c")) == [1.0, 0.0, 0.0]
    assert sum(one_hot("b", ("a", "b", "c"))) == 1.0


def test_features_for_length_is_stable():
    vector = features_for(
        tactic="invoice", difficulty=3, role="Accountant", department="Finance",
        base_alertness=0.55, times_seen_tactic=0, last_response=None,
        safe_streak=0, round_no=1, employee_code="emp_001")
    assert len(vector) > 0
    assert all(isinstance(v, float) for v in vector)


def test_identity_aware_features_differ_across_employees():
    base = dict(tactic="invoice", difficulty=3, role="Accountant",
                department="Finance", base_alertness=0.55,
                times_seen_tactic=0, last_response=None, safe_streak=0, round_no=1)
    emp1 = features_for(employee_code="emp_001", **base)
    emp2 = features_for(employee_code="emp_002", **base)
    assert emp1 != emp2


def test_training_data_shapes_match():
    features, labels = generate_training_data(n_employees=10, rounds_per_employee=100, seed=7)
    assert len(features) == 1000
    assert len(labels) == 1000
    assert all(label in RESPONSES for label in labels)


def test_classifier_learns_employee_tactic_weakness():
    """An invoice-weak employee should be predicted more dangerous on the
    invoice tactic than on urgency after training on their history."""
    rng = random.Random(1)
    population = generate_population(seed=1)
    employee = next(e for e in population if e.weakest_tactic() == "invoice")

    features, labels = [], []
    times_seen = {t: 0 for t in TACTICS}
    last_response, safe_streak = None, 0
    for round_no in range(1, 301):
        tactic = rng.choice(TACTICS)
        response = sample_response(employee, tactic, 3, rng=rng)
        features.append(features_for(
            tactic=tactic, difficulty=3, role=employee.role,
            department=employee.department, base_alertness=employee.base_alertness,
            times_seen_tactic=times_seen[tactic], last_response=last_response,
            safe_streak=safe_streak, round_no=round_no,
            employee_code=employee.code))
        labels.append(response)
        times_seen[tactic] += 1
        last_response = response
        safe_streak = safe_streak + 1 if response in ("ignore", "report") else 0

    model = LogisticRegression(solver="lbfgs", max_iter=2000).fit(features, labels)

    def unsafe_mass(tactic: str) -> float:
        vector = [features_for(
            tactic=tactic, difficulty=3, role=employee.role,
            department=employee.department, base_alertness=employee.base_alertness,
            times_seen_tactic=0, last_response=None, safe_streak=0, round_no=1,
            employee_code=employee.code)]
        probs = dict(zip(model.classes_, model.predict_proba(vector)[0]))
        return probs.get("click", 0.0) + probs.get("credentials", 0.0)

    assert unsafe_mass("invoice") > unsafe_mass("urgency")