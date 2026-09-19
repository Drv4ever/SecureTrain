"""Synthetic employee simulator and response probability model.

Employee representation:
{
  "name": "Dhruv (Accountant, Finance)",
  "role": "Accountant",
  "department": "Finance",
  "susceptibility": {"urgency": 0.20, "authority": 0.30, "invoice": 0.80, "credential": 0.40}
}

Response probability model given susceptibility s in [0, 1] for chosen tactic:
    P(credentials) = 0.5 * s
    P(click)       = 0.5 * s
    P(ignore)      = 0.4 * (1.0 - s)
    P(report)      = 0.6 * (1.0 - s)
"""

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from backend.app.bandit import ThompsonSampler
from backend.app.random_selector import RandomSelector
from backend.app.reward import DETECTION_REWARDS, RESPONSES, TACTICS, get_detection_reward


@dataclass
class SimulatedEmployee:
    """Represents a synthetic employee with a hidden susceptibility profile."""

    name: str
    role: str
    department: str
    susceptibility: Dict[str, float]

    def get_susceptibility(self, tactic: str) -> float:
        if tactic not in self.susceptibility:
            raise ValueError(f"Unknown tactic '{tactic}' for employee {self.name}")
        return self.susceptibility[tactic]

    def weakest_tactic(self) -> str:
        """Return the tactic with highest susceptibility (ground truth)."""
        return max(self.susceptibility, key=self.susceptibility.get)


def response_probabilities(susceptibility: float) -> Dict[str, float]:
    """Calculate categorical response probabilities from susceptibility s."""
    s = min(max(float(susceptibility), 0.0), 1.0)
    p_cred = 0.5 * s
    p_click = 0.5 * s
    p_safe = 1.0 - s
    p_ignore = 0.4 * p_safe
    p_report = 0.6 * p_safe
    return {
        "ignore": p_ignore,
        "report": p_report,
        "click": p_click,
        "credentials": p_cred,
    }


def sample_response(
    employee: SimulatedEmployee,
    tactic: str,
    rng: Optional[random.Random] = None,
) -> str:
    """Sample one response from the employee's probability distribution."""
    r = rng or random
    s = employee.get_susceptibility(tactic)
    probs = response_probabilities(s)
    choices = list(probs.keys())
    weights = [probs[k] for k in choices]
    return r.choices(choices, weights=weights, k=1)[0]


def get_default_employees() -> List[SimulatedEmployee]:
    """Return canonical pre-built employees with distinct weakness profiles."""
    return [
        SimulatedEmployee(
            name="Dhruv (Accountant, Finance)",
            role="Accountant",
            department="Finance",
            susceptibility={"urgency": 0.20, "authority": 0.30, "invoice": 0.80, "credential": 0.40},
        ),
        SimulatedEmployee(
            name="Sarah (Software Engineer, Engineering)",
            role="Software Engineer",
            department="Engineering",
            susceptibility={"urgency": 0.75, "authority": 0.25, "invoice": 0.15, "credential": 0.40},
        ),
        SimulatedEmployee(
            name="Marcus (HR Specialist, People)",
            role="HR Specialist",
            department="People",
            susceptibility={"urgency": 0.30, "authority": 0.80, "invoice": 0.20, "credential": 0.35},
        ),
        SimulatedEmployee(
            name="Elena (Sales Executive, Sales)",
            role="Sales Executive",
            department="Sales",
            susceptibility={"urgency": 0.45, "authority": 0.30, "invoice": 0.25, "credential": 0.85},
        ),
    ]


if __name__ == "__main__":
    # Verification test: Run Thompson Sampling vs Random Selector for 200 rounds against one employee
    test_emp = get_default_employees()[0]
    rounds = 200
    seed = 42

    print(f"=== Running 200-round verification test for: {test_emp.name} ===")
    print(f"Ground-truth susceptibilities: {test_emp.susceptibility}")
    print(f"True weakest tactic: {test_emp.weakest_tactic()}\n")

    # 1. Thompson Sampling
    ts_bandit = ThompsonSampler(seed=seed)
    ts_rng = random.Random(seed)
    ts_cum_reward = 0.0
    for r in range(rounds):
        tactic, _ = ts_bandit.select()
        resp = sample_response(test_emp, tactic, rng=ts_rng)
        reward = get_detection_reward(resp)
        ts_bandit.update(tactic, reward)
        ts_cum_reward += reward

    # 2. Random Selector
    rand_selector = RandomSelector(seed=seed)
    rand_rng = random.Random(seed)
    rand_cum_reward = 0.0
    for r in range(rounds):
        tactic, _ = rand_selector.select()
        resp = sample_response(test_emp, tactic, rng=rand_rng)
        reward = get_detection_reward(resp)
        rand_selector.update(tactic, reward)
        rand_cum_reward += reward

    print(f"Thompson Sampling cumulative reward (200 rounds): {ts_cum_reward:.2f}")
    print("Thompson Sampling learned posteriors:", {k: round(v, 3) for k, v in ts_bandit.posterior_means().items()})
    print(f"Thompson Sampling arm pulls: {ts_bandit.pulls}")
    print(f"\nRandom Selector cumulative reward (200 rounds):    {rand_cum_reward:.2f}")
    print(f"Random Selector arm pulls:    {rand_selector.pulls}")
    print(f"\nPerformance difference: +{(ts_cum_reward - rand_cum_reward):.2f} detection reward with Thompson Sampling")

