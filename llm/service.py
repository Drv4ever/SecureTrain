"""LLM client, prompt builder, schema validator, and fallback scenario templates.

Uses Groq API (llama-3.1-8b-instant by default) to generate structured phishing scenarios.
Falls back seamlessly to hand-written templates if GROQ_API_KEY is unset or if an API
error occurs.
"""

import json
import os
import random
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "llm" / "prompts"
SYSTEM_PROMPT_PATH = PROMPTS_DIR / "system_prompt.txt"

from dotenv import load_dotenv

ENV_PATH = BASE_DIR / ".env"
ENV_EXAMPLE_PATH = BASE_DIR / ".env.example"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv(ENV_EXAMPLE_PATH)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")


def get_system_prompt() -> str:
    """Read the system prompt from prompts/system_prompt.txt."""
    if SYSTEM_PROMPT_PATH.exists():
        return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    return (
        "You are an AI assistant generating simulated phishing scenarios for security training. "
        "Output ONLY valid JSON with keys: tactic, sender_name, sender_email, subject, body, indicators."
    )


# ---------- Fallback Template Library ----------

FALLBACK_TEMPLATES: Dict[str, List[dict]] = {
    "urgency": [
        {
            "tactic": "urgency",
            "sender_name": "IT Enterprise Support Desk",
            "sender_email": "security-alert@internal-gateway.example.com",
            "subject": "[URGENT] Immediate Password Expiration in 15 Minutes",
            "body": "Your enterprise account password will expire within the next 15 minutes. To avoid being locked out of corporate systems and active VPN sessions, you must immediately confirm your access credentials at the secure self-service portal: https://sso-verify.internal-gateway.example.com.",
            "indicators": ["short 15-minute deadline", "threat of workstation lockout", "unverified domain link"],
        },
        {
            "tactic": "urgency",
            "sender_name": "DevOps Infrastructure Monitoring",
            "sender_email": "ci-alerts@internal-deploy.example.com",
            "subject": "[CRITICAL] Deployment Token Rotation Required Within 30 Minutes",
            "body": "A critical authentication token revocation has occurred across all build and deployment runners. You must re-authenticate your developer keys within 30 minutes to prevent scheduled CI/CD pipeline termination.",
            "indicators": ["artificial 30-minute deadline", "threat of deployment stoppage", "unverified OAuth link"],
        },
        {
            "tactic": "urgency",
            "sender_name": "HR Benefits Administration",
            "sender_email": "benefits-portal@hr-connect.example.com",
            "subject": "ACTION REQUIRED: Annual Benefits Enrollment Closes at 5:00 PM Today",
            "body": "Our records indicate your annual healthcare and retirement elections are currently incomplete. Failure to confirm your selections by 5:00 PM today will result in automatic cancellation of optional coverage for the upcoming plan year.",
            "indicators": ["strict same-day deadline", "threat of losing healthcare benefits", "external portal redirect"],
        },
    ],
    "authority": [
        {
            "tactic": "authority",
            "sender_name": "Executive Office",
            "sender_email": "ceo-direct@executive-board.example.com",
            "subject": "Confidential Request from Executive Leadership",
            "body": "Please review the attached confidential organizational restructuring brief before our upcoming board meeting. Due to strict SEC disclosure restrictions, keep this strictly between us and do not discuss it with colleagues until the formal announcement.",
            "indicators": ["executive leadership impersonation", "demand for strict confidentiality", "unusual direct request bypassing managers"],
        },
        {
            "tactic": "authority",
            "sender_name": "VP of Engineering & Architecture",
            "sender_email": "vp-eng@executive-staff.example.com",
            "subject": "Immediate Compliance Audit: Production Cloud Access",
            "body": "Our quarterly external compliance audit is underway today. I need you to immediately verify your production IAM role mappings and submit your active session tokens to the compliance repository linked below.",
            "indicators": ["senior executive authority pressure", "demand to bypass normal audit ticket queue", "request for active session tokens"],
        },
        {
            "tactic": "authority",
            "sender_name": "Chief Legal Counsel",
            "sender_email": "legal-counsel@corporate-legal.example.com",
            "subject": "Urgent Legal Hold Notice: Immediate Document Preservation",
            "body": "You have been designated as a key custodian in pending commercial arbitration. Please immediately log into the legal hold archive portal below and acknowledge receipt of the litigation hold directive.",
            "indicators": ["legal intimidation tactic", "urgent compliance demand", "unfamiliar external portal"],
        },
    ],
    "invoice": [
        {
            "tactic": "invoice",
            "sender_name": "Dana Whitfield (Northwind Logistics)",
            "sender_email": "billing@northwind-vendors.example.com",
            "subject": "Overdue invoice INV-20871 – service suspension Friday",
            "body": "We have not yet received settlement for overdue invoice INV-20871 (amount: $14,850.00). Please remit payment to our updated wire instructions listed on the attached notice by end of day Friday to avoid supply-chain service interruption.",
            "indicators": ["lookalike vendor domain", "financial urgency deadline", "unverified bank account redirection"],
        },
        {
            "tactic": "invoice",
            "sender_name": "Vantage Cloud Services Billing",
            "sender_email": "accounts-receivable@vantage-cloud.example.com",
            "subject": "Final Notice: Enterprise Cloud Hosting Invoice #88412 Overdue",
            "body": "Your enterprise cloud hosting invoice #88412 is past due. To prevent automated de-provisioning of your team's compute clusters and storage buckets, settle the invoice immediately via the payment portal.",
            "indicators": ["lookalike cloud provider domain", "threat of infrastructure de-provisioning", "unsolicited payment link"],
        },
        {
            "tactic": "invoice",
            "sender_name": "Global Office Supplies Corp",
            "sender_email": "billing@office-supplies-vendor.example.com",
            "subject": "Updated Payment Account Instructions for Pending Order PO-9014",
            "body": "Please note that due to our recent financial institution merger, our wire details have changed. Please update your Accounts Payable records and route payment for PO-9014 to the attached ACH account.",
            "indicators": ["fraudulent bank account update", "unverified ACH details", "external vendor invoice notice"],
        },
    ],
    "credential": [
        {
            "tactic": "credential",
            "sender_name": "Single Sign-On Security",
            "sender_email": "auth-verify@sso-portal.example.com",
            "subject": "Security Notice: Confirm Your Identity and Active Session",
            "body": "An anomalous login attempt was registered from an unrecognized IP address. Please enter your enterprise credentials into the identity validation portal immediately to maintain account access and verify your identity.",
            "indicators": ["unsolicited login prompt", "lookalike login URL", "credential harvesting link"],
        },
        {
            "tactic": "credential",
            "sender_name": "Microsoft 365 Cloud Admin",
            "sender_email": "notifications@m365-tenant-admin.example.com",
            "subject": "Action Required: 3 New Encrypted Messages in Quarantine",
            "body": "You have 3 incoming encrypted emails held in the secure gateway quarantine. To decrypt and release these communications, log in with your corporate email password at the secure viewer portal.",
            "indicators": ["fake email quarantine alert", "credential prompt to view messages", "lookalike M365 domain"],
        },
        {
            "tactic": "credential",
            "sender_name": "Internal VPN & Gateway Team",
            "sender_email": "gateway-support@remote-access.example.com",
            "subject": "Required Update: Two-Factor Authenticator Re-Enrollment",
            "body": "Our enterprise remote access gateway has migrated to an updated MFA protocol. You must re-authenticate your mobile token and submit your primary directory credentials to sync your multi-factor profile.",
            "indicators": ["MFA re-enrollment lure", "request for primary directory password", "external portal redirect"],
        },
    ],
}


