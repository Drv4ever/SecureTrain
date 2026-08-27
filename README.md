# Adaptive AI Security Awareness Trainer

A closed-loop adaptive cybersecurity awareness trainer that uses a Multi-Armed Bandit (**Thompson Sampling** with Beta posteriors) to discover which phishing tactic each employee is most vulnerable to, an LLM to generate authentic contextual phishing scenarios, and either a synthetic employee or a live human responding.

> **Simulation-Only Security Project:** Purely synthetic employees, safe demonstration domains (`.example.com` / `.test`), no real emails, no real credentials, zero external attack surface.

---

## System Architecture

Deliberately simple, single-service Python architecture:
- **Backend & AI Engine:** Python + FastAPI in a single process.
- **Database:** Relational SQLite via SQLAlchemy (`trainer.db`) — zero server setup.
- **Frontend Dashboard:** Single-page static HTML + Vanilla JS + Chart.js from CDN (no npm, no React, no build steps).
- **LLM Scenario Generator:** Groq API (`llama-3.1-8b-instant` by default) with an offline template fallback library.

```
phishing-trainer/
├── app/
│   ├── main.py            # FastAPI app & all API routes
│   ├── bandit.py           # Thompson Sampling Beta posteriors (select/update)
│   ├── random_selector.py  # Random baseline comparison selector
│   ├── reward.py           # Response → reward mapping (Detection reward & Safety score)
│   ├── simulator.py        # Synthetic employee susceptibility & response probability model
│   ├── llm.py               # Groq LLM client, schema validation & fallback templates
│   ├── models.py            # SQLAlchemy models: Employee, Session, Scenario, Round
│   ├── db.py                 # SQLite database engine & session factory
│   └── schemas.py            # Pydantic request/response schemas
├── static/
│   ├── index.html            # 3-panel single-screen dashboard
│   ├── style.css             # Responsive styling & risk color grading
│   └── app.js                 # Frontend state, polling & Chart.js rendering
├── data/
│   └── seed_employees.py      # Pre-built synthetic workforce seed script
├── scripts/
│   └── run_offline_eval.py    # Multi-seed offline evaluation runner (CSVs + PNG figures)
├── prompts/
│   └── system_prompt.txt      # LLM system prompt & JSON schema
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quickstart (Single Command Run)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) Set your Groq API key for online LLM generation
cp .env.example .env
# Edit .env with your GROQ_API_KEY (if unset, built-in fallback templates are used)

# 3. Launch the application
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000` in your browser.

---

## How It Works

1. **Thompson Sampling Selection:**
   - Each tactic arm maintains a belief distribution $\text{Beta}(\alpha_k, \beta_k)$ initialized to $\text{Beta}(1, 1)$.
   - Each round samples $\tilde{\theta}_k \sim \text{Beta}(\alpha_k, \beta_k)$ and picks $k^* = \arg\max \tilde{\theta}_k$.

2. **Dual Reward Mapping:**
   - **Detection Reward (Drives Bandit):**
     $$\text{credentials} \to 1.0, \quad \text{click} \to 0.7, \quad \text{ignore} \to 0.3, \quad \text{report} \to 0.0$$
     *Learns the employee's weakest spot rather than avoiding it.*
   - **Safety Score (Reported Only):**
     $$\text{report} \to 1.0, \quad \text{ignore} \to 0.6, \quad \text{click} \to 0.2, \quad \text{credentials} \to 0.0$$

3. **Fractional Posterior Update:**
   $$\alpha_k \leftarrow \alpha_k + r, \quad \beta_k \leftarrow \beta_k + (1 - r)$$

---

## Offline Evaluation (Paper / Report Figures)

Run the standalone evaluation grid across 20+ seeds and all employee personas:

```bash
python scripts/run_offline_eval.py
```

Generated artifacts in `results/`:
- `results/evaluation_summary.csv` — numerical reward and regret summary
- `results/cumulative_reward_comparison.png` — Thompson Sampling vs Random baseline reward curves
- `results/regret_curves_comparison.png` — Sublinear regret proof
- `results/optimal_arm_selection_rate.png` — Convergence towards >90% weak arm focus
