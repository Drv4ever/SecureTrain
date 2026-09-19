"""Random baseline selector.

Provides the same interface as bandit.py (ThompsonSampler) but selects tactics
uniformly at random without learning. Used as the baseline comparison to prove
Thompson Sampling performs better than chance.
"""

import random
from typing import Dict, List, Optional, Tuple

from backend.app.reward import TACTICS


class RandomSelector:
    """Uniform random baseline selector matching ThompsonSampler interface."""

    def __init__(
        self,
        arms: Tuple[str, ...] = TACTICS,
        seed: Optional[int] = None,
    ):
        self.arms = list(arms)
        self.rng = random.Random(seed)
        self.pulls: Dict[str, int] = {arm: 0 for arm in self.arms}
        self.rewards: Dict[str, float] = {arm: 0.0 for arm in self.arms}

    def sample_posteriors(self) -> Dict[str, float]:
        """Uniform random pseudo-samples for interface compatibility."""
        return {arm: self.rng.random() for arm in self.arms}

    def select(self) -> Tuple[str, Dict[str, float]]:
        """Pick an arm uniformly at random."""
        samples = self.sample_posteriors()
        chosen = self.rng.choice(self.arms)
        return chosen, samples

    def update(self, arm: str, reward: float) -> None:
        """Record pull and reward without updating a prior."""
        if arm not in self.pulls:
            raise ValueError(f"Unknown arm '{arm}', expected one of {self.arms}")
        self.pulls[arm] += 1
        self.rewards[arm] += reward

    def posterior_means(self) -> Dict[str, float]:
        """Empirical average reward per arm (or 0.5 default if unpulled)."""
        return {
            arm: (self.rewards[arm] / self.pulls[arm]) if self.pulls[arm] > 0 else 0.5
            for arm in self.arms
        }

    def get_state(self) -> Dict[str, dict]:
        """Return state dictionary matching ThompsonSampler structure."""
        return {
            arm: {
                "alpha": 1.0 + self.rewards[arm],
                "beta": 1.0 + (self.pulls[arm] - self.rewards[arm]),
                "pulls": self.pulls[arm],
                "mean": (self.rewards[arm] / self.pulls[arm]) if self.pulls[arm] > 0 else 0.5,
            }
            for arm in self.arms
        }

    @classmethod
    def from_state(
        cls,
        state: Dict[str, dict],
        arms: Tuple[str, ...] = TACTICS,
        seed: Optional[int] = None,
    ) -> "RandomSelector":
        """Instantiate random selector from stored state."""
        selector = cls(arms=arms, seed=seed)
        for arm in selector.arms:
            if arm in state:
                selector.pulls[arm] = int(state[arm].get("pulls", 0))
                # compute total reward from alpha if available
                alpha = float(state[arm].get("alpha", 1.0))
                selector.rewards[arm] = max(0.0, alpha - 1.0)
        return selector