def get_fallback_scenario(tactic: str, role: str = "", department: str = "") -> dict:
    """Select a realistic template from the fallback library."""
    templates = FALLBACK_TEMPLATES.get(tactic, FALLBACK_TEMPLATES["urgency"])
    chosen = random.choice(templates)
    return {
        "tactic": tactic,
        "sender_name": chosen["sender_name"],
        "sender_email": chosen["sender_email"],
        "subject": chosen["subject"],
        "body": chosen["body"],
        "indicators": list(chosen["indicators"]),
    }


def validate_scenario_schema(data: dict, expected_tactic: str) -> bool:
    """Verify that the generated JSON matches the required schema."""
    required_keys = ("tactic", "sender_name", "sender_email", "subject", "body", "indicators")
    if not all(k in data for k in required_keys):
        return False
    if not isinstance(data["indicators"], list) or len(data["indicators"]) == 0:
        return False
    if not isinstance(data["subject"], str) or not isinstance(data["body"], str):
        return False
    return True


def generate_scenario_with_groq(
    tactic: str,
    role: str = "Employee",
    department: str = "General",
    employee_name: str = "",
) -> Optional[dict]:
    """Call Groq API to generate a structured JSON scenario."""
    if not GROQ_API_KEY:
        return None

    try:
        from groq import Groq

        client = Groq(api_key=GROQ_API_KEY)
        system_prompt = get_system_prompt()
        user_prompt = (
            f"Generate one realistic simulated phishing scenario.\n"
            f"Target: {employee_name or 'Employee'} (Role: {role}, Department: {department})\n"
            f"Tactic: {tactic}\n"
            f"Return ONLY valid JSON matching the schema."
        )

        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
        )

        raw_json = response.choices[0].message.content.strip()
        if raw_json.startswith("```"):
            raw_json = raw_json.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        if not raw_json.startswith("{"):
            start, end = raw_json.find("{"), raw_json.rfind("}")
            raw_json = raw_json[start:end + 1] if start >= 0 and end > start else raw_json
        data = json.loads(raw_json)

        if validate_scenario_schema(data, tactic):
            data["tactic"] = tactic  # Ensure tactic consistency
            return data
    except Exception as exc:
        print(f"[LLM Warning] Groq scenario generation failed ({exc}); using fallback template.")

    return None


