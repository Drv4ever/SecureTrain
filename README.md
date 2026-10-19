# Safeguard

Safeguard is a simulation-only security-awareness trainer. A FastAPI service stores assignments and round history, Thompson Sampling selects the next tactic, an optional Groq integration generates scenarios, and a React/Vite dashboard supports admin and employee workflows.


## Run locally

```powershell
Copy-Item .env.example .env
# Set JWT_SECRET and COMPANY_NAME. GROQ_API_KEY is optional.

## First-time local setup

Before starting the server after cloning, generate the local classifier and RAG index:

```bash
python scripts/train_classifier.py
python scripts/ingest_rag.py
```

The classifier artifact, Chroma vector store, and SQLite database are generated locally and intentionally excluded from Git.
## Safeguard Architecture Diagram

<img width="5473" height="5845" alt="diagram (1)" src="https://github.com/user-attachments/assets/6f2f2962-c51a-4c62-9a28-9c655b797085" />
## Repository layout

```text
backend/app/       FastAPI routes, authentication, database, classifier, and domain logic
frontend/           React/Vite client
rag/indicators/    Markdown phishing-indicator knowledge base
rag/retriever.py   ChromaDB and sentence-transformers retrieval service
llm/service.py     Groq/fallback scenario and feedback generation
llm/prompts/       LLM system prompts
scripts/           Training, ingestion, reset, and evaluation utilities
tests/             Backend tests
```
pip install -r requirements.txt
python scripts/reset_db.py
cd frontend; npm install; npm run build; cd ..
uvicorn backend.app.main:app --reload --port 8000
```

The React build is served at `/` after `frontend/npm run build`. Without a Groq key, scenarios use the safe fallback templates and are labelled in the employee UI.

## Deploy (Vercel + Render)

The frontend and API are deployed separately. Push this repository to a Git provider connected to both services.

1. Create a Vercel project for this repository with **Root Directory** set to `frontend`. The included `frontend/vercel.json` configures the Vite build and `dist` output. Deploy once to get the production Vercel URL.
2. Create a Render Blueprint from the repository root. Render reads `render.yaml`; provide `COMPANY_NAME` and set `CORS_ALLOWED_ORIGINS` to the exact Vercel origin (for example, `https://your-project.vercel.app`, with no trailing slash). The blueprint uses the free web plan, generates `JWT_SECRET`, and trains the classifier during build. SQLite uses the default local path and its data is temporary on Render's free filesystem.
3. In Vercel project settings, add `VITE_API_BASE_URL` with the Render service origin (for example, `https://securetrain-api.onrender.com`) for Production, then redeploy the frontend. Keep the optional `GROQ_API_KEY` only in Render's environment settings; the app uses fallback scenarios when it is absent.
4. Create the first admin through the Render API's `/docs` page using `POST /auth/register` with `role: "client_admin"`. Then sign in at the Vercel site.

The Render blueprint is configured for a free demo service. Render free services sleep after inactivity and their local filesystem is ephemeral, so training data can be lost on a restart or redeploy. The registration route currently allows public account creation, including client-admin accounts, so treat this as a demo deployment and restrict registration before using it with real employee data. `VITE_SHOW_DEMO_CREDENTIALS` is off unless explicitly set to `true`; do not enable it on a public deployment.

## Demo data

`python scripts/reset_db.py` drops and recreates the configured SQLite schema, then seeds exactly five synthetic employees, one demo admin, and no assignment history. It is the repeatable reset path; do not hand-edit `trainer.db`.

The reset script creates `admin@demo.securetrain.test` / `AdminDemo123!` and employee seed accounts with `EmployeeDemo123!` for local demonstration only. Set `VITE_SHOW_DEMO_CREDENTIALS=true` only for a local demo build.

## API highlights

- `/auth/register`, `/auth/login` — JWT authentication for admins and employees.
- `/admin/training-assignments` — configurable title, 1–100 rounds, tactics, and schedule.
- `/employee/round/{id}/respond` and `/employee/round/{id}/feedback` — response, classifier-informed reward, and teaching feedback.
- `/admin/employees/{id}` — employee round history.
- `/admin/reports/export?format=csv|pdf` — organization or employee export.
- `/admin/analytics/sampling?rounds=&repetitions=&seed=` — configurable Thompson/random benchmark.

Set `JWT_SECRET`, `COMPANY_NAME`, and database credentials through environment configuration in production. Never commit `.env` or real API keys. If the previously exposed Groq key was valid, revoke it in the Groq dashboard and scrub it from any public git history.

Notifications are intentionally future scope for this v1. The legacy `notification_seen` column remains for backward-compatible migrations but is not presented as an active product capability.
