# test_evidence.py — Tests for the evidence logging module

import json
import pytest
from truvek_comply.evidence import record_check, get_evidence
from truvek_comply.checker import check_message


# A minimal passing result to use across tests
def _make_result():
    return check_message(
        subject="Your 20% off sale",
        body=(
            "Your 20% off sale is here! "
            "Unsubscribe: https://example.com/unsub. "
            "Sent by Acme Pty Ltd, 123 Main St Sydney."
        ),
        consent="express",
        sender_identified=True,
    )


class TestRecordCheck:

    def test_writes_one_line(self, tmp_path, monkeypatch):
        """record_check should write exactly one JSON line to the log file."""
        log_file = tmp_path / "evidence.jsonl"
        monkeypatch.setenv("SENDCHECK_LOG", str(log_file))

        result = _make_result()
        record_check("Subject", "Body", "test@example.com", result)

        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_line_is_valid_json(self, tmp_path, monkeypatch):
        """The written line must be valid JSON."""
        log_file = tmp_path / "evidence.jsonl"
        monkeypatch.setenv("SENDCHECK_LOG", str(log_file))

        result = _make_result()
        record_check("Subject", "Body", "test@example.com", result)

        line = log_file.read_text(encoding="utf-8").strip()
        entry = json.loads(line)  # will raise if not valid JSON
        assert isinstance(entry, dict)

    def test_returns_check_id(self, tmp_path, monkeypatch):
        """record_check should return a non-empty string check_id."""
        log_file = tmp_path / "evidence.jsonl"
        monkeypatch.setenv("SENDCHECK_LOG", str(log_file))

        result = _make_result()
        check_id = record_check("Subject", "Body", "test@example.com", result)

        assert isinstance(check_id, str)
        assert len(check_id) > 0

    def test_original_text_not_in_log(self, tmp_path, monkeypatch):
        """Subject, body, and recipient text must NOT appear in the log — only the hash."""
        log_file = tmp_path / "evidence.jsonl"
        monkeypatch.setenv("SENDCHECK_LOG", str(log_file))

        subject = "Super secret subject line"
        body = "Super secret body content that should never appear"
        recipient = "private@example.com"

        result = _make_result()
        record_check(subject, body, recipient, result)

        raw = log_file.read_text(encoding="utf-8")
        assert subject not in raw
        assert body not in raw
        assert recipient not in raw
        # The hash should be there instead
        assert "content_hash" in raw


class TestGetEvidence:

    def test_get_by_check_id(self, tmp_path, monkeypatch):
        """get_evidence with a check_id should return only the matching entry."""
        log_file = tmp_path / "evidence.jsonl"
        monkeypatch.setenv("SENDCHECK_LOG", str(log_file))

        result = _make_result()
        check_id = record_check("Sub1", "Body1", "a@example.com", result)
        record_check("Sub2", "Body2", "b@example.com", result)  # second entry

        entries = get_evidence(check_id=check_id)
        assert len(entries) == 1
        assert entries[0]["check_id"] == check_id

    def test_get_by_campaign_id(self, tmp_path, monkeypatch):
        """get_evidence with a campaign_id should return all entries for that campaign."""
        log_file = tmp_path / "evidence.jsonl"
        monkeypatch.setenv("SENDCHECK_LOG", str(log_file))

        result = _make_result()
        record_check("Sub1", "Body1", "a@example.com", result, campaign_id="camp-123")
        record_check("Sub2", "Body2", "b@example.com", result, campaign_id="camp-123")
        record_check("Sub3", "Body3", "c@example.com", result, campaign_id="camp-999")

        entries = get_evidence(campaign_id="camp-123")
        assert len(entries) == 2
        for e in entries:
            assert e["campaign_id"] == "camp-123"

    def test_get_all_recent_when_no_filter(self, tmp_path, monkeypatch):
        """get_evidence with no filters should return recent entries up to limit."""
        log_file = tmp_path / "evidence.jsonl"
        monkeypatch.setenv("SENDCHECK_LOG", str(log_file))

        result = _make_result()
        for i in range(5):
            record_check(f"Subject {i}", f"Body {i}", f"{i}@example.com", result)

        entries = get_evidence(limit=3)
        assert len(entries) == 3  # limited to 3

    def test_returns_empty_list_for_missing_log(self, tmp_path, monkeypatch):
        """get_evidence should return an empty list if the log file does not exist yet."""
        log_file = tmp_path / "nonexistent.jsonl"
        monkeypatch.setenv("SENDCHECK_LOG", str(log_file))

        entries = get_evidence()
        assert entries == []

    def test_entry_has_expected_keys(self, tmp_path, monkeypatch):
        """Each log entry should contain the required fields."""
        log_file = tmp_path / "evidence.jsonl"
        monkeypatch.setenv("SENDCHECK_LOG", str(log_file))

        result = _make_result()
        check_id = record_check("Sub", "Body", "x@example.com", result)

        entries = get_evidence(check_id=check_id)
        assert len(entries) == 1
        entry = entries[0]
        for key in ("check_id", "ts", "content_hash", "verdict", "rule_ids", "ruleset_version"):
            assert key in entry, f"Missing key '{key}' in log entry"
