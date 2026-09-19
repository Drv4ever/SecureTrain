"""Thompson Sampling with Beta posteriors.

Each arm maintains a Beta(alpha, beta) distribution initialized to Beta(1, 1).
For each round:
1. Sample theta_k ~ Beta(alpha_k, beta_k) for all arms.
2. Select arm with argmax(theta_k).
3. Observe reward r in [0, 1].
4. Update posterior:
     alpha_k += r
     beta_k  += (1 - r)
"""

import random
from typing import Dict, List, Optional, Tuple

from backend.app.reward import TACTICS


def sample_beta(alpha: float, beta: float, rng: Optional[random.Random] = None) -> float:
    """Draw a single sample from Beta(alpha, beta)."""
    r = rng or random
    return r.betavariate(alpha, beta)


def update_arm(alpha: float, beta: float, reward: float) -> Tuple[float, float]:
    """Perform fractional Beta update given reward r in [0, 1]."""
    if not 0.0 <= reward <= 1.0:
        raise ValueError(f"Reward must be in [0, 1], got {reward}")
    return alpha + reward, beta + (1.0 - reward)


def arm_mean(alpha: float, beta: float) -> float:
    """Calculate the expected posterior mean alpha / (alpha + beta)."""
    return alpha / (alpha + beta)


class ThompsonSampler:
    """Thompson Sampling multi-armed bandit."""

    def __init__(
        self,
        arms: Tuple[str, ...] = TACTICS,
        prior_alpha: float = 1.0,
        prior_beta: float = 1.0,
        seed: Optional[int] = None,
    ):
        self.arms = list(arms)
        self.prior_alpha = float(prior_alpha)
        self.prior_beta = float(prior_beta)
        self.rng = random.Random(seed)
        self.alpha: Dict[str, float] = {arm: self.prior_alpha for arm in self.arms}
        self.beta: Dict[str, float] = {arm: self.prior_beta for arm in self.arms}
        self.pulls: Dict[str, int] = {arm: 0 for arm in self.arms}

    def sample_posteriors(self) -> Dict[str, float]:
        """Draw one sample from each arm's posterior."""
        return {
            arm: sample_beta(self.alpha[arm], self.beta[arm], self.rng)
            for arm in self.arms
        }

    def select(self) -> Tuple[str, Dict[str, float]]:
        """Sample all arms and return the winning arm along with all drawn samples."""
        samples = self.sample_posteriors()
        chosen = max(samples, key=samples.get)
        return chosen, samples

    def update(self, arm: str, reward: float) -> None:
        """Update posterior belief for the selected arm with observed reward."""
        if arm not in self.alpha:
            raise ValueError(f"Unknown arm '{arm}', expected one of {self.arms}")
        new_alpha, new_beta = update_arm(self.alpha[arm], self.beta[arm], reward)
        self.alpha[arm] = new_alpha
        self.beta[arm] = new_beta
        self.pulls[arm] += 1

    def posterior_means(self) -> Dict[str, float]:
        """Return the current posterior mean for every arm."""
        return {arm: arm_mean(self.alpha[arm], self.beta[arm]) for arm in self.arms}

    def get_state(self) -> Dict[str, dict]:
        """Return full state dictionary for persistence/API inspection."""
        return {
            arm: {
                "alpha": self.alpha[arm],
                "beta": self.beta[arm],
                "pulls": self.pulls[arm],
                "mean": arm_mean(self.alpha[arm], self.beta[arm]),
            }
            for arm in self.arms
        }

    @classmethod
    def from_state(
        cls,
        state: Dict[str, dict],
        arms: Tuple[str, ...] = TACTICS,
        seed: Optional[int] = None,
    ) -> "ThompsonSampler":
        """Instantiate sampler from stored state."""
        sampler = cls(arms=arms, seed=seed)
        for arm in sampler.arms:
            if arm in state:
                sampler.alpha[arm] = float(state[arm]["alpha"])
                sampler.beta[arm] = float(state[arm]["beta"])
                sampler.pulls[arm] = int(state[arm].get("pulls", 0))
        return sampler

