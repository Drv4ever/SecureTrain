"""Offline Evaluation Script: Multi-Armed Bandit vs Random Baseline.

Runs Thompson Sampling vs Uniform Random selection across a population of synthetic
employees and multiple random seeds. Computes cumulative reward, regret curves,
and optimal arm identification rate.

Outputs:
- results/evaluation_summary.csv
- results/cumulative_reward_comparison.png
- results/regret_curves_comparison.png
- results/optimal_arm_selection_rate.png

Run:
    python scripts/run_offline_eval.py
"""

import csv
import sys
from pathlib import Path
from typing import Dict, List

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import matplotlib.pyplot as plt
import numpy as np

from backend.app.bandit import ThompsonSampler
from backend.app.random_selector import RandomSelector
from backend.app.reward import DETECTION_REWARDS, TACTICS, get_detection_reward
from backend.app.simulator import SimulatedEmployee, get_default_employees, response_probabilities, sample_response

RESULTS_DIR = ROOT_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def calculate_expected_rewards(employee: SimulatedEmployee) -> Dict[str, float]:
    """Calculate true expected detection reward for each tactic given ground truth."""
    expected = {}
    for tactic in TACTICS:
        s = employee.get_susceptibility(tactic)
        probs = response_probabilities(s)
        exp_r = sum(probs[resp] * DETECTION_REWARDS[resp] for resp in probs)
        expected[tactic] = exp_r
    return expected


def run_single_simulation(
    employee: SimulatedEmployee,
    selector_type: str,
    n_rounds: int = 200,
    seed: int = 42,
) -> dict:
    """Run one full session of n_rounds for a specific selector and seed."""
    expected_rewards = calculate_expected_rewards(employee)
    best_tactic = max(expected_rewards, key=expected_rewards.get)
    max_expected = expected_rewards[best_tactic]

    if selector_type == "thompson":
        selector = ThompsonSampler(seed=seed)
    elif selector_type == "random":
        selector = RandomSelector(seed=seed)
    else:
        raise ValueError(f"Unknown selector {selector_type}")

    rng = np.random.RandomState(seed)

    rewards = []
    regrets = []
    optimal_choices = []

    for _ in range(n_rounds):
        chosen_tactic, _ = selector.select()
        # Sample response
        s = employee.get_susceptibility(chosen_tactic)
        probs = response_probabilities(s)
        resp = rng.choice(list(probs.keys()), p=list(probs.values()))
        reward = get_detection_reward(resp)

        selector.update(chosen_tactic, reward)

        rewards.append(reward)
        regret = max_expected - expected_rewards[chosen_tactic]
        regrets.append(regret)
        optimal_choices.append(1.0 if chosen_tactic == best_tactic else 0.0)

    cum_reward = np.cumsum(rewards)
    cum_regret = np.cumsum(regrets)

    return {
        "selector": selector_type,
        "employee": employee.name,
        "seed": seed,
        "cum_reward": cum_reward,
        "cum_regret": cum_regret,
        "optimal_rate": np.array(optimal_choices),
        "final_reward": cum_reward[-1],
        "final_regret": cum_regret[-1],
        "pulls": selector.pulls if hasattr(selector, "pulls") else {},
    }


def run_evaluation_suite(
    n_rounds: int = 200,
    n_seeds: int = 25,
):
    """Run full evaluation grid across employees and seeds for Thompson vs Random."""
    employees = get_default_employees()
    selectors = ["thompson", "random"]

    print(f"Starting Offline Evaluation: {len(employees)} employees, {n_seeds} seeds, {n_rounds} rounds per session...")

    all_results = {s: [] for s in selectors}
    summary_rows = []

    for emp in employees:
        print(f"\nEvaluating employee: {emp.name}")
        exp_rewards = calculate_expected_rewards(emp)
        best_tac = max(exp_rewards, key=exp_rewards.get)
        print(f"  True expected rewards: { {k: round(v, 3) for k, v in exp_rewards.items()} } (Best: {best_tac})")

        for sel in selectors:
            sel_rewards = []
            sel_regrets = []
            for seed in range(1, n_seeds + 1):
                res = run_single_simulation(emp, sel, n_rounds=n_rounds, seed=seed)
                all_results[sel].append(res)
                sel_rewards.append(res["final_reward"])
                sel_regrets.append(res["final_regret"])

            mean_rew = np.mean(sel_rewards)
            std_rew = np.std(sel_rewards)
            mean_reg = np.mean(sel_regrets)
            std_reg = np.std(sel_regrets)

            print(f"  [{sel.upper():<8}] Mean Cum. Reward: {mean_rew:.2f} (±{std_rew:.2f}) | Mean Regret: {mean_reg:.2f} (±{std_reg:.2f})")

            summary_rows.append({
                "employee": emp.name,
                "selector": sel,
                "rounds": n_rounds,
                "seeds": n_seeds,
                "mean_reward": round(mean_rew, 2),
                "std_reward": round(std_rew, 2),
                "mean_regret": round(mean_reg, 2),
                "std_regret": round(std_reg, 2),
            })

    # Save CSV summary
    csv_path = RESULTS_DIR / "evaluation_summary.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"\nSaved CSV summary to: {csv_path}")

    # Plotting
    plot_results(all_results, n_rounds)


