# SecureTrain

SecureTrain is a simulation-only security-awareness trainer. A FastAPI service stores assignments and round history, Thompson Sampling selects the next tactic, an optional Groq integration generates scenarios, and a React/Vite dashboard supports admin and employee workflows.

## Run locally

```powershell
Copy-Item .env.example .env
# Set JWT_SECRET and COMPANY_NAME. GROQ_API_KEY is optional.
pip install -r requirements.txt
python scripts/reset_db.py
cd frontend; npm install; npm run build; cd ..
uvicorn app.main:app --reload --port 8000
```

The React build is served at `/` after `frontend/npm run build`. Without a Groq key, scenarios use the safe fallback templates and are labelled in the employee UI.

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
