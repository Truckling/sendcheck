# checker.py — Pattern-based message compliance checking
# Classifies messages and checks them against email/SMS laws:
#   Spam Act 2003 (AU), CAN-SPAM (US), CASL (CA), GDPR/ePrivacy (EU)

import re
from .rules import get_rule, RULESET_VERSION, rules_for_jurisdiction
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
    # No word boundaries on unsubscribe — ESP footers often concatenate links
    # into a single string like "PreferencesUnsubscribePrivacy"
    r'unsubscribe',
    r'\b(opt.out|manage (preferences|subscriptions)|stop receiving)\b',
    r'https?://\S*(unsub|optout|opt.out)\S*',
]

LOGIN_WALL_PATTERNS = [
    r'(log in|sign in|login|signin).{0,80}(unsubscribe|opt.out)',
    r'(unsubscribe|opt.out).{0,80}(log in|sign in|login|signin)',
]

# Newsletter/editorial signals — strong indicators an email is commercial
# even when it contains no obvious promotional language.
NEWSLETTER_PATTERNS = [
    r'\b(newsletter|briefing|morning briefing|morning update|news update|daily update|weekly update)\b',
    r'\b(top stories|breaking news|latest news|live updates|round.?up|this week|this month)\b',
    r'\b(view online|view in browser|view this email|having trouble reading|read online)\b',
    r'\b(subscribe|subscription|edition|issue|digest)\b',
    r'\bpowered by\b',
    r'\bsportsmail\b',
    r'\b(live free agency|live trade|live scores|live blog)\b',
    r'\bBREAKING\b',
]

