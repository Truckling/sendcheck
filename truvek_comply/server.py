# server.py — MCP server entry point for SendCheck
# Supports both local stdio transport (Claude Desktop / Claude Code)
# and remote streamable-http transport (hosted deployment).
#
# Local:  sendcheck                           (stdio, default)
# Hosted: sendcheck --transport http          (streamable-http on $PORT)

import os
import argparse
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from .checker import check_message as _check, classify_message as _classify
from .evidence import record_check, get_evidence as _get_evidence
from .rules import RULES, RULESET_VERSION, get_rule

mcp = MCPServer("truvek-comply")

_read_only = ToolAnnotations(read_only_hint=True, destructive_hint=False)


@mcp.tool(
    title="Check message compliance",
    annotations=_read_only,
)
def check_message(
    subject: str,
    body: str,
    channel: str = "email",
    consent: str = "unknown",
    sender_identified: bool = False,
    recipient: str = "",
    campaign_id: str = "",
    jurisdiction: str = "all",
) -> dict:
    """
    Run email/SMS compliance checks before sending.

    Checks against: Spam Act 2003 (AU), CAN-SPAM (US), CASL (CA), GDPR/ePrivacy (EU).

    Parameters:
      subject           — message subject line
      body              — full message body text
      channel           — "email" or "sms"
      consent           — "express", "inferred", "none", or "unknown"
      sender_identified — True if the sender is clearly named in the message
      recipient         — recipient address (for evidence log only, never stored in full)
      campaign_id       — optional campaign reference for grouping evidence records
      jurisdiction      — "au", "us", "ca", "eu", or "all" (default: all — strictest)

    Returns a verdict (pass/review/block), findings with fixes tagged by law,
    the message classification, and a check_id for your evidence log.
    """
    result = _check(subject, body, channel, consent, sender_identified, jurisdiction)
    check_id = record_check(subject, body, recipient, result, campaign_id)
    result["check_id"] = check_id
    return result


@mcp.tool(
    title="Classify message type",
    annotations=_read_only,
)
def classify_message(subject: str, body: str, channel: str = "email") -> dict:
    """
    Classify a message as marketing, transactional, transactional_with_promotion, or unclear.

    Useful for understanding how the law will treat your message before running
    the full compliance check.
    """
    return _classify(subject, body, channel)


@mcp.tool(
    title="Explain a compliance rule",
    annotations=_read_only,
)
def explain_rule(rule_id: str) -> dict:
    """
    Look up a specific compliance rule by its ID.

    Returns the rule description, the law section it comes from, and how to fix it.
    Call list_rules() first to see all valid rule IDs.
    """
    rule = get_rule(rule_id)
    if rule is None:
        return {
            "error": f"Rule '{rule_id}' not found",
            "valid_ids": [r["id"] for r in RULES],
        }
    return rule


@mcp.tool(
    title="List all compliance rules",
    annotations=_read_only,
)
def list_rules() -> dict:
    """
    Return all compliance rules known to SendCheck.

    Covers Spam Act 2003 (AU), CAN-SPAM (US), CASL (CA), and GDPR/ePrivacy (EU).
    Includes rule IDs, severity levels, law sections, jurisdiction tags, and fix guidance.
    """
    return {"ruleset_version": RULESET_VERSION, "rules": RULES}


@mcp.tool(
    title="Retrieve evidence records",
    annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False),
)
def get_evidence(check_id: str = "", campaign_id: str = "", limit: int = 20) -> list:
    """
    Retrieve past compliance check records from the evidence log.

    Filter by check_id (single check) or campaign_id (all checks for a campaign).
    Leave both blank to retrieve the most recent entries.
    """
    return _get_evidence(check_id, campaign_id, limit)


def main():
    parser = argparse.ArgumentParser(description="SendCheck MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode: stdio (local) or http (hosted, reads $PORT)",
    )
    args, _ = parser.parse_known_args()

    if args.transport == "http":
        port = int(os.environ.get("PORT", 8000))
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
