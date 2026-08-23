# SecureTrain — Adaptive AI Security Awareness Trainer

An RL agent (Thompson Sampling) learns which phishing *tactic* each employee is weak to, an LLM writes contextualized training scenarios for that tactic, and a simulated employee's response updates the agent.

**Status:** Stages 1–6 done — full adaptive loop runs end-to-end with a React dashboard.

- Full design: [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md)
- Stack: React + TypeScript · Node/Express + TypeScript · MongoDB · Python/FastAPI + scikit-learn · Groq API

> This is a **simulation-only security-awareness project**: synthetic employees, fictional scenarios shown only inside the app, no real emails, no credential collection, no real targets.

## Quick start

Requires: Python 3.12+, Node 22+, and a local MongoDB on `27017`.

```bash
# 1. Python AI service (bandit, behavior model, freshness, scenario lint)
cd ai-service
pip install fastapi "uvicorn[standard]" httpx pydantic scikit-learn matplotlib
python classifier.py train        # trains the simulated behavior model (once)
python -m uvicorn api:app --port 8000

# 2. Seed MongoDB with the canonical 100-employee workforce
#    (new terminal)
node database/init.js
node database/seed.js             # requires the Python service above

# 3. Backend API (Express + TS)
cd backend
npm install
npm run dev                       # http://localhost:4000

# 4. Dashboard (React + TS, solar-light theme)
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

Open `http://localhost:5173` — pick an employee, start a session (probabilistic /
classifier / **you as the employee**), watch the bandit's posteriors move, and run
experiment grids in the Analytics tab.

### Standalone tools (no servers needed)

```bash
cd ai-service
python bandit.py              # watch Thompson Sampling learn a fake employee's weak spot
python employee_simulator.py  # inspect the synthetic workforce
python -m pytest              # run the test suite
python run_experiment.py      # full offline evaluation -> results/ (CSVs + figures)
python generate_scenarios.py  # LLM-first scenario generation (template fallback)
```

### Live-demo flow (Stages 6 UI coming next)

1. `POST /api/demo/warm-start {"employee_id": "...", "rounds": 50}` — pre-seed a profile.
2. `POST /api/training/sessions {"employee_id": "...", "selector": "thompson", "behavior_source": "human", "mode": "demo", "inherit_bandit_from": "<warm session id>"}` — you are the employee.
3. `POST /api/training/sessions/:id/rounds` — get a scenario; `PATCH .../rounds/:n/response {"response": "click"}` — answer.

## Development stages

| Stage | Scope | Status |
|-------|-------|--------|
| 1 | Bandit + reward + employee simulator + tests | done |
| 2 | Offline evaluation (TS vs random, regret curves) | done — TS beats random 188 vs 127 reward, regret 12.5 vs 73.8 |
| 3 | LLM scenario generation + freshness | done — Groq-first with template fallback, schema + safety lint, TF-IDF freshness |
| 4 | FastAPI service + behavior classifier | done — 11 stateless endpoints; classifier at Bayes ceiling (0.47 acc), TS converges 10/10 through it |
| 5 | MongoDB + Express API + full evaluation runs | done — 100-employee seed, session/round/batch/export/experiments endpoints; API grid: TS 90.1 vs random 63.3 reward, 100% discovery |
| 6 | React dashboard + docs + demo recording | done — solar-light dashboard: employee tiles, live inbox (human mode), posterior bars, reward/response/share charts, experiment runner |
| 5 | MongoDB + Express API + full evaluation runs | pending |
| 6 | React dashboard + docs + demo recording | pending |
