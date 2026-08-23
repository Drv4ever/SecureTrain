"""Structural validation and safety linting for generated scenarios.

A scenario must satisfy the JSON schema (validated by pydantic) AND the
safety constraints below. Any failure means the scenario is not stored.

Safety rules (defensive simulation boundary):
- sender_email must use a fictional TLD (.example.com / .test / .invalid)
- no URLs at all in the body (nothing that could be clicked for real)
- no real-world lure keywords (brands, services, agencies)
- no downloadable payload language (.exe / .zip / "open the attachment")
"""

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from bandit import TACTICS

FICTIONAL_TLDS = (".example.com", ".test", ".invalid")

# common lure targets in real phishing; word-boundary matched, case-insensitive
BANNED_KEYWORDS = (
    "google", "microsoft", "adobe", "paypal", "amazon", "apple", "netflix",
    "dropbox", "fedex", "dhl", "amazon pay", "irs", "o365", "outlook",
    "windows update", "bank of", "chase", "wells fargo",
)

BANNED_PAYLOAD_PATTERNS = (".exe", ".scr", ".apk", ".bat", "open the attachment",
                           "click the attachment", "download attached", "enclosed invoice.zip")


class Scenario(BaseModel):
    """The exact contract the LLM must return (prompts/scenario_schema.json)."""

    tactic: Literal["urgency", "authority", "invoice", "credential"]
    difficulty: int = Field(ge=1, le=5)
    sender_name: str = Field(min_length=2, max_length=60)
    sender_email: str = Field(min_length=5)
    subject: str = Field(min_length=5, max_length=120)
    body: str = Field(min_length=60)
    indicators: List[str] = Field(min_length=1, max_length=8)
    hook: str = Field(min_length=10)

    @field_validator("indicators")
    @classmethod
    def indicators_not_empty(cls, value: List[str]) -> List[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("indicators must contain at least one non-empty item")
        return cleaned


def validate_scenario(data: dict) -> tuple:
    """Returns (valid: bool, issues: list[str]). Structural + safety checks."""
    issues = []

    try:
        scenario = Scenario(**data)
    except Exception as exc:  # pydantic.ValidationError
        return False, [f"schema: {exc}"]

    body_lower = scenario.body.lower()
    subject_lower = scenario.subject.lower()
    full_text = f"{scenario.subject} {scenario.body}".lower()

    if not scenario.sender_email.lower().endswith(FICTIONAL_TLDS):
        issues.append(f"sender_email must end with a fictional TLD {FICTIONAL_TLDS}")

    if "http://" in body_lower or "https://" in body_lower or "www." in body_lower:
        issues.append("body must not contain URLs")

    matched = [word for word in BANNED_KEYWORDS
               if re.search(rf"\b{re.escape(word)}\b", full_text)]
    if matched:
        issues.append(f"banned lure keyword(s) present: {matched}")

    matched_payload = [pattern for pattern in BANNED_PAYLOAD_PATTERNS
                       if re.search(rf"\b{re.escape(pattern)}\b", full_text)]
    if matched_payload:
        issues.append(f"payload/download language present: {matched_payload}")

    word_count = len(scenario.body.split())
    if not 60 <= word_count <= 400:
        issues.append(f"body word count {word_count} outside 60..400")

    return len(issues) == 0, issues


def random_template_hint() -> Optional[str]:
    return None  # placeholder for later template mutation hooks