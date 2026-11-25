# SendCheck

Pre-send compliance checker for Australian email and SMS. Checks messages against the Spam Act 2003 before you send them.

Works as an MCP server — add it to Claude and ask it to check your emails in plain English.

## What it checks

| Rule | Law | Severity |
|------|-----|----------|
| Consent missing or unknown | s16 Spam Act | Block |
| Inferred consent risk | s16 Spam Act | Review |
| Sender not identified | s17 Spam Act | Block |
| No unsubscribe mechanism | s18 Spam Act | Block |
| Unsubscribe requires login | s18 Spam Act | Review |
| Transactional email with promotional content | s6 Spam Act | Review |
| SMS alphanumeric sender ID unregistered | ACMA 2026 | Info |

## Add to Claude

**Claude Desktop** — add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "sendcheck": {
      "command": "sendcheck"
    }
  }
}
```

**Claude Code** — run:

```bash
claude mcp add sendcheck sendcheck
```

## Install

```bash
pip install sendcheck
```

Requires Python 3.10+.

## Usage

Once added, ask Claude to check an email:

> "Check this email for Spam Act compliance. We have express consent from subscribers who opted in via our website."

Or paste in a draft:

> "Is this transactional email okay to send? It includes a discount offer at the bottom."

Claude will call SendCheck and return a verdict — **pass**, **review**, or **block** — with findings and fixes.

## Tools

| Tool | What it does |
|------|-------------|
| `check_message` | Full compliance check — returns verdict, findings, and check ID |
| `classify_message` | Classify as marketing / transactional / transactional_with_promotion / unclear |
| `explain_rule` | Look up a specific rule by ID |
| `list_rules` | Return all rules with severity and fix guidance |
| `get_evidence` | Retrieve past check records from the local evidence log |

## Consent values

Pass one of these when calling `check_message`:

- `express` — subscriber opted in via a form or checkbox
- `inferred` — existing customer relationship, no explicit opt-in
- `none` — no consent on record
- `unknown` — not specified (treated as none)

## Background

The Spam Act 2003 applies to all commercial electronic messages sent to Australian addresses. ACMA has issued fines over $7M for consent failures and $700K for transactional emails that included promotional content. SendCheck is a pre-send tool, not legal advice.

## License

MIT
