# Experiment Pre-Registration

Metric and protocol definitions, written down **before** final paper runs (v1 — Stage 2).

## Configuration

| Parameter | Value |
|---|---|
| Population | 100 synthetic employees (`generate_population(seed=42)`), each with exactly one dominant weak arm |
| Dominant-arm gap | susceptibility ≥ 0.65 vs others ≤ 0.45 (guaranteed margin ≥ 0.20) |
| Rounds | 300 primary · 500 robustness check |
| Difficulty | fixed at 3 (keeps true arm means constant → regret well-defined) |
| Conditions | `thompson` vs `random` (identical pipeline except selection policy) |
| Repetitions | ≥ 20 seeds; paired by (employee, seed); same world-RNG seed across conditions |

## Metric Definitions (as implemented in run_experiment.py)

- **Cumulative reward** at round t: Σ detection rewards {credentials 1.0, click 0.7, ignore 0.3, report 0.0}.
- **Cumulative regret** at round t: Σ (E[r | best arm] − E[r | chosen arm]) using simulator ground truth.
- **Optimal-arm rate**: fraction of rounds choosing the true best arm.
- **Discovery round**: first round where the posterior-mean argmax equals the employee's weakest tactic for ≥10 consecutive rounds (stability rule).
- **Ranking correct**: final posterior argmax equals true weakest tactic.
- **CI**: mean ± 1.96·s/√n across seeds of per-seed population averages.

## Statistical Plan

Wilcoxon signed-rank on paired final cumulative reward (TS vs random), α = 0.05; medians ± IQR for discovery rounds.

## Acceptance Criteria

1. TS cumulative regret visibly sublinear vs random's linear growth.
2. Discovery accuracy > 90% by round ~150.
3. Final-reward difference statistically significant.

## Results Snapshot (Stage 2 run)

100 employees × 300 rounds × 20 seeds, difficulty 3:

| Condition | Final reward | Final regret |
|---|---|---|
| Thompson Sampling | 188.3 ± 1.0 | 12.5 ± 0.2 |
| Random | 127.0 ± 0.6 | 73.8 ± 0.7 |

Discovery found in 100% of sessions, median round 7 (IQR 2–15); final ranking correct 100%. All acceptance criteria met.

## Known Observations / Threats to Validity

1. **Easy-mode population**: the enforced ≥0.20 susceptibility gap makes discovery fast (median round 7). A harder ablation with narrow gaps (e.g., dominant ∈ [0.50, 0.62]) should be added for the robustness section so reviewers don't read the speed as an artifact.
2. **Population-level share chart is flat by design**: dominant arms are uniformly distributed across employees, so average selection share stays ≈25% per arm. The exploration→exploitation story needs a **single-employee trajectory figure** (add before paper submission).
3. No LLM in this loop (template-free probabilistic environment); LLM-in-loop realism subset deferred to Stage 3+.
4. Regret is exactly computable only because the environment is ours — a strength for methodology, not evidence about real humans.

## Behavior Classifier (Stage 4) — fidelity report

Trained: 50,000 interactions (100 employees × 500 rounds, random-tactic sessions, seed 42), multinomial logistic regression (lbfgs). Features are observable-only **plus employee identity and identity×tactic interactions** — without those the model structurally cannot represent per-employee-per-tactic tendencies and collapses to the majority class (measured 0.434 acc / 0.154 macro-F1). With them:

| Metric | Value | Note |
|---|---|---|
| accuracy | 0.470 | ≈ Bayes ceiling of the stochastic simulator (~0.46 est.) |
| macro-F1 | 0.328 | |
| closed-loop convergence | 10/10 sessions | TS still identifies the true weak tactic when the "employee" is the classifier |

Residual error is irreducible simulator randomness, not model failure. The classifier is a *simulated behavior model* — never presented as a real-human predictor. Model artifact: `ai-service/models/behavior_model.pkl` (gitignored; regenerate with `python classifier.py train`).
