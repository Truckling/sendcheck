"""
docs.py - /tools (reference page) and /llms.txt, built from the live tool list.

Inputs come straight from each tool's JSON schema, so the reference cannot drift
from what the endpoint accepts. Outputs and the next tool are described here,
because a schema does not say what an agent should do with the result.
"""

import html
import json
import re

# What each tool returns (beyond verdict, findings, next_tool) and what it hands on to.
TOOL_DOCS = {
    "design_get_guide": ("The guide text for one topic: where generated email breaks and how to avoid it.", "design_get_schema"),
    "design_get_schema": ("The layout JSON schema and the list of modules (header, hero, columns, footer and the rest).", "design_compile"),
    "design_extract_brand": ("Brand colours, fonts and logo candidates from the user's own https site, with warnings.", "design_compile"),
    "design_compile": ("Email HTML for the chosen platform, a plain-text version and the lint summary.", "design_autofix or design_compile while blocked, then comply_check_message for marketing email or deliver_send_requirements for transactional"),
    "design_lint": ("Findings for existing email HTML, each with the rule, the line and the fix.", "design_autofix for fixable errors, design_lint after fixing by hand, then comply_check_message for marketing email or deliver_send_requirements for transactional"),
    "design_autofix": ("The HTML with mechanical issues fixed, what changed, and what is left to fix by hand.", "design_lint"),
    "design_explain_rule": ("Why a lint rule exists, which clients it affects and how to fix it.", "design_lint"),
    "deliver_send_requirements": ("Headers, DNS records and a code snippet for sending through Resend, SES, Postmark, SendGrid, Nodemailer or Mailgun.", "None. This is the end of the loop."),
    "comply_check_message": ("Findings by law (Spam Act, CAN-SPAM, CASL, GDPR and ePrivacy, TCPA), the message classification and a check_id.", "comply_check_message after fixing a block, otherwise deliver_send_requirements"),
    "comply_classify_message": ("Whether the message counts as marketing, transactional or transactional with promotion, and why.", "comply_check_message"),
    "comply_explain_rule": ("The law section, what it requires and how to fix it, for one rule.", "comply_check_message"),
    "comply_list_rules": ("Every compliance rule with its law, jurisdictions and severity.", "comply_check_message"),
}

LOOP = [
    ("Build", "design_compile", "Describe the email as a layout. Get HTML for your platform."),
    ("Lint", "design_lint", "Check any email HTML against 51 rendering rules."),
    ("Check content", "comply_check_message", "Check the words against spam and privacy law."),
    ("Send requirements", "deliver_send_requirements", "Get the headers and DNS your sender needs."),
]


def _first_sentence(text: str) -> str:
    text = " ".join((text or "").split())
    for end in (". ", "\n"):
        if end in text:
            return text.split(end)[0].rstrip(".") + "."
    return text


def _inputs(tool) -> list[tuple[str, str, bool]]:
    schema = tool.input_schema or {}
    required = set(schema.get("required", []))
    rows = []
    for name, prop in (schema.get("properties") or {}).items():
        if "enum" in prop:
            kind = " or ".join(str(v) for v in prop["enum"][:8])
        else:
            kind = prop.get("type") or ("object" if "properties" in prop or "additionalProperties" in prop else "any")
            if isinstance(kind, list):
                kind = " or ".join(kind)
        if "default" in prop and prop["default"] not in ("", None):
            default = prop["default"]
            kind += f", default {default if isinstance(default, str) else json.dumps(default)}"
        rows.append((name, kind, name in required))
    return rows


def _link_tools(text: str) -> str:
    """Turn tool names in already-escaped text into links to their entries."""
    names = sorted(TOOL_DOCS, key=len, reverse=True)
    return re.sub(r"\b(" + "|".join(names) + r")\b", r'<a href="#\1"><code>\1</code></a>', text)


def tools_page(tools) -> str:
    e = html.escape
    rows = []
    for tool in tools:
        returns, nxt = TOOL_DOCS.get(tool.name, ("See the tool description.", ""))
        inputs = _inputs(tool)
        input_html = "".join(
            f"<li><code>{e(n)}</code> <span>{e(k)}{'' if req else ', optional'}</span></li>" for n, k, req in inputs
        ) or "<li><span>No inputs</span></li>"
        rows.append(f"""
      <li class="tool" id="{e(tool.name)}">
        <div>
          <h3><code>{e(tool.name)}</code></h3>
          <p>{e(_first_sentence(tool.description or ''))}</p>
        </div>
        <div>
          <h4>Inputs</h4>
          <ul class="inputs">{input_html}</ul>
        </div>
        <div>
          <h4>Returns</h4>
          <p>{e(returns)}</p>
          <h4>Next tool</h4>
          <p>{_link_tools(e(nxt))}</p>
        </div>
      </li>""")
    count = len(tools)
    return PAGE.format(rows="".join(rows), count=count)


