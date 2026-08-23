"""Offline evaluation: Thompson Sampling vs random tactic selection.

Runs the complete closed loop WITHOUT any servers or LLM calls:
bandit selects a tactic -> simulated employee responds -> reward ->
bandit update. Produces aggregate curves (CSV) and paper figures (PNG)
in results/.

Usage:
    python run_experiment.py                        # full grid
    python run_experiment.py --seeds 2 --rounds 60  # quick smoke test
    python run_experiment.py --no-plots             # CSVs only
"""

import argparse
import csv
import math
import random
import statistics
import time
from pathlib import Path

from bandit import TACTICS, ThompsonSampler, best_arm
from employee_simulator import (
    generate_population,
    sample_response,
    true_arm_means,
)
from reward import detection_reward

POPULATION_SEED = 42
STABLE_ROUNDS_FOR_DISCOVERY = 10
CONDITIONS = ("thompson", "random")
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

CONDITION_LABELS = {"thompson": "Thompson Sampling", "random": "Random"}
CONDITION_COLORS = {"thompson": "tab:blue", "random": "tab:orange"}


class RandomSelector:
    """Baseline policy: a uniformly random tactic every round."""

    def __init__(self, seed=None):
        self.rng = random.Random(seed)

    def select(self) -> str:
        return self.rng.choice(TACTICS)

    def update(self, arm: str, reward: float) -> None:
        """The random baseline ignores feedback by design."""


def make_selector(condition: str, seed: int):
    if condition == "thompson":
        return ThompsonSampler(seed=seed)
    if condition == "random":
        return RandomSelector(seed=seed)
    raise ValueError(f"unknown condition {condition!r}")


class SessionResult:
    """Everything one session (one employee x one condition x one seed) produces."""

    def __init__(self, n_rounds: int):
        self.trace_reward = [0.0] * n_rounds        # cumulative reward per round
        self.trace_regret = [0.0] * n_rounds        # cumulative regret per round
        self.trace_optimal = [0.0] * n_rounds       # 1.0 if best arm was chosen
        self.trace_correct = [0.0] * n_rounds       # 1.0 if posterior argmax is the true weak arm (thompson only)
        self.trace_share = {arm: [0.0] * n_rounds for arm in TACTICS}
        self.discovery_round = None                 # first round where argmax has matched for STABLE_ROUNDS_FOR_DISCOVERY
        self.final_reward = 0.0
        self.final_regret = 0.0
        self.ranking_correct = False


def run_session(employee, condition: str, n_rounds: int, difficulty: int,
                seed: int, employee_index: int) -> SessionResult:
    """Play one full training session against one synthetic employee."""
    selector = make_selector(condition, seed=seed)
    world = random.Random((seed << 20) ^ (employee_index + 1))
    means = true_arm_means(employee, difficulty)
    best = best_arm(means)
    weakest = employee.weakest_tactic()
    is_bandit = isinstance(selector, ThompsonSampler)

    result = SessionResult(n_rounds)
    counts = {arm: 0 for arm in TACTICS}
    streak = 0

    for i in range(n_rounds):
        round_no = i + 1
        arm = selector.select()
        response = sample_response(employee, arm, difficulty, rng=world)
        reward = detection_reward(response)
        selector.update(arm, reward)

        counts[arm] += 1
        result.final_reward += reward
        result.final_regret += means[best] - means[arm]

        result.trace_reward[i] = result.final_reward
        result.trace_regret[i] = result.final_regret
        result.trace_optimal[i] = 1.0 if arm == best else 0.0
        for tactic in TACTICS:
            result.trace_share[tactic][i] = counts[tactic] / round_no

        if is_bandit:
            estimates = selector.posterior_means()
            learned_best = max(estimates, key=estimates.get)
            correct_now = learned_best == weakest
            result.trace_correct[i] = 1.0 if correct_now else 0.0
            streak = streak + 1 if correct_now else 0
            if result.discovery_round is None and streak >= STABLE_ROUNDS_FOR_DISCOVERY:
                result.discovery_round = round_no - STABLE_ROUNDS_FOR_DISCOVERY + 1

    if is_bandit:
        estimates = selector.posterior_means()
        result.ranking_correct = max(estimates, key=estimates.get) == weakest
    return result


class GridAccumulator:
    """Per-seed population-average curves for one condition.

    merge() folds one session's traces into this seed's rows as a running
    sum; finish_seed() divides by the number of employees once the seed's
    last session has been merged.
    """

    def __init__(self, n_seeds: int, n_rounds: int):
        self.n_seeds = n_seeds
        self.cum_reward = [[0.0] * n_rounds for _ in range(n_seeds)]
        self.cum_regret = [[0.0] * n_rounds for _ in range(n_seeds)]
        self.optimal_rate = [[0.0] * n_rounds for _ in range(n_seeds)]
        self.discovery_accuracy = [[0.0] * n_rounds for _ in range(n_seeds)]
        self.arm_share = [{arm: [0.0] * n_rounds for arm in TACTICS} for _ in range(n_seeds)]

    def merge(self, seed_idx: int, result: SessionResult, weight: float) -> None:
        for i, value in enumerate(result.trace_reward):
            self.cum_reward[seed_idx][i] += value * weight
        for i, value in enumerate(result.trace_regret):
            self.cum_regret[seed_idx][i] += value * weight
        for i, value in enumerate(result.trace_optimal):
            self.optimal_rate[seed_idx][i] += value * weight
        for i, value in enumerate(result.trace_correct):
            self.discovery_accuracy[seed_idx][i] += value * weight
        for arm in TACTICS:
            row = self.arm_share[seed_idx][arm]
            for i, value in enumerate(result.trace_share[arm]):
                row[i] += value * weight


