import os

os.environ.setdefault("JWT_SECRET", "test-only-secret")

from backend.app.auth import create_token, decode_token, hash_password, verify_password
from backend.app.reward import get_detection_reward, get_safety_score


def test_password_and_jwt_round_trip():
    encoded = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong", encoded)
    assert decode_token(create_token({"sub": "7", "role": "employee"}))['sub'] == "7"


def test_response_reward_pipeline_is_bounded_and_directional():
    assert get_safety_score("report") == 1.0
    assert get_detection_reward("credentials") == 1.0
    assert 0.0 <= get_detection_reward("click", 0.9) <= 1.0
    assert get_detection_reward("report", 0.0) == 0.0

