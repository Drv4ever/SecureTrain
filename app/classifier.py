"""Runtime adapter for the offline behavior classifier.

The trained artifact is optional. When unavailable, the adapter preserves the
existing deterministic reward mapping so simulations remain fully functional.
"""
import pickle
from pathlib import Path
from typing import Optional
from app.reward import get_detection_reward

MODEL_PATH = Path(__file__).resolve().parent.parent / "data" / "classifier.pkl"

def score_response(tactic: str, role: str, department: str, response: str,
                  times_seen: int = 0, round_no: int = 1) -> float:
    """Return a classifier confidence that the response indicates susceptibility."""
    if MODEL_PATH.exists():
        try:
            from scripts.train_classifier import extract_features
            with MODEL_PATH.open("rb") as handle:
                artifact = pickle.load(handle)
            model = artifact["model"]
            features = extract_features(tactic, role, department, times_seen, response, round_no)
            probabilities = model.predict_proba([features])[0]
            classes = list(model.classes_)
            return round(float(sum(p * get_detection_reward(c) for p, c in zip(probabilities, classes))), 4)
        except Exception:
            pass
    return get_detection_reward(response)
