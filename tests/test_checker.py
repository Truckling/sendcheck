# test_checker.py — Tests for message classification and compliance checking

import pytest
from sendcheck.checker import classify_message, check_message


# ---------------------------------------------------------------------------
# classify_message tests
# ---------------------------------------------------------------------------

class TestClassifyMessage:

    def test_marketing_email(self):
        """Body with 'sale' should be classified as marketing."""
        result = classify_message(
            subject="Weekend deals",
            body="Big sale on now! Save up to 50% on all items.",
        )
        assert result["type"] == "marketing"
        assert len(result["reasons"]) > 0

    def test_transactional_email(self):
        """Body with 'order confirmation' should be classified as transactional."""
        result = classify_message(
            subject="Your order confirmation",
            body="Thank you for your order. Your order confirmation number is 12345.",
        )
        assert result["type"] == "transactional"

    def test_transactional_with_promotion(self):
        """Body with both 'order' and 'sale' should be transactional_with_promotion."""
        result = classify_message(
            subject="Your order is on the way",
            body="Your order has shipped! Also, check out our flash sale — 30% off everything.",
        )
        assert result["type"] == "transactional_with_promotion"

    def test_unclear_generic_body(self):
        """A generic message with no signals should be classified as unclear."""
        result = classify_message(
            subject="Hello",
            body="Just checking in. Hope you are well.",
        )
        assert result["type"] == "unclear"

    def test_sms_channel_accepted(self):
        """channel parameter should be accepted without errors."""
        result = classify_message(
            subject="",
            body="Flash sale on now!",
            channel="sms",
        )
        assert result["type"] == "marketing"


# ---------------------------------------------------------------------------
# check_message tests
# ---------------------------------------------------------------------------

class TestCheckMessage:

    def test_block_when_consent_none(self):
        """consent='none' on a commercial message must produce a block verdict."""
        result = check_message(
            subject="Big sale",
            body="Sale on now! Unsubscribe: https://example.com/unsub",
            consent="none",
            sender_identified=True,
        )
        assert result["verdict"] == "block"
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "consent_missing" in rule_ids

    def test_block_when_consent_unknown(self):
        """consent='unknown' (the default) must also block a commercial message."""
        result = check_message(
            subject="Exclusive offer",
            body="Members only deal! Unsubscribe: https://example.com/unsub",
            consent="unknown",
            sender_identified=True,
        )
        assert result["verdict"] == "block"
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "consent_missing" in rule_ids

    def test_block_when_no_unsubscribe(self):
        """Missing unsubscribe link must block even with express consent and sender ID."""
        result = check_message(
            subject="Weekend sale",
            body="Huge discounts available now. Sent by Acme Pty Ltd.",
            consent="express",
            sender_identified=True,
        )
        assert result["verdict"] == "block"
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "unsubscribe_missing" in rule_ids

    def test_block_when_sender_not_identified(self):
        """sender_identified=False must add a sender_missing finding (block)."""
        result = check_message(
            subject="Sale now on",
            body="Big sale! Unsubscribe: https://example.com/unsub",
            consent="express",
            sender_identified=False,
        )
        assert result["verdict"] == "block"
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "sender_missing" in rule_ids

    def test_pass_fully_compliant_marketing_email(self):
        """
        A marketing email with express consent, sender identified, and an
        unsubscribe link should pass.
        """
        result = check_message(
            subject="Your 20% off sale",
            body=(
                "Your 20% off sale is here! "
                "Unsubscribe: https://example.com/unsub. "
                "Sent by Acme Pty Ltd, 123 Main St Sydney."
            ),
            channel="email",
            consent="express",
            sender_identified=True,
        )
        assert result["verdict"] == "pass"
        assert result["findings"] == []

    def test_review_for_inferred_consent(self):
        """consent='inferred' should produce a review (not block) finding."""
        result = check_message(
            subject="Sale on now",
            body=(
                "Save 20% today! "
                "Unsubscribe: https://example.com/unsub. "
                "Sent by Acme Pty Ltd."
            ),
            consent="inferred",
            sender_identified=True,
        )
        assert result["verdict"] == "review"
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "consent_inferred_risk" in rule_ids

    def test_transactional_with_promotion_triggers_review(self):
        """A transactional message with promotional content must trigger a review finding."""
        result = check_message(
            subject="Your order has shipped",
            body=(
                "Your order has shipped! "
                "Also, our flash sale is on — save 30%! "
                "Unsubscribe: https://example.com/unsub. "
                "Sent by Acme Pty Ltd."
            ),
            consent="express",
            sender_identified=True,
        )
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "transactional_with_promotion" in rule_ids
        # Overall verdict must be at least review
        assert result["verdict"] in ("review", "block")

    def test_transactional_pure_no_unsubscribe_needed(self):
        """
        A pure transactional message with sender identified should not require
        an unsubscribe link (it is not commercial).
        """
        result = check_message(
            subject="Your invoice #9001",
            body="Please find your invoice attached. Contact us at support@acme.com.",
            consent="express",
            sender_identified=True,
        )
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "unsubscribe_missing" not in rule_ids

    def test_sms_always_adds_sender_id_finding(self):
        """SMS channel must always add the sms_sender_id_unregistered finding."""
        result = check_message(
            subject="",
            body="Flash sale! Unsubscribe reply STOP. Sent by Acme.",
            channel="sms",
            consent="express",
            sender_identified=True,
        )
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "sms_sender_id_unregistered" in rule_ids

    def test_findings_contain_required_keys(self):
        """Each finding must contain the expected keys."""
        result = check_message(
            subject="Sale",
            body="Big sale!",
            consent="none",
            sender_identified=False,
        )
        for finding in result["findings"]:
            for key in ("rule_id", "severity", "section", "act", "trigger", "fix"):
                assert key in finding, f"Missing key '{key}' in finding: {finding}"

    def test_ruleset_version_present(self):
        """Result must include ruleset_version."""
        result = check_message(subject="Hi", body="Hello", consent="express", sender_identified=True)
        assert "ruleset_version" in result
        assert isinstance(result["ruleset_version"], str)
