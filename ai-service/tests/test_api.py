import pytest
from fastapi.testclient import TestClient

from api import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_bandit_select_returns_valid_tactic(client):
    payload = {
        "arms": {
            "urgency": {"alpha": 1.0, "beta": 1.0},
            "authority": {"alpha": 1.0, "beta": 1.0},
            "invoice": {"alpha": 2.5, "beta": 1.0},
            "credential": {"alpha": 1.0, "beta": 2.0},
        }
    }
    response = client.post("/bandit/select", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["tactic"] in payload["arms"]
    assert set(body["samples"].keys()) == set(payload["arms"].keys())
    assert all(0.0 < v < 1.0 for v in body["samples"].values())


def test_bandit_update_math(client):
    response = client.post("/bandit/update",
                           json={"arm": "invoice", "reward": 0.7, "alpha": 1.0, "beta": 1.0})
    assert response.status_code == 200
    body = response.json()
    assert body["alpha"] == pytest.approx(1.7)
    assert body["beta"] == pytest.approx(1.3)
    assert body["mean"] == pytest.approx(1.7 / 3.0)


def test_bandit_update_rejects_bad_reward(client):
    response = client.post("/bandit/update",
                           json={"arm": "invoice", "reward": 1.5, "alpha": 1.0, "beta": 1.0})
    assert response.status_code == 422


def test_scenario_evaluate_valid(client):
    scenario = {
        "tactic": "invoice", "difficulty": 3,
        "sender_name": "Billing Desk",
        "sender_email": "billing@aurora-cloud.example.com",
        "subject": "Invoice 10458 - payment due",
        "body": ("This is a reminder that invoice 10458 is due for payment in "
                 "the amount of one thousand two hundred and forty dollars. "
                 "The invoice relates to the software maintenance subscription "
                 "for your department and was issued on the first of the month. "
                 "Payment terms are net fifteen. If payment has already been "
                 "made, please disregard this reminder. Otherwise, please "
                 "process the payment through the usual channels and update "
                 "the payment reference."),
        "indicators": ["urgency deadline", "payment request"],
        "hook": "Looks like a routine monthly finance reminder.",
    }
    response = client.post("/scenario/evaluate", json={"scenario": scenario})
    assert response.json()["valid"] is True


def test_scenario_evaluate_rejects_real_domain(client):
    scenario = {
        "tactic": "invoice", "difficulty": 3,
        "sender_name": "Billing Desk",
        "sender_email": "billing@paypal.com",
        "subject": "Invoice", "body": "x" * 120,
        "indicators": ["a"], "hook": "h" * 20,
    }
    response = client.post("/scenario/evaluate", json={"scenario": scenario})
    assert response.json()["valid"] is False


def test_scenario_freshness(client):
    history = [{"subject": "Overdue invoice", "body": "Please settle invoice 10458 immediately today."}]
    candidate = {"subject": "Overdue invoice", "body": "Please settle invoice 10458 immediately today."}
    response = client.post("/scenario/freshness",
                           json={"candidate": candidate, "history": history, "threshold": 0.85})
    body = response.json()
    assert body["passed"] is False
    assert body["max_cosine"] > 0.9


def test_metrics_session_regret(client):
    response = client.post("/metrics/session", json={
        "true_means": {"urgency": 0.2, "authority": 0.3, "invoice": 0.9, "credential": 0.4},
        "rounds": [
            {"arm": "invoice", "reward": 1.0},
            {"arm": "urgency", "reward": 0.0},
        ],
    })
    assert response.status_code == 200
    body = response.json()
    assert body["cum_reward"] == [1.0, 1.0]
    assert body["cum_regret"] == [0.0, 0.7]  # first arm is optimal; second gives 0.9-0.2
    assert body["optimal_rate"] == [1.0, 0.0]


def test_behavior_predict_without_model_returns_503(client):
    if client.get("/model/info").json().get("loaded", False):
        pytest.skip("model already loaded")
    response = client.post("/behavior/predict", json={
        "features": {"tactic": "invoice", "difficulty": 3, "role": "Accountant",
                     "department": "Finance", "base_alertness": 0.55,
                     "times_seen_tactic": 0, "last_response": None,
                     "safe_streak": 0, "round_no": 1, "employee_code": "emp_001"}})
    assert response.status_code == 503


def test_behavior_predict_with_model(client):
    info = client.get("/model/info").json()
    if not info.get("loaded", False):
        pytest.skip("no trained model available")
    response = client.post("/behavior/predict", json={
        "features": {"tactic": "invoice", "difficulty": 3, "role": "Accountant",
                     "department": "Finance", "base_alertness": 0.55,
                     "times_seen_tactic": 2, "last_response": "report",
                     "safe_streak": 2, "round_no": 5, "employee_code": "emp_042"}})
    assert response.status_code == 200
    body = response.json()
    assert set(body["probs"].keys()) == {"ignore", "report", "click", "credentials"}
    assert body["predicted"] in body["probs"]
    assert sum(body["probs"].values()) == pytest.approx(1.0, abs=1e-6)
    assert body["predicted"] == max(body["probs"], key=body["probs"].get)


def test_model_info_exposes_metadata(client):
    info = client.get("/model/info").json()
    assert "loaded" in info
    if info["loaded"]:
        assert info["feature_count"] > 0
        assert 0.0 < info["accuracy"] <= 1.0