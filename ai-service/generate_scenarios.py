"""Scenario generation: Groq LLM first, local template fallback.

Reads GROQ_API_KEY / GROQ_MODEL_BULK / GROQ_MODEL_DEMO from the
environment (optionally a .env file at the repo root). If no key is set,
or the call fails or is rate-limited, generation falls back to the
hand-written template library in prompts/templates/.

Usage:
    python generate_scenarios.py                 # demo: 3 scenarios, random tactic
    python generate_scenarios.py --tactic invoice --count 5
    python generate_scenarios.py --pool          # offline pool -> ../results/scenario_pool.json
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path
from typing import Dict, List, Optional

import httpx

from freshness import FreshnessChecker
from scenario import validate_scenario

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "prompts"
TEMPLATES_DIR = PROMPTS_DIR / "templates"
RESULTS_DIR = REPO_ROOT / "results"

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

FICTIONAL_COMPANIES = (
    "Aurora Cloud",
    "Northwind Logistics",
    "Vantage Partners",
    "Ironpeak Systems",
    "Harborline Group",
    "Crestwood Consulting",
)

STYLE_SEEDS = (
    "formal corporate memo",
    "casual colleague note",
    "automated system notification",
    "overworked manager's quick ask",
    "compliance official notice",
)


def load_env() -> None:
    """Load KEY=VALUE lines from a .env file at the repo root, if present."""
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def system_prompt() -> str:
    return (PROMPTS_DIR / "system_prompt.txt").read_text(encoding="utf-8")


def build_user_prompt(tactic: str, difficulty: int, role: str = "employee",
                      department: str = "General", company: str = "Aurora Cloud",
                      style: str = "formal corporate memo",
                      recent_subjects: Optional[List[str]] = None) -> str:
    """The per-request context sent to the LLM."""
    parts = [
        f"Generate one phishing scenario for a security-awareness training simulation.",
        f"Target: {role} in the {department} department.",
        f"Company name to use: {company}.",
        f"Tactic: {tactic}.",
        f"Difficulty target: {difficulty} out of 5.",
        f"Writing style: {style}.",
        "Do not reuse or paraphrase any of these recent subject lines: "
        + ("; ".join(recent_subjects) if recent_subjects else "none yet."),
    ]
    return "\n".join(parts)


def call_groq(user_prompt: str, model: Optional[str] = None,
              temperature: float = 0.9) -> Optional[dict]:
    """Return parsed JSON from the LLM, or None on any failure."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    model = model or os.environ.get("GROQ_MODEL_BULK", "llama-3.1-8b-instant")

    try:
        response = httpx.post(
            GROQ_ENDPOINT,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt()},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            },
            timeout=30.0,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError) as exc:
        print(f"  [llm] generation failed ({type(exc).__name__}), using template fallback", file=sys.stderr)
        return None


def load_template_pool() -> Dict[str, List[dict]]:
    """{tactic: [scenario dicts]} from prompts/templates/<tactic>/."""
    pool: Dict[str, List[dict]] = {}
    for tactic_dir in TEMPLATES_DIR.iterdir():
        if not tactic_dir.is_dir():
            continue
        pool[tactic_dir.name] = []
        for path in sorted(tactic_dir.glob("*.json")):
            pool[tactic_dir.name].append(json.loads(path.read_text(encoding="utf-8")))
    return pool


def template_scenario(tactic: str, rng: Optional[random.Random] = None,
                      pool: Optional[Dict[str, List[dict]]] = None) -> dict:
    """Pick a random hand-written scenario for the tactic."""
    rng = rng or random.Random()
    pool = pool or load_template_pool()
    choices = pool.get(tactic, [])
    if not choices:
        raise ValueError(f"no templates available for tactic {tactic!r}")
    return dict(rng.choice(choices))


def generate_scenario(tactic: str, difficulty: int = 3,
                      role: str = "employee", department: str = "General",
                      recent_subjects: Optional[List[str]] = None,
                      rng: Optional[random.Random] = None,
                      history: Optional[List[dict]] = None,
                      freshness: Optional[FreshnessChecker] = None) -> dict:
    """Generate one validated, fresh scenario.

    Order: LLM -> validate -> freshness re-check (regenerate up to 2 more
    times) -> template fallback -> freshness re-check -> best effort.
    Returns a scenario dict with an added 'generation_source' field.
    """
    rng = rng or random.Random()
    freshness = freshness or FreshnessChecker()
    history = history or []
    company = rng.choice(FICTIONAL_COMPANIES)
    style = rng.choice(STYLE_SEEDS)

    for attempt in range(3):
        raw = call_groq(build_user_prompt(
            tactic, difficulty, role, department, company, style, recent_subjects))
        if raw is not None and validate_scenario(raw)[0]:
            raw["generation_source"] = "llm"
            raw["company"] = company
            if freshness.check(raw, history)["passed"]:
                return raw
    # LLM path exhausted (or no API key): fall back to templates
    pool = load_template_pool()
    for _ in range(3):
        scenario = template_scenario(tactic, rng, pool)
        scenario["generation_source"] = "template"
        scenario["company"] = scenario.get("company", company)
        if freshness.check(scenario, history)["passed"]:
            return scenario
    # give up on freshness but keep a valid scenario (flagged for later logging)
    scenario = template_scenario(tactic, rng, pool)
    scenario["generation_source"] = "template"
    scenario["company"] = company
    return scenario


def _demo() -> None:
    load_env()
    print("Scenario generation demo (template fallback unless GROQ_API_KEY is set)\n")
    rng = random.Random(7)
    from bandit import TACTICS
    for tactic in TACTICS:
        scenario = generate_scenario(tactic, difficulty=3, role="Accountant",
                                     department="Finance", rng=rng)
        print(f"[{tactic} / {scenario['generation_source']}]")
        print(f"  {scenario['sender_name']} <{scenario['sender_email']}>")
        print(f"  Subject: {scenario['subject']}")
        print(f"  Body: {scenario['body'][:160]}...")
        print(f"  Indicators: {scenario['indicators']}\n")


def _build_pool(per_tactic: int) -> None:
    """Generate an offline pool of validated scenarios -> results/scenario_pool.json."""
    load_env()
    from bandit import TACTICS
    pool = {}
    for tactic in TACTICS:
        bucket = []
        for _ in range(per_tactic):
            scenario = generate_scenario(tactic, difficulty=3)
            bucket.append(scenario)
        pool[tactic] = bucket
        print(f"{tactic}: {len(bucket)} scenarios")
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "scenario_pool.json").write_text(
        json.dumps(pool, indent=2), encoding="utf-8")
    print(f"\npool written to {RESULTS_DIR / 'scenario_pool.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate phishing-awareness scenarios")
    parser.add_argument("--tactic", choices=("urgency", "authority", "invoice", "credential"))
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--pool", action="store_true", help="build offline pool to results/")
    args = parser.parse_args()

    if args.pool:
        _build_pool(per_tactic=args.count if args.count > 1 else 3)
        return
    _demo()


if __name__ == "__main__":
    main()