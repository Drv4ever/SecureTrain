import random

import pytest

from employee_simulator import (
    Employee,
    TACTICS,
    difficulty_factor,
    expected_detection_reward,
    generate_population,
    response_distribution,
    sample_response,
)
from reward import DETECTION_REWARDS, RESPONSES, detection_reward, safety_reward


def make_employee(invoice_susceptibility: float) -> Employee:
    return Employee(
        code="emp_test",
        role="Accountant",
        department="Finance",
        base_alertness=0.55,
        susceptibility={
            "urgency": 0.2,
            "authority": 0.3,
            "invoice": invoice_susceptibility,
            "credential": 0.4,
        },
    )


# ---------- reward mappings (Design A) ----------

def test_detection_rewards_match_design_a():
    assert detection_reward("credentials") == 1.0
    assert detection_reward("click") == 0.7
    assert detection_reward("ignore") == 0.3
    assert detection_reward("report") == 0.0


def test_safety_rewards_keep_original_rubric():
    assert safety_reward("report") == 1.0
    assert safety_reward("ignore") == 0.6
    assert safety_reward("click") == 0.2
    assert safety_reward("credentials") == 0.0


def test_unknown_response_rejected():
    with pytest.raises(ValueError):
        detection_reward("forwarded_to_colleague")


# ---------- response distribution ----------

def test_probabilities_sum_to_one_for_every_arm_and_difficulty():
    emp = make_employee(invoice_susceptibility=0.8)
    for tactic in TACTICS:
        for difficulty in range(1, 6):
            probs = response_distribution(emp, tactic, difficulty)
            assert sum(probs.values()) == pytest.approx(1.0)
            assert set(probs.keys()) == set(RESPONSES)


def test_extreme_susceptibility_stays_in_valid_range():
    for s in (0.0, 1.0):
        probs = response_distribution(make_employee(s), "invoice", difficulty=5)
        assert all(p >= 0.0 for p in probs.values())
        assert all(p <= 1.0 for p in probs.values())
        assert sum(probs.values()) == pytest.approx(1.0)


def test_higher_susceptibility_means_higher_expected_reward():
    low = expected_detection_reward(make_employee(0.1), "invoice")
    high = expected_detection_reward(make_employee(0.9), "invoice")
    assert high > low


def test_harder_scenarios_are_more_dangerous():
    easy = expected_detection_reward(make_employee(0.5), "invoice", difficulty=1)
    hard = expected_detection_reward(make_employee(0.5), "invoice", difficulty=5)
    assert hard > easy


def test_difficulty_factor_bounds():
    assert difficulty_factor(1) == pytest.approx(0.70)
    assert difficulty_factor(5) == pytest.approx(1.25)
    with pytest.raises(ValueError):
        difficulty_factor(6)


# ---------- population ----------

def test_population_size_and_hidden_dominant_weakness():
    population = generate_population(seed=5)
    assert len(population) == 100
    for emp in population:
        values = sorted(emp.susceptibility.values())
        assert values[-1] >= 0.65                      # one clear weak arm
        assert values[-2] <= 0.45                      # gap of at least 0.20
        assert emp.weakest_tactic() in TACTICS


def test_sampled_responses_are_always_valid():
    emp = make_employee(invoice_susceptibility=0.8)
    rng = random.Random(0)
    for _ in range(200):
        for tactic in TACTICS:
            assert sample_response(emp, tactic, rng=rng) in RESPONSES


def test_true_arm_means_are_computable_and_ordered():
    emp = make_employee(invoice_susceptibility=0.9)
    means = {tactic: expected_detection_reward(emp, tactic) for tactic in TACTICS}
    assert max(means, key=means.get) == "invoice"
    # every mean is a weighted combination of the detection table
    for value in means.values():
        assert 0.0 <= value <= max(DETECTION_REWARDS.values())
