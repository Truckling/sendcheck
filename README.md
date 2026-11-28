# Truvek Comply

Pre-send compliance checker for email and SMS. Checks messages against five spam and privacy laws before you send them, and returns a verdict, findings and fixes.

Works as an MCP server over HTTP. Add it to Claude, or any MCP client, and your agent checks every message before it sends. Part of [Truvek](https://truvek.io), tools for AI agents that send email.

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

Over HTTP, nothing to install:

```bash
# Every Truvek tool (Comply and Design) on one endpoint
claude mcp add --transport http truvek https://truvek.io/mcp

# Comply only
claude mcp add --transport http truvek-comply https://truvek.io/comply/mcp
```

In Claude.ai or another MCP client, add a custom connector with either URL.

### Run it locally instead

```bash
pip install truvek-comply
claude mcp add truvek-comply truvek-comply
```

Requires Python 3.10+. The local server also keeps an evidence log of each check on your machine (`get_evidence`).

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

## Hosted endpoints

| Endpoint | What it serves |
|----------|----------------|
| `https://truvek.io/mcp` | Every Truvek tool: `comply_*` from this package, `design_*` and `deliver_*` relayed to Truvek Design |
| `https://truvek.io/comply/mcp` | Comply only, with the tool names above |
| `POST https://truvek.io/check` | JSON API: `subject`, `body`, `channel`, `consent`, `sender_identified` |
| `https://truvek.io/tools` | Reference for every tool: inputs, outputs and the next tool |
| `https://truvek.io/llms.txt` | The same reference for agents |

All are open, rate limited to 120 requests a minute per IP on every path, and capped at 1 MB per request. Message content is not stored or logged; the combined endpoint relays Design calls without keeping them.

## Response format

Every tool, in Comply and in Design, returns the same fields first:

```json
{
  "verdict": "block",
  "findings": [
    {
      "rule": "unsubscribe_missing",
      "title": "Unsubscribe link missing",
      "scope": "AU, US, CA, EU",
      "line": null,
      "fix": "Add a working unsubscribe link or reply-to address."
    }
  ],
  "next_tool": "check_message"
}
```

- `verdict`: `pass`, `review` or `block` from `check_message`; `info` from the reference tools.
- `findings`: `rule`, `title` (plain sentence case), `scope` (the laws it falls under), `line` (`null` for plain text), `fix`, then the detail: `why`, `trigger`, `severity`, `section`, `act`, `jurisdiction`. `rule_id` is kept for older callers.
- `next_tool`: what to call next. After a block it is `check_message` again, once fixed. After a pass or review it is `deliver_send_requirements`, with `next_tool_server` set to Truvek Design. On the combined endpoint the names carry their prefixes and `next_tool_server` is left out.

## Part of the Truvek suite

[Truvek Design](https://truvek.io/design) makes email HTML render in Outlook, Gmail, Apple Mail and dark mode. Comply checks what the email says. On `https://truvek.io/mcp` an agent runs the whole loop:

```
design_compile(layout, dialect)               # repeat until the verdict is not block
comply_check_message(subject, body, consent)
deliver_send_requirements(provider)           # if your app sends its own mail
```

## Background

Email and SMS marketing is regulated everywhere. ACMA (Australia) has issued fines over 7 million AUD for consent failures and 700K AUD for transactional emails containing promotional content. The FTC enforces CAN-SPAM with civil penalties of up to 53,088 USD per email ([Federal Register, 17 January 2025](https://www.federalregister.gov/documents/2025/01/17/2025-01361/adjustments-to-civil-penalty-amounts); the FTC kept the 2025 amounts for 2026). CRTC enforces CASL with penalties up to 10 million CAD per violation.

Truvek Comply is a pre-send compliance tool, not legal advice.

## License

MIT
