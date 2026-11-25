# checker.py — Pattern-based message compliance checking
# Classifies messages and checks them against Spam Act 2003 rules.

import re
from .rules import get_rule, RULESET_VERSION
from . import ml_classifier

# --- Pattern lists ---

PROMOTIONAL_PATTERNS = [
    r'\b(sale|discount|off|save|deal|offer|promo|coupon|free shipping|limited time|act now|buy now|shop now|exclusive)\b',
    r'\b(% off|\$\d+ off|members only|early access|flash sale)\b',
]

TRANSACTIONAL_PATTERNS = [
    r'\b(order|receipt|invoice|confirmation|shipping|delivery|tracking|password reset|account|your (booking|reservation|appointment))\b',
]

UNSUBSCRIBE_PATTERNS = [
    r'\b(unsubscribe|opt.out|manage (preferences|subscriptions)|stop receiving)\b',
    r'https?://\S*(unsub|optout|opt.out)\S*',
]

LOGIN_WALL_PATTERNS = [
    r'(log in|sign in|login|signin).{0,80}(unsubscribe|opt.out)',
    r'(unsubscribe|opt.out).{0,80}(log in|sign in|login|signin)',
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    """Return True if any pattern matches the text (case-insensitive)."""
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def classify_message(subject: str, body: str, channel: str = "email") -> dict:
    """
    Classify a message as marketing, transactional, transactional_with_promotion, or unclear.

    Returns a dict with keys:
      - type: one of the four classifications above
      - reasons: list of plain-English strings explaining the classification
    """
    combined = f"{subject}\n{body}".lower()
    reasons = []

    promotional = _matches_any(combined, PROMOTIONAL_PATTERNS)
    transactional = _matches_any(combined, TRANSACTIONAL_PATTERNS)

    if promotional:
        reasons.append("Promotional language detected (e.g. sale, discount, offer).")
    if transactional:
        reasons.append("Transactional language detected (e.g. order, confirmation, invoice).")

    if transactional and promotional:
        msg_type = "transactional_with_promotion"
        reasons.append("Both transactional and promotional content found — treated as commercial.")
    elif transactional:
        msg_type = "transactional"
    elif promotional:
        msg_type = "marketing"
    else:
        msg_type = "unclear"
        reasons.append("No clear promotional or transactional signals found.")

    return {"type": msg_type, "reasons": reasons}


def check_message(
    subject: str,
    body: str,
    channel: str = "email",
    consent: str = "unknown",
    sender_identified: bool = False,
) -> dict:
    """
    Run Spam Act 2003 compliance checks on a message.

    Parameters:
      subject           — the message subject line
      body              — the full message body text
      channel           — "email" or "sms"
      consent           — "express", "inferred", "none", or "unknown"
      sender_identified — True if the message clearly names the sender

    Returns a dict with:
      - verdict: "pass", "review", or "block"
      - findings: list of rule violations found
      - classification: output of classify_message()
      - ruleset_version: version string for the rule set used
    """
    findings = []

    # Use the ML model if one has been trained, otherwise fall back to patterns
    ml_result = ml_classifier.classify(subject, body)
    if ml_result:
        classification = {
            "type": ml_result["type"],
            "reasons": [f"ML classifier (confidence {ml_result['confidence']:.0%})."],
            "source": "ml",
        }
    else:
        classification = classify_message(subject, body, channel)

    msg_type = classification["type"]

    # A message is "commercial" under the Spam Act if it's marketing,
    # a transactional message with promotional content, or we can't tell.
    is_commercial = msg_type in ("marketing", "transactional_with_promotion", "unclear")

    def add_finding(rule_id: str, trigger: str):
        rule = get_rule(rule_id)
        findings.append({
            "rule_id": rule_id,
            "severity": rule["severity"],
            "section": rule["section"],
            "act": rule["act"],
            "trigger": trigger,
            "fix": rule["fix"],
        })

    if is_commercial:
        # s16 — consent
        if consent in ("none", "unknown"):
            add_finding(
                "consent_missing",
                f"consent='{consent}' passed by caller — no valid consent on record.",
            )
        elif consent == "inferred":
            add_finding(
                "consent_inferred_risk",
                "consent='inferred' passed by caller — ACMA guidance warns against over-reliance.",
            )

        # s17 — sender identification
        if not sender_identified:
            add_finding(
                "sender_missing",
                "sender_identified=False passed by caller — no sender details confirmed.",
            )

        # s18 — unsubscribe mechanism
        has_unsubscribe = _matches_any(body, UNSUBSCRIBE_PATTERNS)
        if not has_unsubscribe:
            add_finding(
                "unsubscribe_missing",
                "No unsubscribe pattern found in message body.",
            )
        else:
            # Check if unsubscribe requires login (login wall anti-pattern)
            if _matches_any(body, LOGIN_WALL_PATTERNS):
                add_finding(
                    "unsubscribe_login_required",
                    "Login language found near unsubscribe text in message body.",
                )

        # s6 — transactional message with promotional content
        if msg_type == "transactional_with_promotion":
            add_finding(
                "transactional_with_promotion",
                "Message classified as transactional_with_promotion — commercial rules apply.",
            )

    else:
        # Pure transactional messages still need sender identification (s17)
        if not sender_identified:
            add_finding(
                "sender_missing",
                "sender_identified=False — sender details required even for transactional messages.",
            )

    # SMS sender ID check applies to all SMS messages regardless of commercial status
    if channel == "sms":
        add_finding(
            "sms_sender_id_unregistered",
            "Channel is 'sms' — alphanumeric sender ID registration required from 1 Jul 2026.",
        )

    # Determine overall verdict from the most severe finding
    severities = {f["severity"] for f in findings}
    if "block" in severities:
        verdict = "block"
    elif "review" in severities:
        verdict = "review"
    else:
        verdict = "pass"

    return {
        "verdict": verdict,
        "findings": findings,
        "classification": classification,
        "ruleset_version": RULESET_VERSION,
    }
