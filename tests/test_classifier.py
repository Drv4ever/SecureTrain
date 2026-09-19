from app.classifier import load_classifier, get_classifier_info, score_response


def test_classifier_loading_and_info():
    artifact = load_classifier()
    assert artifact is not None
    assert "model" in artifact

    info = get_classifier_info()
    assert info["loaded"] is True
    assert info["status"] == "Trained & Active"
    assert info["accuracy"] is not None
    assert info["macro_f1"] is not None
    assert len(info["confusion_matrix"]) == 4
    assert len(info["classes"]) == 4
    assert len(info["feature_names"]) == 23


def test_classifier_scoring_determinism():
    s1 = score_response("urgency", "Accountant", "Finance", last_response="none", times_seen=0, round_no=1)
    s2 = score_response("urgency", "Accountant", "Finance", last_response="none", times_seen=0, round_no=1)
    assert s1 == s2
    assert 0.0 <= s1 <= 1.0
