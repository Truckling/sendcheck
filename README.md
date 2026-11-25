# SendCheck

Pre-send compliance checker for email and SMS. Checks messages against four major laws before you send them — returns a verdict, findings, and fixes.

Works as an MCP server. Add it to Claude and ask it to check your emails in plain English.

## Laws covered

| Law | Region | Channel |
|-----|--------|---------|
| Spam Act 2003 | Australia | Email + SMS |
| CAN-SPAM Act | United States | Email |
| CASL | Canada | Email + SMS |
| GDPR / ePrivacy Directive | European Union | Email + SMS |
| TCPA | United States | SMS |

## What it checks

| Rule | Laws | Severity |
|------|------|----------|
| Consent missing (opt-in required) | Spam Act, CASL, GDPR | Block |
| Opt-out not confirmed | CAN-SPAM | Review |
| Inferred/implied consent risk | Spam Act, CASL | Review |
| Sender not identified | All four laws | Block |
| No unsubscribe mechanism | All four laws | Block |
| Unsubscribe requires login | Spam Act, CASL, GDPR | Review |
| Physical mailing address missing | CAN-SPAM, CASL | Block |
| Transactional email with promotional content | Spam Act, CAN-SPAM, CASL | Review |
| SMS alphanumeric sender ID unregistered | ACMA (AU, from Jul 2026) | Info |
| SMS prior written consent missing | TCPA (US) | Block |
| SMS opt-in consent missing | ePrivacy (EU) | Block |

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

> "Check this email for compliance. We have express consent from subscribers who opted in via our website."

Specify a jurisdiction if you know your audience:

> "Check this email against Australian law only."

Or check all jurisdictions at once (the default):

> "Check this email — our list includes US, Canadian, and Australian subscribers."

Claude will call SendCheck and return a verdict — **pass**, **review**, or **block** — with findings tagged to the specific law they come from.

## Tools

| Tool | What it does |
|------|-------------|
| `check_message` | Full compliance check — verdict, findings tagged by law, check ID |
| `classify_message` | Classify as marketing / transactional / transactional_with_promotion / unclear |
| `explain_rule` | Look up a specific rule by ID |
| `list_rules` | Return all rules with severity, jurisdiction, and fix guidance |
| `get_evidence` | Retrieve past check records from the local evidence log |

## Parameters

**`check_message` accepts:**

| Parameter | Values | Default |
|-----------|--------|---------|
| `channel` | `email`, `sms` | `email` |
| `consent` | `express`, `inferred`, `none`, `unknown` | `unknown` |
| `sender_identified` | `true`, `false` | `false` |
| `jurisdiction` | `au`, `us`, `ca`, `eu`, `all` | `all` |

**Consent by jurisdiction:**
- AU / CA / EU: opt-in required — `none` or `unknown` blocks the send
- US CAN-SPAM: opt-out model — prior consent not required, but opt-outs must be honoured

## Background

Email and SMS marketing is regulated everywhere. ACMA (Australia) has issued fines over 7 million AUD for consent failures and 700K AUD for transactional emails containing promotional content. The FTC enforces CAN-SPAM with fines up to 51,744 USD per email. CRTC enforces CASL with penalties up to 10 million CAD per violation.

SendCheck is a pre-send compliance tool, not legal advice.

## License

MIT
