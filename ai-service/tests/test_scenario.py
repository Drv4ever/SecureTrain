import pytest

from scenario import Scenario, validate_scenario


def valid_payload(**overrides):
    base = {
        "tactic": "invoice",
        "difficulty": 3,
        "sender_name": "Billing Desk",
        "sender_email": "billing@aurora-cloud.example.com",
        "subject": "Invoice 10458 - payment due",
        "body": ("This is a reminder that invoice 10458 is due for payment "
                 "in the amount of one thousand two hundred and forty dollars. "
                 "The invoice relates to the software maintenance subscription "
                 "for your department and was issued on the first of the month. "
                 "Payment terms are net fifteen. If payment has already been "
                 "made, please disregard this reminder. Otherwise, please "
                 "process the payment through the usual channels and update "
                 "the payment reference. A copy of the invoice is available "
                 "in the billing portal under your account."),
        "indicators": ["urgency deadline", "payment request"],
        "hook": "Looks like a routine monthly finance reminder.",
    }
    base.update(overrides)
    return base


def test_valid_scenario_passes():
    valid, issues = validate_scenario(valid_payload())
    assert valid is True
    assert issues == []


def test_wrong_tactic_fails_schema():
    valid, issues = validate_scenario(valid_payload(tactic="blackmail"))
    assert valid is False
    assert any("schema" in issue for issue in issues)


def test_missing_fields_fail_schema():
    payload = valid_payload()
    del payload["body"]
    valid, issues = validate_scenario(payload)
    assert valid is False


def test_real_domain_rejected():
    valid, issues = validate_scenario(valid_payload(sender_email="billing@paypal.com"))
    assert valid is False
    assert any("fictional" in issue for issue in issues)


def test_url_in_body_rejected():
    valid, issues = validate_scenario(valid_payload(
        body="Please visit https://billing.example.com to pay the invoice."))
    assert valid is False
    assert any("URL" in issue for issue in issues)


def test_banned_lure_keyword_rejected():
    valid, issues = validate_scenario(valid_payload(subject="Your Paypal account is locked"))
    assert valid is False
    assert any("banned lure" in issue for issue in issues)


def test_payload_download_language_rejected():
    valid, issues = validate_scenario(valid_payload(
        body="Please open the attachment invoice.exe to review the charges."))
    assert valid is False
    assert any("payload" in issue for issue in issues)


def test_empty_indicators_fail_schema():
    valid, issues = validate_scenario(valid_payload(indicators=[]))
    assert valid is False


def test_whitespace_only_indicators_cleaned():
    valid, issues = validate_scenario(valid_payload(indicators=["  ", "   "]))
    assert valid is False


def test_scenario_model_roundtrip():
    scenario = Scenario(**valid_payload())
    assert scenario.tactic == "invoice"
    assert scenario.difficulty == 3