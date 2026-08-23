"""FastAPI service: stateless compute for the adaptive training loop.

Node.js owns persistence (Stage 5). State is passed in and returned;
nothing is stored here. Endpoints (docs/BLUEPRINT.md, section 13):

    POST /bandit/select       arms -> chosen tactic + posterior samples
    POST /bandit/update       arm + reward + current (alpha,beta) -> new state
    POST /behavior/predict    observable features -> response probabilities
    POST /behavior/train      retrain the behavior classifier
    GET  /model/info          trained-model metadata
    POST /scenario/evaluate   schema + safety lint on a scenario
    POST /scenario/freshness  similarity vs history -> pass/regenerate
    POST /metrics/session     rounds + true means -> regret / reward curves
    GET  /healthz

Run:  uvicorn api:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from bandit import ThompsonSampler
from classifier import BehaviorClassifier
from freshness import FreshnessChecker
from scenario import validate_scenario


class ArmState(BaseModel):
    alpha: float = Field(gt=0)
    beta: float = Field(gt=0)


class BanditSelectRequest(BaseModel):
    arms: Dict[str, ArmState]


class BanditSelectResponse(BaseModel):
    tactic: str
    samples: Dict[str, float]


class BanditUpdateRequest(BaseModel):
    arm: str
    reward: float = Field(ge=0, le=1)
    alpha: float = Field(gt=0)
    beta: float = Field(gt=0)


class BanditUpdateResponse(BaseModel):
    alpha: float
    beta: float
    mean: float
    variance: float


class BehaviorPredictRequest(BaseModel):
    features: dict


class BehaviorTrainRequest(BaseModel):
    n_employees: int = 100
    rounds_per_employee: int = 500
    seed: int = 42


class ScenarioEvaluateRequest(BaseModel):
    scenario: dict


class FreshnessRequest(BaseModel):
    candidate: dict
    history: List[dict] = []
    threshold: float = 0.85


class MetricsRequest(BaseModel):
    true_means: Dict[str, float]
    rounds: List[dict]


class MetricsResponse(BaseModel):
    cum_reward: List[float]
    cum_regret: List[float]
    optimal_rate: List[float]


classifier: Optional[BehaviorClassifier] = None


def load_classifier() -> Optional[BehaviorClassifier]:
    try:
        return BehaviorClassifier()
    except FileNotFoundError:
        return None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global classifier
    classifier = load_classifier()
    yield


app = FastAPI(title="SecureTrain AI Service", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "model_loaded": classifier is not None}


# ---------- bandit ----------

@app.post("/bandit/select", response_model=BanditSelectResponse)
def bandit_select(request: BanditSelectRequest) -> BanditSelectResponse:
    sampler = ThompsonSampler.from_state({
        "arms": {name: {"alpha": s.alpha, "beta": s.beta, "pulls": 0}
                 for name, s in request.arms.items()},
        "prior_alpha": 1.0,
        "prior_beta": 1.0,
    })
    samples = sampler.sample_posteriors()
    return BanditSelectResponse(tactic=sampler.select(), samples=samples)


@app.post("/bandit/update", response_model=BanditUpdateResponse)
def bandit_update(request: BanditUpdateRequest) -> BanditUpdateResponse:
    alpha = request.alpha + request.reward
    beta = request.beta + (1.0 - request.reward)
    total = alpha + beta
    mean = alpha / total
    variance = (alpha * beta) / (total * total * (total + 1.0))
    return BanditUpdateResponse(alpha=alpha, beta=beta, mean=mean, variance=variance)


# ---------- behavior classifier ----------

@app.post("/behavior/predict")
def behavior_predict(request: BehaviorPredictRequest) -> dict:
    if classifier is None:
        raise HTTPException(status_code=503, detail="behavior model not trained; POST /behavior/train")
    try:
        return classifier.predict(request.features)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"invalid features: {exc}") from exc


@app.post("/behavior/train")
def behavior_train(request: BehaviorTrainRequest) -> dict:
    from classifier import train_and_save
    global classifier
    artifact = train_and_save(request.n_employees, request.rounds_per_employee, request.seed)
    classifier = BehaviorClassifier()
    return {"trained": True, "metrics": artifact["metrics"]}


@app.get("/model/info")
def model_info() -> dict:
    if classifier is None:
        return {"loaded": False}
    return {"loaded": True, **classifier.info}


# ---------- scenario ----------

@app.post("/scenario/evaluate")
def scenario_evaluate(request: ScenarioEvaluateRequest) -> dict:
    valid, issues = validate_scenario(request.scenario)
    return {"valid": valid, "issues": issues}


@app.post("/scenario/freshness")
def scenario_freshness(request: FreshnessRequest) -> dict:
    checker = FreshnessChecker(threshold=request.threshold)
    return checker.check(request.candidate, request.history)


# ---------- metrics ----------

@app.post("/metrics/session", response_model=MetricsResponse)
def metrics_session(request: MetricsRequest) -> MetricsResponse:
    best = max(request.true_means, key=request.true_means.get)
    cum_reward, cum_regret, optimal = [], [], []
    reward_total = regret_total = 0.0
    for entry in request.rounds:
        arm = entry["arm"]
        reward = entry.get("reward", 0.0)
        reward_total += reward
        regret_total += request.true_means[best] - request.true_means.get(arm, 0.0)
        cum_reward.append(round(reward_total, 4))
        cum_regret.append(round(regret_total, 4))
        optimal.append(1.0 if arm == best else 0.0)
    return MetricsResponse(cum_reward=cum_reward, cum_regret=cum_regret, optimal_rate=optimal)