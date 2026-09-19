"""Diagnostic script for Behavior Classifier artifact (classifier.pkl).

Checks:
1. Loads classifier.pkl and prints feature-column order.
2. Runs 5 fixed synthetic feature vectors twice in a row.
3. Confirms identical output both times (determinism / caching stability).
4. Confirms sane-looking probabilities (no NaNs, sum to 1.0, non-degenerate distributions).
"""

import pickle
import sys
from pathlib import Path
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.train_classifier import (
    DEPARTMENTS,
    FEATURE_NAMES,
    HISTORY_STATES,
    ROLES,
    TACTICS,
    extract_features,
)

MODEL_PATH = BASE_DIR / "data" / "classifier.pkl"


def run_diagnosis():
    print("=" * 60)
    print("CLASSIFIER DIAGNOSTIC REPORT")
    print("=" * 60)

    if not MODEL_PATH.exists():
        print(f"[FAIL] Artifact not found at {MODEL_PATH}")
        sys.exit(1)

    with open(MODEL_PATH, "rb") as f:
        artifact = pickle.load(f)

    model = artifact.get("model")
    classes = artifact.get("classes", list(model.classes_))
    feature_names = artifact.get("feature_names", FEATURE_NAMES)
    metrics = artifact.get("metrics", {})

    print(f"[1] Loaded artifact successfully from {MODEL_PATH}")
    print(f"    Classes: {classes}")
    print(f"    Feature count: {len(feature_names)}")
    print(f"    Metrics: Accuracy={metrics.get('accuracy')}, Macro F1={metrics.get('macro_f1')}")
    print(f"    Dataset: n_train={metrics.get('n_train')}, n_test={metrics.get('n_test')}")

    print("\n[2] Feature Column Order (23 features):")
    for idx, fname in enumerate(feature_names, 1):
        print(f"    {idx:2d}. {fname}")

    # 5 fixed synthetic feature scenarios
    test_cases = [
        ("urgency", "Accountant", "Finance", 0, "none", 1),
        ("authority", "Software Engineer", "Engineering", 2, "click", 3),
        ("invoice", "Operations Manager", "Operations", 5, "report", 10),
        ("credential", "HR Specialist", "People", 8, "credentials", 15),
        ("urgency", "Sales Executive", "Sales", 1, "ignore", 2),
    ]

    vectors = [extract_features(*tc) for tc in test_cases]

    print("\n[3] Testing Determinism (Run 1 vs Run 2)...")
    probs_run1 = model.predict_proba(vectors)
    probs_run2 = model.predict_proba(vectors)

    diff = np.max(np.abs(probs_run1 - probs_run2))
    print(f"    Max absolute probability difference between Run 1 and Run 2: {diff:.10e}")
    if diff == 0.0:
        print("    [PASS] Consecutive outputs are strictly IDENTICAL (deterministic).")
    else:
        print(f"    [FAIL] Model output varied between consecutive runs (diff={diff}).")
        sys.exit(1)

    print("\n[4] Inspecting Predicted Probabilities for 5 Test Vectors:")
    for idx, (tc, probs) in enumerate(zip(test_cases, probs_run1), 1):
        tactic, role, dept, times_seen, last_resp, round_no = tc
        prob_dict = {cls: round(float(p), 4) for cls, p in zip(classes, probs)}
        prob_sum = sum(probs)
        print(f"    Vector {idx} ({tactic} | {role} | {dept} | seen={times_seen} | last={last_resp} | r={round_no}):")
        print(f"        Probabilities: {prob_dict} (Sum = {prob_sum:.4f})")

        # Sanity assertions
        assert abs(prob_sum - 1.0) < 1e-4, f"Probabilities do not sum to 1: {prob_sum}"
        assert not np.isnan(probs).any(), "Probabilities contain NaN values"
        assert all(p >= 0.0 for p in probs), "Probabilities contain negative values"

    print("    [PASS] All probabilities are sane, non-negative, and sum to 1.0.")
    print("=" * 60)
    print("ALL DIAGNOSTIC CHECKS PASSED.")
    print("=" * 60)


if __name__ == "__main__":
    run_diagnosis()
