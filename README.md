# Truvek Comply

Pre-send compliance checker for email and SMS. Checks messages against five spam and privacy laws before you send them, and returns a verdict, findings and fixes.

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

**Claude Desktop:** add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "truvek-comply": {
      "command": "truvek-comply"
    }
  }
}
```

**Claude Code:** run:

```bash
claude mcp add truvek-comply truvek-comply
```

## Install

```bash
pip install truvek-comply
```

Requires Python 3.10+.

## Usage

Once added, ask Claude to check an email:

> "Check this email for compliance. We have express consent from subscribers who opted in via our website."

Specify a jurisdiction if you know your audience:

> "Check this email against Australian law only."

Or check all jurisdictions at once (the default):

> "Check this email. Our list includes US, Canadian, and Australian subscribers."

Claude will call Truvek Comply and return a verdict (**pass**, **review** or **block**) with findings tagged to the specific law they come from.

## Tools

| Tool | What it does |
|------|-------------|
| `check_message` | Full compliance check: verdict, findings tagged by law, check ID |
| `classify_message` | Classify as marketing / transactional / transactional_with_promotion / unclear |
| `explain_rule` | Look up a specific rule by ID |
| `list_rules` | Return all rules with severity, jurisdiction, and fix guidance |
| `get_evidence` | Retrieve past check records from the local evidence log (local installs only, not on the hosted endpoint) |

## Parameters

**`check_message` accepts:**

| Parameter | Values | Default |
|-----------|--------|---------|
| `channel` | `email`, `sms` | `email` |
| `consent` | `express`, `inferred`, `none`, `unknown` | `unknown` |
| `sender_identified` | `true`, `false` | `false` |
| `jurisdiction` | `au`, `us`, `ca`, `eu`, `all` | `all` |

**Consent by jurisdiction:**
- AU / CA / EU: opt-in required, so `none` or `unknown` blocks the send
- US CAN-SPAM: opt-out model. Prior consent not required, but opt-outs must be honoured

## Hosted endpoint

Remote MCP over Streamable HTTP at `https://truvek.io/mcp`, plus a JSON API at `POST https://truvek.io/check`. Both are open, rate limited to 120 requests a minute per IP, and capped at 1 MB per request. Message content is not stored.

```bash
claude mcp add --transport http truvek-comply https://truvek.io/mcp
```

## Part of the Truvek suite

[Truvek Design](https://truvek.io/design) makes email HTML render in Outlook, Gmail, Apple Mail and dark mode. Comply checks what the email says. Connect both and an agent runs the whole loop:

```
design_compile(layout, dialect)        # Truvek Design: repeat until lint passes
check_message(subject, body, consent)  # Truvek Comply
deliver_send_requirements(provider)    # Truvek Design: if your app sends its own mail
```

```bash
claude mcp add --transport http truvek-design https://design.truvek.io/mcp
```

## Background

Email and SMS marketing is regulated everywhere. ACMA (Australia) has issued fines over 7 million AUD for consent failures and 700K AUD for transactional emails containing promotional content. The FTC enforces CAN-SPAM with fines up to 51,744 USD per email. CRTC enforces CASL with penalties up to 10 million CAD per violation.

Truvek Comply is a pre-send compliance tool, not legal advice.

## License

MIT
