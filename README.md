# SecureTrain — Adaptive AI Security Awareness Trainer

An RL agent (Thompson Sampling) learns which phishing *tactic* each employee is weak to, an LLM writes contextualized training scenarios for that tactic, and a simulated employee's response updates the agent.

**Status:** Stage 1 — core learning loop (bandit + simulated employees), no servers yet.

- Full design: [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md)
- Stack: React + TypeScript · Node/Express + TypeScript · MongoDB · Python/FastAPI · Groq API

> This is a **simulation-only security-awareness project**: synthetic employees, fictional scenarios shown only inside the app, no real emails, no credential collection, no real targets.

## Quick start (Stage 1)

```bash
cd ai-service
python bandit.py              # watch Thompson Sampling learn a fake employee's weak spot
python employee_simulator.py  # inspect the synthetic workforce
python -m pytest              # run the test suite
python run_experiment.py      # full evaluation: TS vs random (CSVs + figures -> ../results)
```

## Development stages

| Stage | Scope | Status |
|-------|-------|--------|
| 1 | Bandit + reward + employee simulator + tests | done |
| 2 | Offline evaluation (TS vs random, regret curves) | done — TS beats random 188 vs 127 reward, regret 12.5 vs 73.8 |
| 3 | LLM scenario generation + freshness | done — Groq-first with template fallback, schema + safety lint, TF-IDF freshness |
| 4 | FastAPI service + behavior classifier | done — 9 stateless endpoints; classifier at Bayes ceiling (0.47 acc), TS converges 10/10 through it |
| 5 | MongoDB + Express API + full evaluation runs | pending |
| 5 | MongoDB + Express API + full evaluation runs | pending |
| 6 | React dashboard + docs + demo recording | pending |
