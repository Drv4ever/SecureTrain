"""Response to reward conversion rules.

Two reward signals are computed and stored per round, but only ONE drives the bandit:
- Detection reward (drives the bandit):
    credentials -> 1.0
    click       -> 0.7
    ignore      -> 0.3
    report      -> 0.0
  The bandit is a vulnerability finder — it converges on the tactic the employee is worst at.

- Safety score (reported only, does not affect learning):
    report      -> 1.0
    ignore      -> 0.6
    click       -> 0.2
    credentials -> 0.0
"""

from typing import Dict
from backend.app.config import TACTICS, RESPONSES

DETECTION_REWARDS: Dict[str, float] = {
    "credentials": 1.0,
    "click": 0.7,
    "ignore": 0.3,
    "report": 0.0,
}

SAFETY_REWARDS: Dict[str, float] = {
    "report": 1.0,
    "ignore": 0.6,
    "click": 0.2,
    "credentials": 0.0,
}


def get_detection_reward(response: str, classifier_score: float | None = None) -> float:
    """Return the bandit learning reward in [0.0, 1.0]."""
    if response not in DETECTION_REWARDS:
        raise ValueError(f"Unknown response '{response}', expected one of {RESPONSES}")
    base = DETECTION_REWARDS[response]
    if classifier_score is None:
        return base
    return round((base + max(0.0, min(1.0, classifier_score))) / 2, 4)


def get_safety_score(response: str) -> float:
    """Return the human-facing safety metric in [0.0, 1.0]."""
    if response not in SAFETY_REWARDS:
        raise ValueError(f"Unknown response '{response}', expected one of {RESPONSES}")
    return SAFETY_REWARDS[response]

