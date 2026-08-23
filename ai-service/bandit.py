"""Thompson Sampling with Beta posteriors (Design A).

Every arm keeps a Beta(alpha, beta) belief about its reward rate.
Rewards are fractional values in [0, 1], so one observation updates:

    alpha += reward
    beta  += (1 - reward)

With this fractional update the posterior mean alpha/(alpha+beta) equals
the running average of observed rewards, while the shrinking spread of
the Beta distribution produces exploration automatically: an arm with
few observations can still sample high and get tried.

Selection rule per round: draw one sample per arm, pick the largest.
"""

import random

TACTICS = ("urgency", "authority", "invoice", "credential")


class ThompsonSampler:
    """Bandit over a fixed set of arms; state is JSON/Mongo serializable."""

    def __init__(self, arm_names=TACTICS, prior_alpha=1.0, prior_beta=1.0, seed=None):
        self.arm_names = list(arm_names)
        self.prior_alpha = float(prior_alpha)
        self.prior_beta = float(prior_beta)
        self.rng = random.Random(seed)
        self.alpha = {arm: self.prior_alpha for arm in self.arm_names}
        self.beta = {arm: self.prior_beta for arm in self.arm_names}
        self.pulls = {arm: 0 for arm in self.arm_names}

    def select(self) -> str:
        """Sample every posterior once and return the winning arm."""
        samples = {
            arm: self.rng.betavariate(self.alpha[arm], self.beta[arm])
            for arm in self.arm_names
        }
        return max(samples, key=samples.get)

    def update(self, arm: str, reward: float) -> None:
        """Fold one observed reward into the arm's posterior."""
        if arm not in self.alpha:
            raise ValueError(f"unknown arm {arm!r}")
        if not 0.0 <= reward <= 1.0:
            raise ValueError(f"reward must be in [0, 1], got {reward}")
        self.alpha[arm] += reward
        self.beta[arm] += 1.0 - reward
        self.pulls[arm] += 1

    def posterior_mean(self, arm: str) -> float:
        return self.alpha[arm] / (self.alpha[arm] + self.beta[arm])

    def posterior_means(self) -> dict:
        return {arm: self.posterior_mean(arm) for arm in self.arm_names}

    def total_pulls(self) -> int:
        return sum(self.pulls.values())

    def state(self) -> dict:
        """Plain-dict snapshot for storage (MongoDB later)."""
        return {
            "arms": {
                arm: {
                    "alpha": self.alpha[arm],
                    "beta": self.beta[arm],
                    "pulls": self.pulls[arm],
                }
                for arm in self.arm_names
            },
            "prior_alpha": self.prior_alpha,
            "prior_beta": self.prior_beta,
        }

    @classmethod
    def from_state(cls, state: dict, seed=None) -> "ThompsonSampler":
        sampler = cls(
            arm_names=list(state["arms"].keys()),
            prior_alpha=state["prior_alpha"],
            prior_beta=state["prior_beta"],
            seed=seed,
        )
        for arm, values in state["arms"].items():
            sampler.alpha[arm] = values["alpha"]
            sampler.beta[arm] = values["beta"]
            sampler.pulls[arm] = values.get("pulls", 0)
        return sampler


def best_arm(true_means: dict) -> str:
    """Arm with the highest true expected reward. Used by the evaluation harness only."""
    return max(true_means, key=true_means.get)


def _demo() -> None:
    """Standalone demo: 'invoice' secretly pays best; watch the bandit find it."""
    true_rates = {"urgency": 0.27, "authority": 0.34, "invoice": 0.70, "credential": 0.41}
    sampler = ThompsonSampler(seed=42)
    world = random.Random(7)

    print("Thompson Sampling demo - hidden true rates:", true_rates)
    print(f"\n{'round':>5}  {'chosen':<11}{'reward':>6}   posterior means")
    for t in range(1, 11):
        chosen = sampler.select()
        reward = 1.0 if world.random() < true_rates[chosen] else 0.0
        sampler.update(chosen, reward)
        means = ", ".join(f"{a}={m:.2f}" for a, m in sampler.posterior_means().items())
        print(f"{t:>5}  {chosen:<11}{reward:>6.1f}   {means}")

    learned = max(sampler.posterior_means(), key=sampler.posterior_means().get)
    print(f"\nafter 10 rounds learned best arm = {learned} (true best = {best_arm(true_rates)})")
    print("(with only 10 rounds the leader may still be wrong - variance matters)")


if __name__ == "__main__":
    _demo()
