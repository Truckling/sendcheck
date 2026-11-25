# rules.py — Email and SMS compliance rules
# Covers: Spam Act 2003 (AU), CAN-SPAM (US), CASL (CA), GDPR/ePrivacy (EU)
#
# severity:
#   "block"  — message must not be sent until this is fixed
#   "review" — human should review before sending
#   "info"   — informational; action may be needed depending on context
#
# jurisdiction:
#   List of codes this rule applies to: "au", "us", "ca", "eu"
#   Rules with all four apply globally.

RULESET_VERSION = "0.2.0"

RULES = [
    # --- Consent ---

    {
        "id": "consent_missing",
        "section": "s16 / s6(1) / Art.6(1)(a)",
        "act": "Spam Act 2003 (AU) / CASL (CA) / GDPR (EU)",
        "jurisdiction": ["au", "ca", "eu"],
        "description": (
            "AU, CA, and EU law require prior consent before sending commercial messages. "
            "Express opt-in is safest. Implied/inferred consent is allowed in limited "
            "circumstances but lapses if not renewed."
        ),
        "fix": (
            "Obtain express consent before sending. Document when and how consent was given."
        ),
        "severity": "block",
    },
    {
        "id": "consent_missing_us",
        "section": "15 U.S.C. § 7704",
        "act": "CAN-SPAM Act (US)",
        "jurisdiction": ["us"],
        "description": (
            "CAN-SPAM uses an opt-out model — prior consent is not required, but you must "
            "honour opt-out requests promptly. Sending to someone who has opted out is a "
            "violation."
        ),
        "fix": (
            "Confirm the recipient has not previously opted out. Include a clear opt-out "
            "mechanism and honour requests within 10 business days."
        ),
        "severity": "review",
    },
    {
        "id": "consent_inferred_risk",
        "section": "s16 / s10(9)",
        "act": "Spam Act 2003 (AU) / CASL (CA)",
        "jurisdiction": ["au", "ca"],
        "description": (
            "Inferred/implied consent is risky. ACMA's 2026 spotlight highlighted over-reliance "
            "on it. Under CASL, implied consent from a business relationship expires after 2 years."
        ),
        "fix": "Replace inferred consent with an express opt-in wherever possible.",
        "severity": "review",
    },

    # --- Sender identification ---

    {
        "id": "sender_missing",
        "section": "s17 / s6(2)(b) / s5(a)(1)",
        "act": "Spam Act 2003 (AU) / CASL (CA) / CAN-SPAM (US) / GDPR (EU)",
        "jurisdiction": ["au", "us", "ca", "eu"],
        "description": (
            "Every commercial message must clearly identify the sender. All four major laws "
            "require this. CASL and GDPR also require a mailing address."
        ),
        "fix": (
            "Include the sender's name, a working contact address, and — for US emails — "
            "a valid physical postal address."
        ),
        "severity": "block",
    },

    # --- Physical address (CAN-SPAM / CASL) ---

    {
        "id": "physical_address_missing",
        "section": "s5(a)(5) / s6(2)(c)",
        "act": "CAN-SPAM Act (US) / CASL (CA)",
        "jurisdiction": ["us", "ca"],
        "description": (
            "CAN-SPAM requires a valid physical postal address in every commercial email. "
            "CASL requires a mailing address. This is typically placed in the email footer."
        ),
        "fix": (
            "Add your company's physical mailing address to the email footer — "
            "street address, PO Box, or registered office."
        ),
        "severity": "block",
    },

    # --- Unsubscribe ---

    {
        "id": "unsubscribe_missing",
        "section": "s18 / s6(2)(c) / s5(a)(3)",
        "act": "Spam Act 2003 (AU) / CASL (CA) / CAN-SPAM (US) / ePrivacy (EU)",
        "jurisdiction": ["au", "us", "ca", "eu"],
        "description": (
            "Every commercial message must include a functional unsubscribe or opt-out mechanism. "
            "Required under all four major laws."
        ),
        "fix": (
            "Add a working unsubscribe link or reply-to address. "
            "AU/CA: must work for at least 30 days. US: honour within 10 business days."
        ),
        "severity": "block",
    },
    {
        "id": "unsubscribe_login_required",
        "section": "s18",
        "act": "Spam Act 2003 (AU) / ACMA guidance",
        "jurisdiction": ["au", "ca", "eu"],
        "description": (
            "Requiring login to unsubscribe is not considered a functional opt-out under "
            "ACMA guidance and is inconsistent with CASL and GDPR expectations."
        ),
        "fix": "Allow one-click unsubscribe without requiring the recipient to log in.",
        "severity": "review",
    },

    # --- Content classification ---

    {
        "id": "transactional_with_promotion",
        "section": "s6 / ACMA v Lululemon (Mar 2026)",
        "act": "Spam Act 2003 (AU) / CAN-SPAM (US) / CASL (CA)",
        "jurisdiction": ["au", "us", "ca"],
        "description": (
            "A transactional message that contains promotional content is treated as commercial. "
            "All consent, sender ID, and unsubscribe obligations then apply. "
            "ACMA fined Lululemon $702K for this in 2026."
        ),
        "fix": (
            "Remove the promotional content, or treat the full message as commercial and "
            "apply all applicable obligations."
        ),
        "severity": "review",
    },

    # --- SMS ---

    {
        "id": "sms_sender_id_unregistered",
        "section": "SMS Sender ID Register (1 Jul 2026)",
        "act": "ACMA (AU)",
        "jurisdiction": ["au"],
        "description": (
            "Alphanumeric SMS sender IDs must be registered on the ACMA SMS Sender "
            "ID Register from 1 July 2026."
        ),
        "fix": "Register your sender ID at the ACMA portal before sending.",
        "severity": "info",
    },
    {
        "id": "tcpa_sms_consent",
        "section": "47 U.S.C. § 227(b)(1)(A)",
        "act": "TCPA (US)",
        "jurisdiction": ["us"],
        "description": (
            "The TCPA requires prior express written consent before sending marketing SMS "
            "to US mobile numbers. Violations carry statutory damages of $500–$1,500 per message."
        ),
        "fix": (
            "Obtain written prior express consent (e.g. web form with clear SMS opt-in checkbox) "
            "before sending any marketing SMS to US numbers."
        ),
        "severity": "block",
    },
    {
        "id": "eu_sms_consent",
        "section": "Art. 13 ePrivacy Directive",
        "act": "ePrivacy Directive (EU)",
        "jurisdiction": ["eu"],
        "description": (
            "EU ePrivacy Directive requires prior opt-in consent before sending marketing SMS "
            "to EU numbers."
        ),
        "fix": "Obtain explicit opt-in consent before sending marketing SMS to EU recipients.",
        "severity": "block",
    },
]


def get_rule(rule_id: str) -> dict | None:
    """Return the rule dict for a given rule_id, or None if not found."""
    for rule in RULES:
        if rule["id"] == rule_id:
            return rule
    return None


def rules_for_jurisdiction(jurisdiction: str) -> list:
    """Return rules applicable to a given jurisdiction code, or all rules if 'all'."""
    if jurisdiction == "all":
        return RULES
    return [r for r in RULES if jurisdiction in r.get("jurisdiction", [])]
