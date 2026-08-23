"""Synthetic employees and how they respond to phishing scenarios.

IMPORTANT: this is a SIMULATED environment for training and evaluating
the bandit agent. It is not a predictor of real human behavior.

Ground truth: each employee hides a susceptibility value per tactic.
The learning agent never sees these numbers; it only sees sampled
responses. The evaluation harness uses them to compute regret.
"""

import random
from dataclasses import dataclass

from reward import DETECTION_REWARDS

TACTICS = ("urgency", "authority", "invoice", "credential")

ROLES = (
    "Accountant",
    "Software Engineer",
    "HR Specialist",
    "Sales Executive",
    "Operations Manager",
)

DEPARTMENTS = ("Finance", "Engineering", "People", "Sales", "Operations")

# scenario difficulty 1..5 scales susceptibility between 0.70x and 1.25x
DIFFICULTY_MIN_FACTOR = 0.70
DIFFICULTY_MAX_FACTOR = 1.25

# keep responses probabilistic, never deterministic
MIN_EFFECTIVE_SUSCEPTIBILITY = 0.02
MAX_EFFECTIVE_SUSCEPTIBILITY = 0.95

# dominant weak arm per employee is drawn from these ranges so that the
# gap to every other arm is at least 0.20 (keeps regret well-defined)
DOMINANT_SUSCEPTIBILITY_RANGE = (0.65, 0.90)
OTHER_SUSCEPTIBILITY_MAX = 0.45


@dataclass
class Employee:
    """One synthetic employee with a hidden vulnerability profile."""

    code: str
    role: str
    department: str
    base_alertness: float          # 0..1 general security awareness
    susceptibility: dict           # tactic -> hidden 0..1 vulnerability
    training_boost: float = 0.0    # future use: repeated-exposure learning

    def weakest_tactic(self) -> str:
        return max(self.susceptibility, key=self.susceptibility.get)


def difficulty_factor(difficulty: int) -> float:
    """Map scenario difficulty 1..5 onto a linear multiplier in [0.7, 1.25]."""
    if difficulty not in (1, 2, 3, 4, 5):
        raise ValueError(f"difficulty must be an integer 1..5, got {difficulty}")
    span = DIFFICULTY_MAX_FACTOR - DIFFICULTY_MIN_FACTOR
    return DIFFICULTY_MIN_FACTOR + (difficulty - 1) / 4 * span


def response_distribution(employee: Employee, tactic: str, difficulty: int = 3) -> dict:
    """Probability of each response to one scenario.

    Higher effective susceptibility shifts probability mass away from
    report/ignore towards click/credentials, i.e. towards higher
    detection reward.
    """
    alertness_factor = 1.3 - 0.6 * employee.base_alertness
    effective_s = (
        employee.susceptibility[tactic]
        * difficulty_factor(difficulty)
        * alertness_factor
        - employee.training_boost
    )
    effective_s = min(max(effective_s, MIN_EFFECTIVE_SUSCEPTIBILITY), MAX_EFFECTIVE_SUSCEPTIBILITY)

    p_credentials = 0.5 * effective_s
    p_click = 0.5 * effective_s
    p_safe = 1.0 - effective_s
    p_ignore = p_safe * (1.0 - 0.6 * employee.base_alertness)
    p_report = p_safe - p_ignore

    return {
        "ignore": p_ignore,
        "report": p_report,
        "click": p_click,
        "credentials": p_credentials,
    }


def sample_response(employee: Employee, tactic: str, difficulty: int = 3, rng=None) -> str:
    """Draw one behavioral response from the employee's distribution."""
    rng = rng or random.Random()
    probs = response_distribution(employee, tactic, difficulty)
    responses = list(probs.keys())
    weights = [probs[r] for r in responses]
    return rng.choices(responses, weights=weights, k=1)[0]


def expected_detection_reward(employee: Employee, tactic: str, difficulty: int = 3) -> float:
    """True mean reward of using this tactic on this employee.

    Evaluation-harness-only value (regret computation). Never shown to
    the learning agent.
    """
    probs = response_distribution(employee, tactic, difficulty)
    return sum(prob * DETECTION_REWARDS[response] for response, prob in probs.items())


def true_arm_means(employee: Employee, difficulty: int = 3) -> dict:
    """Expected detection reward for every tactic, e.g. {'urgency': 0.27, ...}."""
    return {tactic: expected_detection_reward(employee, tactic, difficulty) for tactic in TACTICS}


def generate_population(count_per_combo: int = 4, seed=None) -> list:
    """Build the synthetic workforce.

    count_per_combo employees for each role x department pairing:
    5 roles x 5 departments x 4 variants = 100 employees by default.
    Every employee gets exactly one dominant weak arm.
    """
    rng = random.Random(seed)
    employees = []
    counter = 0
    for role in ROLES:
        for department in DEPARTMENTS:
            for _ in range(count_per_combo):
                counter += 1
                dominant = rng.choice(TACTICS)
                susceptibility = {}
                for tactic in TACTICS:
                    if tactic == dominant:
                        low, high = DOMINANT_SUSCEPTIBILITY_RANGE
                        susceptibility[tactic] = rng.uniform(low, high)
                    else:
                        susceptibility[tactic] = rng.uniform(0.05, OTHER_SUSCEPTIBILITY_MAX)
                employees.append(
                    Employee(
                        code=f"emp_{counter:03d}",
                        role=role,
                        department=department,
                        base_alertness=rng.uniform(0.30, 0.80),
                        susceptibility=susceptibility,
                    )
                )
    return employees


def _demo() -> None:
    """Standalone demo: inspect a few employees and one live sampling round."""
    population = generate_population(seed=42)
    accountant = next(e for e in population if e.role == "Accountant")

    print("Synthetic workforce:", len(population), "employees\n")
    for emp in population[:3]:
        shown = {tactic: round(value, 2) for tactic, value in emp.susceptibility.items()}
        print(f"{emp.code}  {emp.role:<20} {emp.department:<12} "
              f"alertness={emp.base_alertness:.2f}  weakest={emp.weakest_tactic()}")
        print(f"   susceptibility: {shown}\n")

    print(f"Response probabilities for {accountant.code} at difficulty 3:")
    for tactic in TACTICS:
        probs = response_distribution(accountant, tactic, difficulty=3)
        pretty = ", ".join(f"{r}={p:.2f}" for r, p in probs.items())
        print(f"  {tactic:<11}-> {pretty}")
        print(f"              true expected detection reward = "
              f"{expected_detection_reward(accountant, tactic):.3f}")

    rng = random.Random(0)
    print("\n10 sampled responses (invoice):",
          [sample_response(accountant, "invoice", rng=rng) for _ in range(10)])


if __name__ == "__main__":
    _demo()