# Physical address patterns — required by CAN-SPAM and CASL in email footers
PHYSICAL_ADDRESS_PATTERNS = [
    # Street address: number + street name + type
    r'\b\d+\s+\w[\w\s]{1,30}(street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|place|pl|court|ct|suite|ste)\b',
    # PO Box
    r'\bp\.?\s*o\.?\s*box\s+\d+\b',
    # US ZIP code in context (5 digits, optionally +4)
    r'\b[A-Z]{2}\s+\d{5}(-\d{4})?\b',
    # Canadian postal code
    r'\b[A-Z]\d[A-Z]\s*\d[A-Z]\d\b',
    # Australian postcode in context (4 digits after state abbreviation or city)
    r'\b(NSW|VIC|QLD|WA|SA|TAS|ACT|NT)\s+\d{4}\b',
    # UK postcode
    r'\b[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}\b',
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
    newsletter = _matches_any(combined, NEWSLETTER_PATTERNS)

    if promotional:
        reasons.append("Promotional language detected (e.g. sale, discount, offer).")
    if transactional:
        reasons.append("Transactional language detected (e.g. order, confirmation, invoice).")
    if newsletter and not transactional:
        reasons.append("Editorial newsletter signals detected (e.g. briefing, view online, subscribe).")

    if transactional and promotional:
        msg_type = "transactional_with_promotion"
        reasons.append("Both transactional and promotional content found — treated as commercial.")
    elif transactional:
        msg_type = "transactional"
    elif promotional or newsletter:
        msg_type = "marketing"
    else:
        msg_type = "unclear"
        reasons.append("No clear promotional, transactional, or newsletter signals found.")

    return {"type": msg_type, "reasons": reasons}


def check_message(
    subject: str,
    body: str,
    channel: str = "email",
    consent: str = "unknown",
    sender_identified: bool = False,
    jurisdiction: str = "all",
) -> dict:
    """
    Run compliance checks on a message against one or more jurisdictions.

    Parameters:
      subject           — the message subject line
      body              — the full message body text
      channel           — "email" or "sms"
      consent           — "express", "inferred", "none", or "unknown"
      sender_identified — True if the message clearly names the sender
      jurisdiction      — "au", "us", "ca", "eu", or "all" (default: "all")

    Returns a dict with:
      - verdict: "pass", "review", or "block"
      - findings: list of rule violations, each tagged with jurisdiction
      - classification: output of classify_message()
      - ruleset_version: version string
    """
    findings = []

    # Use ML model if trained, otherwise fall back to patterns
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

    # Commercial under any law = marketing, transactional_with_promotion, or unclear
    is_commercial = msg_type in ("marketing", "transactional_with_promotion", "unclear")

    # Which jurisdictions to check
    if jurisdiction == "all":
        active = ["au", "us", "ca", "eu"]
    else:
        active = [jurisdiction]

    def add_finding(rule_id: str, trigger: str):
        rule = get_rule(rule_id)
        if rule is None:
            return
        # Only add if this rule applies to at least one active jurisdiction
        rule_jurisdictions = rule.get("jurisdiction", [])
        applies_to = [j for j in rule_jurisdictions if j in active]
        if not applies_to:
            return
        findings.append({
            "rule_id": rule_id,
            "severity": rule["severity"],
            "section": rule["section"],
            "act": rule["act"],
            "jurisdiction": applies_to,
            "trigger": trigger,
            "fix": rule["fix"],
        })

    if is_commercial:
        # --- Consent ---

        # AU, CA, EU: opt-in required — none/unknown is a block
        opt_in_jurisdictions = [j for j in active if j in ("au", "ca", "eu")]
        if opt_in_jurisdictions and consent in ("none", "unknown"):
            add_finding(
                "consent_missing",
                f"consent='{consent}' — opt-in consent required for {', '.join(j.upper() for j in opt_in_jurisdictions)}.",
            )
        elif opt_in_jurisdictions and consent == "inferred":
            add_finding(
                "consent_inferred_risk",
                "consent='inferred' — ACMA and CASL warn against over-reliance on implied consent.",
            )

        # US CAN-SPAM: opt-out model — flag as review if unknown (may have opted out)
        if "us" in active and consent in ("none", "unknown"):
            add_finding(
                "consent_missing_us",
                f"consent='{consent}' — confirm recipient has not previously opted out (CAN-SPAM).",
            )

        # --- Sender identification ---
        if not sender_identified:
            add_finding(
                "sender_missing",
                "sender_identified=False — sender name and contact details required.",
            )

        # --- Physical address (US/CA) ---
        if any(j in active for j in ("us", "ca")):
            has_address = _matches_any(body, PHYSICAL_ADDRESS_PATTERNS)
            if not has_address:
                add_finding(
                    "physical_address_missing",
                    "No physical mailing address detected in message body.",
                )

        # --- Unsubscribe ---
        has_unsubscribe = _matches_any(body, UNSUBSCRIBE_PATTERNS)
        if not has_unsubscribe:
            add_finding(
                "unsubscribe_missing",
                "No unsubscribe mechanism found in message body.",
            )
        else:
            if _matches_any(body, LOGIN_WALL_PATTERNS):
                add_finding(
                    "unsubscribe_login_required",
                    "Login language found near unsubscribe text — may not be functional.",
                )

        # --- Transactional with promotion ---
        if msg_type == "transactional_with_promotion":
            add_finding(
                "transactional_with_promotion",
                "Message classified as transactional_with_promotion — commercial rules apply.",
            )

    else:
        # Pure transactional: sender ID still required everywhere
        if not sender_identified:
            add_finding(
                "sender_missing",
                "sender_identified=False — sender details required even for transactional messages.",
            )

    # --- SMS-specific rules ---
    if channel == "sms":
        if "au" in active:
            add_finding(
                "sms_sender_id_unregistered",
                "Channel is 'sms' — alphanumeric sender ID registration required from 1 Jul 2026 (AU).",
            )
        if "us" in active and is_commercial:
            add_finding(
                "tcpa_sms_consent",
                "Channel is 'sms' — TCPA requires written prior express consent for marketing SMS to US numbers.",
            )
        if "eu" in active and is_commercial:
            add_finding(
                "eu_sms_consent",
                "Channel is 'sms' — ePrivacy Directive requires opt-in consent for marketing SMS to EU numbers.",
            )

    # Verdict from most severe finding
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
        "jurisdiction_checked": active,
        "ruleset_version": RULESET_VERSION,
    }