def generate_scenario(
    tactic: str,
    role: str = "Employee",
    department: str = "General",
    employee_name: str = "",
) -> dict:
    """Generate a phishing scenario (Groq API first, template fallback if unavailable)."""
    # 1. Try Groq generation if API key is present
    if GROQ_API_KEY:
        llm_scenario = generate_scenario_with_groq(tactic, role, department, employee_name)
        if llm_scenario:
            llm_scenario["source"] = "groq"
            return llm_scenario

    # 2. Fallback template library
    fallback = get_fallback_scenario(tactic, role, department)
    fallback["source"] = "fallback"
    return fallback


def generate_report_analysis(rounds: list[dict], employee_name: str = "Employee") -> str:
    """Generate a data-grounded report narrative with a safe fallback."""
    weakest = min(rounds, key=lambda item: item.get("safety_score", 0)).get("tactic") if rounds else "the assessed tactics"
    scores = ", ".join(f"R{item.get('round_number')}: {item.get('safety_score', 0):.0%}" for item in rounds[-8:])
    if GROQ_API_KEY and rounds:
        try:
            from groq import Groq
            response = Groq(api_key=GROQ_API_KEY).chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "Write a concise, supportive cybersecurity training analysis. Use only the supplied data. Do not give attack instructions. Return 2 short paragraphs."},
                    {"role": "user", "content": f"Employee: {employee_name}\nRound data: {json.dumps(rounds)}"},
                ], temperature=0.2,
            )
            text = response.choices[0].message.content.strip()
            if text:
                return text
        except Exception as exc:
            print(f"[LLM Warning] Report analysis failed ({exc}); using fallback.")
    return (f"{employee_name}'s lowest observed safety result was in {weakest}. "
            f"Round scores were {scores or 'not available'}. Continue verifying unusual requests through a trusted channel and report suspicious messages.")


