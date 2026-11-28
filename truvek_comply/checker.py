# checker.py — Pattern-based message compliance checking
# Classifies messages and checks them against email/SMS laws:
#   Spam Act 2003 (AU), CAN-SPAM (US), CASL (CA), GDPR/ePrivacy (EU)

import os
import re
from .rules import get_rule, RULESET_VERSION, rules_for_jurisdiction
from . import ml_classifier

# --- Pattern lists ---

PROMOTIONAL_PATTERNS = [
    r'\b(sales?|discounts?|off|save|savings|deals?|offers?|promos?|coupons?|specials|bargains?|free shipping|limited time|act now|buy now|shop now|exclusive|black friday|cyber monday|new arrivals?)\b',
    r'\b(% off|\$\d+ off|members only|early access|flash sale)\b',
    # Urgency and scarcity selling ("last chance", "selling fast", "sold out")
    r'\b(last chance|final days|final call|ends (soon|tonight|today)|selling fast|sell(s|ing)? out|sold out|almost gone|don.?t miss|hurry)\b',
    # Lotteries, raffles, competitions and prize draws
    r'\b(chance to win|win (a|an|up to)\b|prize (draw|home)|bonus tickets?|buy (your )?tickets?|get your tickets?|enter (now|the draw))',
]

TRANSACTIONAL_PATTERNS = [
    # "account" only counts when it describes something that happened to the
    # account. A bare "My Account" nav link sits in almost every marketing email.
    r'\b(order|receipt|invoice|confirmation|shipping|delivery|tracking|password reset|your (booking|reservation|appointment))\b',
    r'\b(account (created|verified|activated|suspended|locked|closed|statement|balance)|your account (has|was|is|will))\b',
    # Legal, administrative and notice-type emails
    r'\b(notice to|legal notice|class action|group member|settlement|claimant|proceeding|tribunal|court order|opt.?out deadline)\b',
    r'\b(you (are|were) (registered|included|identified)|you have been (added|identified|included))\b',
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

# Strong newsletter/editorial signals — content-defining; mean the email is a
# newsletter or editorial product, not an administrative or transactional message.
NEWSLETTER_CONTENT_PATTERNS = [
    r'\b(newsletter|briefing|morning briefing|morning update|news update|daily update|weekly update)\b',
    r'\b(top stories|breaking news|latest news|live updates|round.?up)\b',
    r'\b(edition|digest)\b',
    r'\b(this issue|latest issue|current issue)\b',
    r'\bsportsmail\b',
    r'\b(live free agency|live trade|live scores|live blog)\b',
    r'\bBREAKING\b',
]

# Weak boilerplate patterns — appear in newsletters AND transactional/admin emails.
# Used to detect newsletter-style formatting but not strong enough alone to override
# a clear transactional classification.
NEWSLETTER_BOILERPLATE_PATTERNS = [
    r'\b(view online|view in browser|view this email|having trouble reading|read online)\b',
    r'\b(subscribe|subscription)\b',
    r'\bpowered by\b',
    r'\b(this week|this month)\b',
]

# Combined — used where any newsletter signal is enough (e.g. marketing classification
# when there are no transactional signals at all).
NEWSLETTER_PATTERNS = NEWSLETTER_CONTENT_PATTERNS + NEWSLETTER_BOILERPLATE_PATTERNS

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

    promotional     = _matches_any(combined, PROMOTIONAL_PATTERNS)
    transactional   = _matches_any(combined, TRANSACTIONAL_PATTERNS)
    newsletter      = _matches_any(combined, NEWSLETTER_PATTERNS)
    # Strong = content-defining newsletter signals (briefing, edition, top stories…)
    # Weak   = boilerplate that appears in many email types (view online, subscribe…)
    strong_newsletter = _matches_any(combined, NEWSLETTER_CONTENT_PATTERNS)

    if promotional:
        reasons.append("Promotional language detected (e.g. sale, discount, offer).")
    if transactional:
        reasons.append("Transactional language detected (e.g. order, confirmation, invoice).")
    if newsletter and not transactional:
        reasons.append("Editorial newsletter signals detected (e.g. briefing, view online, subscribe).")

    if transactional and not strong_newsletter:
        # Transactional classification wins when there are no strong content-defining
        # newsletter signals. Boilerplate like "view online" or "subscription preferences"
        # in a footer is not enough to reclassify a legal notice or order confirmation.
        if promotional:
            msg_type = "transactional_with_promotion"
            reasons.append("Both transactional and promotional content found, so it is treated as commercial.")
        else:
            msg_type = "transactional"
    elif strong_newsletter or promotional:
        # Strong newsletter signals (briefing, edition, top stories, etc.) or purely
        # promotional content → marketing, even if transactional words appear in a footer.
        msg_type = "marketing"
    elif newsletter:
        # Only weak boilerplate newsletter signals, no transactional content.
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

    # Use ML model if trained and confident, otherwise fall back to patterns.
    # Below 75% the model is unreliable on out-of-distribution emails (legal
    # notices, admin messages, etc.) and pattern-based is more accurate.
    ML_CONFIDENCE_FLOOR = 0.85
    # Off unless COMPLY_ML=1. On 100 real promos from a Gmail inbox the model
    # called 13 "transactional" at 85%+ confidence (patterns: 2), which would
    # skip consent and unsubscribe checks. Keep it off until retrained on
    # real marketing email.
    ml_result = ml_classifier.classify(subject, body) if os.environ.get("COMPLY_ML") == "1" else None
    if ml_result and ml_result["confidence"] >= ML_CONFIDENCE_FLOOR:
        classification = {
            "type": ml_result["type"],
            "reasons": [f"ML classifier (confidence {ml_result['confidence']:.0%})."],
            "source": "ml",
        }
    else:
        classification = classify_message(subject, body, channel)
        if ml_result:
            classification["reasons"].append(
                f"ML classifier confidence too low ({ml_result['confidence']:.0%}), so pattern matching was used."
            )

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
            # Standard finding fields shared by every Truvek tool: rule, title, scope, line, fix.
            "rule": rule_id,
            "title": rule["title"],
            "scope": ", ".join(j.upper() for j in applies_to),
            "line": None,
            "why": rule["description"],
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
                f"Consent is {consent}. Opt-in consent is required for {', '.join(j.upper() for j in opt_in_jurisdictions)}.",
            )
        elif opt_in_jurisdictions and consent == "inferred":
            add_finding(
                "consent_inferred_risk",
                "Consent is inferred. ACMA and CASL warn against relying on implied consent.",
            )

        # US CAN-SPAM: opt-out model — flag as review if unknown (may have opted out)
        if "us" in active and consent in ("none", "unknown"):
            add_finding(
                "consent_missing_us",
                f"Consent is {consent}. Confirm the recipient has not opted out before (CAN-SPAM).",
            )

        # --- Sender identification ---
        if not sender_identified:
            add_finding(
                "sender_missing",
                "The message does not clearly name the sender. Sender name and contact details are required.",
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
                    "Login wording appears near the unsubscribe text, so the opt-out may not work without signing in.",
                )

        # --- Transactional with promotion ---
        if msg_type == "transactional_with_promotion":
            add_finding(
                "transactional_with_promotion",
                "This transactional message includes promotional content, so commercial rules apply.",
            )

    else:
        # Pure transactional: sender ID still required everywhere
        if not sender_identified:
            add_finding(
                "sender_missing",
                "The message does not clearly name the sender. Sender details are required even in transactional messages.",
            )

    # --- SMS-specific rules ---
    if channel == "sms":
        if "au" in active:
            add_finding(
                "sms_sender_id_unregistered",
                "Alphanumeric SMS sender IDs must be registered with ACMA from 1 July 2026.",
            )
        if "us" in active and is_commercial:
            add_finding(
                "tcpa_sms_consent",
                "The TCPA requires prior express written consent for marketing SMS to US numbers.",
            )
        if "eu" in active and is_commercial:
            add_finding(
                "eu_sms_consent",
                "The ePrivacy Directive requires opt-in consent for marketing SMS to EU numbers.",
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
