# rules.py — Spam Act 2003 compliance rules
# Each rule maps to a specific legal obligation or regulatory guidance.
# severity:
#   "block"  — message must not be sent until this is fixed
#   "review" — human should review before sending
#   "info"   — informational; action may be needed depending on context

RULESET_VERSION = "0.1.0"

RULES = [
    {
        "id": "consent_missing",
        "section": "s16",
        "act": "Spam Act 2003",
        "description": (
            "Commercial messages must only be sent to people who have consented "
            "(expressly or by inference)."
        ),
        "fix": (
            "Get express consent before sending, or confirm that inferred consent "
            "applies and document it."
        ),
        "severity": "block",
    },
    {
        "id": "consent_inferred_risk",
        "section": "s16",
        "act": "Spam Act 2003 / ACMA 2026 guidance",
        "description": (
            "Inferred consent is risky. ACMA's 2026 spotlight highlighted that many "
            "senders over-rely on it."
        ),
        "fix": "Replace inferred consent with an express opt-in wherever possible.",
        "severity": "review",
    },
    {
        "id": "sender_missing",
        "section": "s17",
        "act": "Spam Act 2003",
        "description": (
            "Every commercial message must clearly identify the sender and include "
            "accurate contact details."
        ),
        "fix": (
            "Add the sender's name and a working Australian contact address or "
            "phone number."
        ),
        "severity": "block",
    },
    {
        "id": "unsubscribe_missing",
        "section": "s18",
        "act": "Spam Act 2003",
        "description": (
            "Every commercial message must include a functional unsubscribe mechanism."
        ),
        "fix": (
            "Add a working unsubscribe link or reply-to address. It must work for "
            "at least 30 days after sending."
        ),
        "severity": "block",
    },
    {
        "id": "unsubscribe_login_required",
        "section": "s18",
        "act": "Spam Act 2003 / ACMA guidance",
        "description": (
            "Requiring login to unsubscribe is not considered functional under "
            "ACMA guidance."
        ),
        "fix": "Allow one-click unsubscribe without requiring the recipient to log in.",
        "severity": "review",
    },
    {
        "id": "transactional_with_promotion",
        "section": "s6",
        "act": "Spam Act 2003 / ACMA v Lululemon (Mar 2026)",
        "description": (
            "A transactional message that contains promotional content is treated as "
            "commercial. The consent and unsubscribe rules then apply."
        ),
        "fix": (
            "Remove the promotional content, or treat the message as commercial and "
            "apply all Spam Act obligations."
        ),
        "severity": "review",
    },
    {
        "id": "sms_sender_id_unregistered",
        "section": "SMS Sender ID Register (1 Jul 2026)",
        "act": "ACMA",
        "description": (
            "Alphanumeric SMS sender IDs must be registered on the ACMA SMS Sender "
            "ID Register from 1 July 2026."
        ),
        "fix": "Register your sender ID at the ACMA portal before sending.",
        "severity": "info",
    },
]


def get_rule(rule_id: str) -> dict | None:
    """Return the rule dict for a given rule_id, or None if not found."""
    for rule in RULES:
        if rule["id"] == rule_id:
            return rule
    return None