def build_feedback_prompt(
    tactic: str,
    response: str,
    scenario_indicators: list[str],
    retrieved_docs: list[dict],
) -> str:
    """Build a structured feedback prompt separating reference material from round context."""
    passed = response == "report"
    outcome = "correctly reported this simulation" if passed else f"responded with '{response}'"
    indicators_text = "\n".join(f"- {ind}" for ind in scenario_indicators[:4])

    ref_blocks = []
    for doc in retrieved_docs[:3]:
        title = doc.get("title", "Reference")
        source = doc.get("source", "Security Reference")
        snippet = doc.get("snippet", doc.get("text", ""))[:300]
        ref_blocks.append(f"[{title}] (Source: {source})\n{snippet}")
    reference_section = "\n\n".join(ref_blocks) if ref_blocks else "No reference material available."

    return f"""You are a cybersecurity awareness coach delivering post-exercise feedback.

=== REFERENCE MATERIAL (documented phishing patterns for this tactic) ===
{reference_section}

=== ROUND SUMMARY ===
Tactic tested: {tactic}
Employee action: {outcome}
Scenario warning signs:
{indicators_text}

=== YOUR TASK ===
Write 2–3 short, supportive sentences of feedback grounded in the reference material above.
- If the employee reported: affirm what they spotted, referencing one specific documented indicator.
- If the employee clicked or entered credentials: explain what pattern was used and what to do next time.
Do NOT repeat attack instructions. Do NOT use jargon-heavy language. Be encouraging."""


def generate_feedback(
    tactic: str,
    response: str,
    indicators: list[str],
    retriever=None,
) -> tuple[str, list[dict]]:
    """Generate RAG-grounded post-round feedback.

    Returns:
        (feedback_text, retrieved_indicators)
    """
    # Attempt to retrieve reference documents for this tactic
    retrieved_docs: list[dict] = []
    if retriever is None:
        try:
            from rag.retriever import get_retriever
            retriever = get_retriever()
        except Exception:
            retriever = None

    if retriever:
        try:
            retrieved_docs = retriever.retrieve(tactic, k=3)
        except Exception as exc:
            print(f"[LLM Warning] RAG retrieval failed ({exc}); proceeding without reference context.")

    # Try Groq with RAG-grounded prompt
    if GROQ_API_KEY:
        try:
            from groq import Groq

            prompt = build_feedback_prompt(tactic, response, indicators, retrieved_docs)
            resp = Groq(api_key=GROQ_API_KEY).chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a supportive cybersecurity awareness trainer. "
                            "Your feedback is grounded only in the provided reference material. "
                            "Never provide instructions that could help attackers."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            text = resp.choices[0].message.content.strip()
            if text:
                return text, retrieved_docs
        except Exception as exc:
            print(f"[LLM Warning] Groq feedback generation failed ({exc}); using grounded fallback.")

    # Fallback: synthesise from retrieved indicators without LLM
    passed = response == "report"
    ind_text = ", ".join(indicators[:3]) if indicators else f"{tactic} techniques"

    if retrieved_docs:
        ref = retrieved_docs[0]
        ref_line = f" According to documented patterns ({ref.get('title', 'Security Reference')}): {ref.get('snippet', '')[:160].rstrip()}."
    else:
        ref_line = ""

    if passed:
        feedback = (
            f"Good catch. You correctly reported this simulated {tactic} message. "
            f"The key warning signs were: {ind_text}.{ref_line}"
        )
    else:
        action_note = {
            "click": "clicking embedded links",
            "credentials": "submitting credentials",
            "ignore": "ignoring without reporting",
        }.get(response, "interacting with the message")
        feedback = (
            f"This was a simulated {tactic} phishing exercise. "
            f"The message used {ind_text}.{ref_line} "
            f"Instead of {action_note}, verify the sender through a trusted channel and use the Report button."
        )

    return feedback, retrieved_docs

