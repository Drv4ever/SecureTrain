"""Response -> score conversion rules.

Two mappings exist by design (docs/BLUEPRINT.md, section 9):

DETECTION_REWARDS drive the Thompson Sampling agent (Design A):
higher means the phishing succeeded, i.e. this tactic found a weakness.

SAFETY_REWARDS are reported to humans only and never touch the bandit.
A safety-maximizing agent would learn to avoid weak spots, which is the
opposite of what an adaptive trainer must discover.
"""

RESPONSES = ("ignore", "report", "click", "credentials")

DETECTION_REWARDS = {
    "credentials": 1.0,
    "click": 0.7,
    "ignore": 0.3,
    "report": 0.0,
}

SAFETY_REWARDS = {
    "report": 1.0,
    "ignore": 0.6,
    "click": 0.2,
    "credentials": 0.0,
}


def _mapped(mapping: dict, response: str) -> float:
    if response not in mapping:
        raise ValueError(f"unknown response {response!r}, expected one of {RESPONSES}")
    return mapping[response]


def detection_reward(response: str) -> float:
    """Bandit signal in [0, 1]: how successful this phishing attempt was."""
    return _mapped(DETECTION_REWARDS, response)


def safety_reward(response: str) -> float:
    """Reported-only metric in [0, 1]: how safely the employee behaved."""
    return _mapped(SAFETY_REWARDS, response)
