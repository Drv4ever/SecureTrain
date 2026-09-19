"""Runtime adapter for the offline behavior classifier.

The trained artifact is cached in memory once loaded at startup so simulations
and requests do not incur disk I/O per prediction.
"""
import pickle
from pathlib import Path
from typing import Any, Dict, Optional

from backend.app.reward import get_detection_reward

MODEL_PATH = Path(__file__).resolve().parents[2] / "data" / "classifier.pkl"

_cached_artifact: Optional[Dict[str, Any]] = None


def load_classifier(force_reload: bool = False) -> Optional[Dict[str, Any]]:
    """Load and cache the classifier artifact into memory."""
    global _cached_artifact
    if _cached_artifact is not None and not force_reload:
        return _cached_artifact

    if MODEL_PATH.exists():
        try:
            with MODEL_PATH.open("rb") as handle:
                _cached_artifact = pickle.load(handle)
                return _cached_artifact
        except Exception as exc:
            print(f"[Classifier Warning] Failed to load {MODEL_PATH}: {exc}")
            _cached_artifact = None
    return None


def get_classifier_info() -> Dict[str, Any]:
    """Return model health metrics and diagnostics for the admin panel."""
    artifact = load_classifier()
    if not artifact:
        return {
            "loaded": False,
            "status": "Model artifact not found. Please run scripts/train_classifier.py.",
            "accuracy": None,
            "macro_f1": None,
            "confusion_matrix": [],
            "classes": ["ignore", "report", "click", "credentials"],
            "n_train": 0,
            "n_test": 0,
            "feature_names": [],
        }

    metrics = artifact.get("metrics", {})
    classes = [str(c) for c in metrics.get("classes", artifact.get("classes", []))]
    return {
        "loaded": True,
        "status": "Trained & Active",
        "accuracy": metrics.get("accuracy"),
        "macro_f1": metrics.get("macro_f1"),
        "confusion_matrix": metrics.get("confusion_matrix", []),
        "classes": classes,
        "n_train": metrics.get("n_train", 0),
        "n_test": metrics.get("n_test", 0),
        "feature_names": artifact.get("feature_names", []),
    }


def score_response(
    tactic: str,
    role: str,
    department: str,
    last_response: Optional[str] = "none",
    times_seen: int = 0,
    round_no: int = 1,
    current_response: Optional[str] = None,
) -> float:
    """Return expected vulnerability/detection reward from observable features."""
    artifact = load_classifier()
    if artifact and "model" in artifact:
        try:
            from scripts.train_classifier import extract_features

            model = artifact["model"]
            hist_state = last_response if last_response in ("ignore", "report", "click", "credentials") else "none"
            features = extract_features(tactic, role, department, times_seen, hist_state, round_no)
            probabilities = model.predict_proba([features])[0]
            classes = [str(c) for c in artifact.get("classes", model.classes_)]
            return round(
                float(sum(p * get_detection_reward(c) for p, c in zip(probabilities, classes))),
                4,
            )
        except Exception as exc:
            print(f"[Classifier Warning] score_response inference failed: {exc}")

    fallback_action = current_response or last_response
    if fallback_action in ("ignore", "report", "click", "credentials"):
        return get_detection_reward(fallback_action)
    return 0.5