def plot_results(all_results: Dict[str, list], n_rounds: int):
    """Generate publication-ready figures for reward, regret, and optimal arm rate."""
    rounds_axis = np.arange(1, n_rounds + 1)
    colors = {"thompson": "#2563eb", "random": "#dc2626"}
    labels = {"thompson": "Thompson Sampling (Adaptive)", "random": "Random Baseline (Uniform)"}

    # Figure 1: Cumulative Reward Comparison
    plt.figure(figsize=(8, 5), dpi=300)
    for sel in ["thompson", "random"]:
        runs = np.array([r["cum_reward"] for r in all_results[sel]])
        mean_curve = np.mean(runs, axis=0)
        std_curve = np.std(runs, axis=0)
        plt.plot(rounds_axis, mean_curve, label=labels[sel], color=colors[sel], linewidth=2.2)
        plt.fill_between(rounds_axis, mean_curve - std_curve, mean_curve + std_curve, color=colors[sel], alpha=0.15)

    plt.title("Cumulative Detection Reward: Thompson Sampling vs. Random", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Training Rounds", fontsize=11)
    plt.ylabel("Cumulative Detection Reward", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(frameon=True, fontsize=10)
    plt.tight_layout()
    fig1_path = RESULTS_DIR / "cumulative_reward_comparison.png"
    plt.savefig(fig1_path)
    plt.close()
    print(f"Saved Figure 1: {fig1_path}")

    # Figure 2: Regret Curves (Sublinear vs Linear)
    plt.figure(figsize=(8, 5), dpi=300)
    for sel in ["thompson", "random"]:
        runs = np.array([r["cum_regret"] for r in all_results[sel]])
        mean_curve = np.mean(runs, axis=0)
        std_curve = np.std(runs, axis=0)
        plt.plot(rounds_axis, mean_curve, label=labels[sel], color=colors[sel], linewidth=2.2)
        plt.fill_between(rounds_axis, mean_curve - std_curve, mean_curve + std_curve, color=colors[sel], alpha=0.15)

    plt.title("Cumulative Regret Comparison (Sublinear vs. Linear)", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Training Rounds", fontsize=11)
    plt.ylabel("Cumulative Regret", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(frameon=True, fontsize=10)
    plt.tight_layout()
    fig2_path = RESULTS_DIR / "regret_curves_comparison.png"
    plt.savefig(fig2_path)
    plt.close()
    print(f"Saved Figure 2: {fig2_path}")

    # Figure 3: Optimal Weak-Arm Selection Rate
    plt.figure(figsize=(8, 5), dpi=300)
    window = 15
    for sel in ["thompson", "random"]:
        runs = np.array([r["optimal_rate"] for r in all_results[sel]])
        mean_curve = np.mean(runs, axis=0)
        # Smoothed moving average
        smoothed = np.convolve(mean_curve, np.ones(window) / window, mode="valid")
        smoothed_rounds = rounds_axis[window - 1 :]
        plt.plot(smoothed_rounds, smoothed * 100, label=labels[sel], color=colors[sel], linewidth=2.2)

    plt.axhline(y=25, color="#64748b", linestyle=":", label="Random Chance (25%)")
    plt.title("Convergence Rate on True Weak Tactic", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Training Rounds", fontsize=11)
    plt.ylabel("Optimal Arm Selection (%)", fontsize=11)
    plt.ylim(0, 105)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(frameon=True, fontsize=10)
    plt.tight_layout()
    fig3_path = RESULTS_DIR / "optimal_arm_selection_rate.png"
    plt.savefig(fig3_path)
    plt.close()
    print(f"Saved Figure 3: {fig3_path}")


if __name__ == "__main__":
    run_evaluation_suite(n_rounds=200, n_seeds=20)