def llms_txt(tools) -> str:
    lines = [
        "# Truvek",
        "",
        "> Tools for AI agents that send email. Build email HTML that renders in every inbox, lint it, check the content against spam and privacy law, then get the send requirements for your provider.",
        "",
        "Every tool returns the same shape: verdict (pass, review, block, or info for reference tools), findings (each with rule, title, scope, line and fix) and next_tool (the tool to call next, or null at the end).",
        "",
        "## Connect",
        "",
        "- All tools, one endpoint (Streamable HTTP MCP): https://truvek.io/mcp",
        "- Install in Claude Code: claude mcp add --transport http truvek https://truvek.io/mcp",
        "- Comply only: https://truvek.io/comply/mcp (tools without the comply_ prefix)",
        "- Design only: https://design.truvek.io/mcp",
        "- Plain HTTP content check: POST https://truvek.io/check with subject, body, channel, consent, sender_identified",
        "- Rate limit: 120 requests a minute per IP on every endpoint. No account needed.",
        "",
        "## The loop",
        "",
    ]
    for i, (step, tool, what) in enumerate(LOOP, 1):
        lines.append(f"{i}. {step}: {tool}. {what}")
    lines += ["", "## Tools", ""]
    for tool in tools:
        returns, nxt = TOOL_DOCS.get(tool.name, ("See the tool description.", ""))
        inputs = ", ".join(f"{n} ({k}{'' if req else ', optional'})" for n, k, req in _inputs(tool)) or "none"
        lines.append(f"- {tool.name}: {_first_sentence(tool.description or '')} Inputs: {inputs}. Returns: {returns} Next: {nxt}")
    lines += [
        "",
        "## Docs",
        "",
        "- Tool reference: https://truvek.io/tools",
        "- Truvek Comply: https://truvek.io/comply",
        "- Truvek Design: https://truvek.io/design",
        "- Source (MIT): https://github.com/Truckling/truvek-comply and https://github.com/Truckling/truvek-design",
        "",
        "Truvek checks are a pre-send aid, not legal advice.",
        "",
    ]
    return "\n".join(lines)


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Truvek tool reference</title>
  <meta name="description" content="Every Truvek MCP tool: what it takes, what it returns and which tool to call next.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/truvek.css">
  <style>
    .shape {{ max-width: 70ch; }}
    .tool-list {{ list-style: none; }}
    .tool {{ display: grid; grid-template-columns: 1.1fr 1fr 1.2fr; gap: 24px; padding: 20px 0; border-top: 1px solid var(--rule-light); scroll-margin-top: 16px; }}
    .tool > * {{ min-width: 0; }}
    .tool h3 code {{ font-size: 14px; font-weight: 500; overflow-wrap: anywhere; }}
    .tool h4 {{ font-size: 14px; font-weight: 500; color: var(--text-muted); margin-bottom: 4px; }}
    .tool h4 + p + h4 {{ margin-top: 12px; }}
    .tool p {{ font-size: 15px; }}
    .inputs {{ list-style: none; font-size: 14px; }}
    .inputs li {{ padding: 2px 0; }}
    .inputs code {{ font-size: 13px; overflow-wrap: anywhere; }}
    .inputs span {{ color: var(--text-muted); }}
    @media (max-width: 860px) {{ .tool {{ grid-template-columns: 1fr; gap: 10px; }} }}
  </style>
</head>
<body>

<nav class="site" aria-label="Main">
  <div class="wrap">
    <div class="nav-inner">
      <div class="brand">
        <a href="/" class="logo">Truvek</a>
        <div class="suite" role="group" aria-label="Truvek products">
          <a href="/comply">Comply</a>
          <a href="/design">Design</a>
        </div>
      </div>
      <div class="nav-links">
        <a href="/tools" aria-current="page">Tools</a>
        <a href="/llms.txt">llms.txt</a>
      </div>
    </div>
  </div>
</nav>

<main>
<section class="hero">
  <div class="wrap">
    <h1>Tool reference</h1>
    <p class="lede">{count} tools on one endpoint, <code>https://truvek.io/mcp</code>. Each one lists what it takes, what it returns and the tool to call next.</p>
    <div class="shape">
      <h2>Every response has the same shape</h2>
      <pre class="code-block">{{
  "verdict": "block",          <span class="c">pass, review, block, or info for reference tools</span>
  "findings": [{{
    "rule": "unsubscribe_missing",
    "title": "Unsubscribe link missing",
    "scope": "AU, US, CA, EU",   <span class="c">laws for Comply, client or area for Design</span>
    "line": null,               <span class="c">line in the HTML, when there is one</span>
    "fix": "Add a working unsubscribe link."
  }}],
  "next_tool": "comply_check_message"
}}</pre>
    </div>
  </div>
</section>

<section>
  <div class="wrap">
    <h2>Tools</h2>
    <ul class="tool-list">{rows}
    </ul>
  </div>
</section>
</main>

<footer>
  <div class="cmy-strip" aria-hidden="true"><span class="cmy-cyan"></span><span class="cmy-magenta"></span><span class="cmy-yellow"></span><span class="cmy-navy"></span></div>
  <div class="wrap">
    <div class="foot-inner">
      <div class="foot-copy">Truvek. Not legal advice.</div>
      <div class="foot-links">
        <a href="/comply">Comply</a>
        <a href="/design">Design</a>
        <a href="/llms.txt">llms.txt</a>
      </div>
    </div>
  </div>
</footer>
</body>
</html>
"""