def run_grid(n_employees: int, n_rounds: int, n_seeds: int, difficulty: int):
    """Run every condition x seed x employee. Returns (accumulators, summary_rows)."""
    population = generate_population(seed=POPULATION_SEED)[:n_employees]
    grids = {cond: GridAccumulator(n_seeds, n_rounds) for cond in CONDITIONS}
    summaries = []
    started = time.perf_counter()

    for condition in CONDITIONS:
        for seed_idx in range(n_seeds):
            seed = seed_idx + 1
            for emp_index, emp in enumerate(population):
                result = run_session(emp, condition, n_rounds, difficulty, seed, emp_index)
                grids[condition].merge(seed_idx, result, weight=1.0 / len(population))
                summaries.append({
                    "condition": condition,
                    "seed": seed,
                    "employee": emp.code,
                    "role": emp.role,
                    "final_reward": result.final_reward,
                    "final_regret": result.final_regret,
                    "discovery_round": result.discovery_round,
                    "ranking_correct": result.ranking_correct,
                })
            print(f"[{condition}] seed {seed_idx + 1}/{n_seeds} done")

    print(f"\ngrid finished in {time.perf_counter() - started:.1f}s "
          f"({n_employees} employees x {n_rounds} rounds x {n_seeds} seeds x {len(CONDITIONS)} conditions)")
    return grids, summaries


# ---------- aggregation ----------

def mean_ci(values: list) -> tuple:
    """Mean and half-width of the 95% confidence interval."""
    center = statistics.mean(values)
    spread = 1.96 * statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0
    return center, spread


def mean_ci_curve(rows: list) -> tuple:
    """rows[i] is one seed's curve; returns ([means], [ci_halfwidths]) per position."""
    means, cis = [], []
    for position in zip(*rows):
        center, spread = mean_ci(list(position))
        means.append(center)
        cis.append(spread)
    return means, cis


def curve_mean(rows: list) -> list:
    """Element-wise mean across seed curves (no CI needed)."""
    return [statistics.mean(position) for position in zip(*rows)]


def aggregate(grids: dict) -> dict:
    out = {}
    for condition, grid in grids.items():
        out[condition] = {
            "cum_reward": mean_ci_curve(grid.cum_reward),
            "cum_regret": mean_ci_curve(grid.cum_regret),
            "optimal_rate": mean_ci_curve(grid.optimal_rate),
            "discovery_accuracy": mean_ci_curve(grid.discovery_accuracy),
            "arm_share": {arm: curve_mean([row[arm] for row in grid.arm_share])
                          for arm in TACTICS},
        }
    return out


# ---------- output ----------

def write_curves_csv(aggregates: dict, condition: str, n_rounds: int) -> None:
    data = aggregates[condition]
    path = RESULTS_DIR / f"curves_{condition}.csv"
    columns = ["round",
               "cum_reward_mean", "cum_reward_ci",
               "cum_regret_mean", "cum_regret_ci",
               "optimal_rate_mean", "optimal_rate_ci"]
    columns += [f"share_{arm}" for arm in TACTICS]
    if condition == "thompson":
        columns += ["discovery_accuracy_mean", "discovery_accuracy_ci"]

    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for i in range(n_rounds):
            row = [i + 1,
                   f"{data['cum_reward'][0][i]:.4f}", f"{data['cum_reward'][1][i]:.4f}",
                   f"{data['cum_regret'][0][i]:.4f}", f"{data['cum_regret'][1][i]:.4f}",
                   f"{data['optimal_rate'][0][i]:.4f}", f"{data['optimal_rate'][1][i]:.4f}"]
            row += [f"{data['arm_share'][arm][i]:.4f}" for arm in TACTICS]
            if condition == "thompson":
                row += [f"{data['discovery_accuracy'][0][i]:.4f}",
                        f"{data['discovery_accuracy'][1][i]:.4f}"]
            writer.writerow(row)


def write_summary_csv(summaries: list) -> None:
    path = RESULTS_DIR / "session_summary.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["condition", "seed", "employee", "role",
                         "final_reward", "final_regret", "discovery_round", "ranking_correct"])
        for row in summaries:
            writer.writerow([
                row["condition"], row["seed"], row["employee"], row["role"],
                f'{row["final_reward"]:.2f}', f'{row["final_regret"]:.2f}',
                row["discovery_round"] if row["discovery_round"] is not None else "",
                "TRUE" if row["ranking_correct"] else "FALSE",
            ])


