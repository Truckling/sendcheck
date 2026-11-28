"""
envelope.py - The response shape every Truvek tool shares.

Every tool, in Comply and in Design, returns at least:
  verdict    "pass", "review" or "block" for checks; "info" for reference tools
  findings   list of {rule, title, scope, line, fix} (plus extra detail per product)
  next_tool  the tool an agent should call next, or None at the end of the loop

When next_tool lives on another Truvek server, next_tool_server gives its MCP URL.
The combined endpoint at https://truvek.io/mcp has every tool, so it drops
next_tool_server and rewrites next_tool to the combined (prefixed) name.
"""

DESIGN_MCP = "https://design.truvek.io/mcp"


def envelope(verdict: str, findings: list, next_tool: str | None, next_tool_server: str | None = None, **payload) -> dict:
    out = {"verdict": verdict, "findings": findings, "next_tool": next_tool}
    if next_tool_server:
        out["next_tool_server"] = next_tool_server
    out.update(payload)
    return out
