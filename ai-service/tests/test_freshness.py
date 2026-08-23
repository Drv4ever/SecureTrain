from freshness import FreshnessChecker, content_hash


def sample_scenario(subject, body):
    return {"subject": subject, "body": body}


def test_content_hash_is_deterministic_and_normalized():
    assert content_hash("HELLO   World") == content_hash("hello world")
    assert content_hash("a") != content_hash("b")


def test_exact_duplicate_is_rejected():
    checker = FreshnessChecker()
    scenario = sample_scenario("Invoice due", "Please pay the invoice as soon as possible.")
    result = checker.check(scenario, [scenario])
    assert result["hash_duplicate"] is True
    assert result["passed"] is False


def test_identical_history_is_detected_via_cosine_too():
    checker = FreshnessChecker()
    history = [sample_scenario("Invoice 10458 overdue", "Your invoice is now overdue. Please settle it immediately.")]
    candidate = sample_scenario("Invoice 10458 overdue", "Your invoice is now overdue. Please settle it immediately.")
    result = checker.check(candidate, history)
    assert result["max_cosine"] > 0.99
    assert result["passed"] is False


def test_distinct_scenario_passes():
    checker = FreshnessChecker()
    history = [sample_scenario("Overdue invoice", "Please settle invoice 10458 immediately.")]
    candidate = sample_scenario("Team lunch invite", "Join us for the quarterly team lunch on Friday at noon.")
    result = checker.check(candidate, history)
    assert result["passed"] is True


def test_empty_history_always_passes():
    checker = FreshnessChecker()
    result = checker.check(sample_scenario("Any subject", "Any body here."), [])
    assert result["passed"] is True


def test_history_window_limits_comparisons():
    checker = FreshnessChecker(history_window=2)
    old = sample_scenario("Ancient invoice", "Very old invoice body that is completely unique in wording here.")
    recent_same = sample_scenario("Invoice 10458 overdue", "Please settle invoice 10458 immediately today.")
    candidate = sample_scenario("Invoice 10458 overdue", "Please settle invoice 10458 immediately today.")
    result = checker.check(candidate, [old, old, old, recent_same])
    # only the last 2 entries are compared; the duplicate IS in them, so still caught
    assert result["passed"] is False


def test_invalid_threshold_rejected():
    try:
        FreshnessChecker(threshold=1.5)
    except ValueError:
        pass
    else:
        raise AssertionError("threshold=1.5 should be rejected")