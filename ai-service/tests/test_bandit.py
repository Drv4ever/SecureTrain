import random

import pytest

from bandit import ThompsonSampler, best_arm


def test_initial_state_is_uniform_ignorance():
    sampler = ThompsonSampler()
    for arm in sampler.arm_names:
        assert sampler.alpha[arm] == 1.0
        assert sampler.beta[arm] == 1.0
        assert sampler.pulls[arm] == 0
        assert sampler.posterior_mean(arm) == pytest.approx(0.5)


def test_update_math_is_exact():
    sampler = ThompsonSampler()
    sampler.update("invoice", 0.7)
    assert sampler.alpha["invoice"] == pytest.approx(1.7)
    assert sampler.beta["invoice"] == pytest.approx(1.3)
    assert sampler.pulls["invoice"] == 1
    # posterior mean equals the running average of observed rewards
    assert sampler.posterior_mean("invoice") == pytest.approx(1.7 / 3.0)


def test_select_returns_a_known_arm():
    sampler = ThompsonSampler(seed=1)
    for _ in range(20):
        assert sampler.select() in sampler.arm_names


def test_sample_posteriors_returns_one_draw_per_arm():
    sampler = ThompsonSampler(seed=2)
    samples = sampler.sample_posteriors()
    assert set(samples.keys()) == set(sampler.arm_names)
    for value in samples.values():
        assert 0.0 < value < 1.0


def test_unknown_arm_rejected():
    sampler = ThompsonSampler()
    with pytest.raises(ValueError):
        sampler.update("bribery", 0.5)


def test_out_of_range_rewards_rejected():
    sampler = ThompsonSampler()
    with pytest.raises(ValueError):
        sampler.update("invoice", 1.5)
    with pytest.raises(ValueError):
        sampler.update("invoice", -0.1)


def test_state_roundtrip_preserves_beliefs():
    sampler = ThompsonSampler(seed=3)
    for _ in range(10):
        sampler.update(sampler.select(), 0.6)

    restored = ThompsonSampler.from_state(sampler.state())

    assert restored.alpha == sampler.alpha
    assert restored.beta == sampler.beta
    assert restored.pulls == sampler.pulls
    assert restored.posterior_means() == sampler.posterior_means()


def test_finds_the_best_arm_and_exploits_it():
    true_rates = {"urgency": 0.2, "authority": 0.3, "invoice": 0.9, "credential": 0.4}
    sampler = ThompsonSampler(seed=11)
    world = random.Random(11)

    choices = []
    for _ in range(400):
        chosen = sampler.select()
        choices.append(chosen)
        reward = 1.0 if world.random() < true_rates[chosen] else 0.0
        sampler.update(chosen, reward)

    assert sampler.posterior_mean("invoice") > sampler.posterior_mean("urgency")
    # exploitation: once learned, the best arm dominates late selections
    late_choices = choices[-100:]
    assert late_choices.count("invoice") >= 80


def test_best_arm_helper():
    means = {"a": 0.1, "b": 0.9, "c": 0.5}
    assert best_arm(means) == "b"