def print_summary(summaries: list, n_employees: int, n_rounds: int, n_seeds: int) -> None:
    print(f"\n{'=' * 72}")
    print(f"RESULTS  ({n_employees} employees, {n_rounds} rounds, {n_seeds} seeds)")
    print(f"{'=' * 72}")

    for condition in CONDITIONS:
        rows = [r for r in summaries if r["condition"] == condition]
        rewards = [r["final_reward"] for r in rows]
        regrets = [r["final_regret"] for r in rows]
        label = CONDITION_LABELS[condition]
        reward_center, reward_spread = mean_ci(rewards)
        regret_center, regret_spread = mean_ci(regrets)
        print(f"{label:<20} final reward {reward_center:7.1f} +/- {reward_spread:4.1f}"
              f"   final regret {regret_center:6.1f} +/- {regret_spread:4.1f}")

    thompson_rows = [r for r in summaries
                     if r["condition"] == "thompson" and r["discovery_round"] is not None]
    if thompson_rows:
        found = [r["discovery_round"] for r in thompson_rows]
        quartiles = statistics.quantiles(found, n=4, method="inclusive")
        correct = statistics.mean(r["ranking_correct"] for r in summaries
                                  if r["condition"] == "thompson")
        share_found = len(thompson_rows) / (n_employees * n_seeds)
        print(f"\ndiscovery ({STABLE_ROUNDS_FOR_DISCOVERY}-round stability rule):")
        print(f"  found in {share_found:5.1%} of sessions | median round "
              f"{quartiles[1]:.0f} (IQR {quartiles[0]:.0f}-{quartiles[2]:.0f})")
        print(f"  final ranking correct in {correct:.1%} of thompson sessions")


# ---------- figures ----------

def plot_all(aggregates: dict, n_rounds: int, meta: str) -> None:
    try:
        import matplotlib
    except ImportError:
        print("\nmatplotlib not installed - skipping figures (pip install matplotlib)")
        return
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rounds = list(range(1, n_rounds + 1))

    def line_figure(metric, title, ylabel, filename, only_thompson=False,
                    reference_line=None):
        plt.figure(figsize=(7, 4.5))
        conditions = ("thompson",) if only_thompson else CONDITIONS
        for condition in conditions:
            means, cis = aggregates[condition][metric]
            color = CONDITION_COLORS[condition]
            plt.plot(rounds, means, color=color, label=CONDITION_LABELS[condition])
            plt.fill_between(rounds, [m - c for m, c in zip(means, cis)],
                             [m + c for m, c in zip(means, cis)],
                             color=color, alpha=0.2)
        if reference_line is not None:
            plt.axhline(reference_line, color="gray", linestyle="--", linewidth=1)
        plt.title(f"{title}\n{meta}", fontsize=10)
        plt.xlabel("round")
        plt.ylabel(ylabel)
        plt.legend(loc="lower right")
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(RESULTS_DIR / filename, dpi=150)
        plt.close()

    line_figure("cum_reward", "Cumulative reward", "cumulative detection reward",
                "graph1_cumulative_reward.png")
    line_figure("cum_regret", "Cumulative regret", "cumulative regret",
                "graph2_regret.png")
    line_figure("discovery_accuracy", "Weakness-discovery accuracy",
                "% employees correctly identified", "graph4_discovery_accuracy.png",
                only_thompson=True, reference_line=0.9)

    # graph 3: stacked selection shares for thompson, with uniform reference
    plt.figure(figsize=(7, 4.5))
    shares = aggregates["thompson"]["arm_share"]
    plt.stackplot(rounds, *[shares[arm] for arm in TACTICS],
                  labels=TACTICS, alpha=0.85)
    plt.axhline(0.25, color="black", linestyle="--", linewidth=1)
    plt.title(f"Tactic selection share over time (Thompson Sampling)\n{meta}", fontsize=10)
    plt.xlabel("round")
    plt.ylabel("selection share")
    plt.legend(loc="upper left", fontsize=8)
    plt.tight_layout()
    plt.savefig(RESULTS_DIR / "graph3_selection_probability.png", dpi=150)
    plt.close()

    print(f"\nfigures written to {RESULTS_DIR}")


# ---------- entry point ----------

def main() -> None:
    parser = argparse.ArgumentParser(description="Thompson Sampling vs random evaluation")
    parser.add_argument("--employees", type=int, default=100)
    parser.add_argument("--rounds", type=int, default=300)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--difficulty", type=int, default=3, choices=(1, 2, 3, 4, 5))
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)
    grids, summaries = run_grid(args.employees, args.rounds, args.seeds, args.difficulty)
    aggregates = aggregate(grids)

    write_curves_csv(aggregates, "thompson", args.rounds)
    write_curves_csv(aggregates, "random", args.rounds)
    write_summary_csv(summaries)
    print(f"\ncurves_thompson.csv, curves_random.csv, session_summary.csv written to {RESULTS_DIR}")

    print_summary(summaries, args.employees, args.rounds, args.seeds)

    if not args.no_plots:
        meta = (f"{args.employees} employees, {args.rounds} rounds, "
                f"{args.seeds} seeds, difficulty {args.difficulty}")
        plot_all(aggregates, args.rounds, meta)


if __name__ == "__main__":
    main()
