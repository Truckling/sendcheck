"""
suite.py - The combined Truvek MCP endpoint at https://truvek.io/mcp.

One connection gives an agent every Truvek tool:
  comply_*                Truvek Comply, run in this process (the same functions as /comply/mcp)
  design_*, deliver_*     Truvek Design, forwarded to the Design service

Comply and Design stay separate services in separate languages. Nothing is
ported between them: this module only relays MCP calls. The per-product
endpoints (/comply/mcp here, https://design.truvek.io/mcp) keep working unchanged.

Privacy: tool arguments and results are relayed, never logged or stored.
"""

import asyncio
import json
import os
import re
import time
import urllib.error
import urllib.request

from mcp.server.lowlevel import Server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from . import server as comply

# On Railway this points at the Design service's private address, so the caller's IP
# (forwarded below) is what Design rate limits on. Over the public URL every combined
# call would share the web service's one IP.
DESIGN_MCP_URL = os.environ.get("DESIGN_MCP_URL", "https://design.truvek.io/mcp")
DESIGN_TIMEOUT_SECONDS = 60
TOOL_CACHE_SECONDS = 300
COMPLY_PREFIX = "comply_"

INSTRUCTIONS = """Truvek is a suite of tools for AI agents that send email.
The loop: build the email with design_compile (or check existing HTML with design_lint), fix findings until the verdict is not "block", check the content with comply_check_message, then call deliver_send_requirements if your app sends its own mail.
Every tool returns verdict, findings (rule, title, scope, line, fix) and next_tool, the tool to call next."""

# Comply's tools, keyed by their name on /comply/mcp.
COMPLY_FUNCTIONS = {
    "check_message": comply.check_message,
    "classify_message": comply.classify_message,
    "explain_rule": comply.explain_rule,
    "list_rules": comply.list_rules,
}


def _text_result(data, is_error: bool = False) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(data, indent=2, default=str))],
        structured_content=data if isinstance(data, dict) else None,
        is_error=is_error,
    )


def _prefix_names(text: str) -> str:
    """Rewrite bare Comply tool names in prose (for example "Call list_rules() first")."""
    for name in COMPLY_FUNCTIONS:
        text = re.sub(rf"(?<![\w]){name}(?=\b)", COMPLY_PREFIX + name, text)
    return text


def _to_suite_names(data):
    """Point next_tool at the combined endpoint's name for that tool.

    Each product names its own tools, and names a tool on another Truvek server together
    with next_tool_server. Here every tool is on one server, so next_tool_server goes."""
    if not isinstance(data, dict):
        return data
    nxt = data.get("next_tool")
    if nxt in COMPLY_FUNCTIONS:
        data["next_tool"] = COMPLY_PREFIX + nxt
    data.pop("next_tool_server", None)
    return data


class DesignClient:
    """Minimal MCP client for Design's stateless Streamable HTTP endpoint."""

    def __init__(self, url: str = DESIGN_MCP_URL):
        self.url = url
        self._tools: list[dict] = []
        self._tools_at = 0.0

    def _post(self, payload: dict, client_ip: str | None) -> dict:
        headers = {"content-type": "application/json", "accept": "application/json, text/event-stream"}
        if client_ip:
            # Design rate limits on X-Real-IP. Over Railway's private network no edge rewrites
            # it, so this is the caller's address as our own limiter saw it.
            headers["x-real-ip"] = client_ip
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=DESIGN_TIMEOUT_SECONDS) as res:
            raw = res.read().decode("utf-8")
        # Design answers with a single server-sent event: "event: message\ndata: {...}"
        for line in raw.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        return json.loads(raw)

    async def call(self, method: str, params: dict, client_ip: str | None) -> dict:
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        return await asyncio.to_thread(self._post, payload, client_ip)

    async def list_tools(self) -> list[dict]:
        if self._tools and time.monotonic() - self._tools_at < TOOL_CACHE_SECONDS:
            return self._tools
        try:
            reply = await self.call("tools/list", {}, None)
            self._tools = reply["result"]["tools"]
            self._tools_at = time.monotonic()
        except Exception as exc:  # Design down: keep serving Comply's tools and the last known list
            print(f"[truvek-suite] Could not list Design tools: {type(exc).__name__}", flush=True)
        return self._tools


design = DesignClient()


async def comply_tools() -> list[Tool]:
    tools = []
    for tool in await comply.mcp.list_tools():
        if tool.name not in COMPLY_FUNCTIONS:
            continue
        tools.append(tool.model_copy(update={
            "name": COMPLY_PREFIX + tool.name,
            "description": _prefix_names(tool.description or ""),
        }))
    return tools


async def all_tools() -> list[Tool]:
    """Every tool on the combined endpoint, Design's loop first."""
    design_tools = [Tool.model_validate(t) for t in await design.list_tools()]
    return design_tools + await comply_tools()


def _client_ip(ctx) -> str | None:
    request = getattr(ctx, "request", None)
    state = getattr(request, "scope", {}).get("state", {}) if request is not None else {}
    return state.get("client_ip")


async def _list_tools(ctx, params) -> ListToolsResult:
    return ListToolsResult(tools=await all_tools())


async def _call_tool(ctx, params) -> CallToolResult:
    name, args = params.name, dict(params.arguments or {})

    if name.startswith(COMPLY_PREFIX):
        fn = COMPLY_FUNCTIONS.get(name[len(COMPLY_PREFIX):])
        if fn is None:
            return _text_result({"error": f"Unknown tool {name}. Call tools/list for the tool names."}, True)
        try:
            return _text_result(_to_suite_names(fn(**args)))
        except TypeError as exc:
            return _text_result({"error": f"Invalid arguments for {name}: {exc}. Call tools/list for its input schema."}, True)

    if name.startswith(("design_", "deliver_")):
        try:
            reply = await design.call("tools/call", {"name": name, "arguments": args}, _client_ip(ctx))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                return _text_result({"error": "Truvek Design rate limit reached for your IP. Wait a minute, then retry the same call."}, True)
            return _text_result({"error": f"Truvek Design returned HTTP {exc.code}. Retry, or connect to https://design.truvek.io/mcp directly."}, True)
        except Exception:
            return _text_result({"error": "Truvek Design is unreachable right now. Retry in a minute, or connect to https://design.truvek.io/mcp directly."}, True)
        if "error" in reply:
            return _text_result({"error": reply["error"].get("message", "Truvek Design rejected the call.")}, True)
        result = reply["result"]
        content = []
        structured = None
        for item in result.get("content", []):
            if item.get("type") != "text":
                continue
            try:
                data = _to_suite_names(json.loads(item["text"]))
                structured = data if isinstance(data, dict) else structured
                content.append(TextContent(type="text", text=json.dumps(data, indent=2)))
            except (ValueError, TypeError):
                content.append(TextContent(type="text", text=item["text"]))
        return CallToolResult(content=content, structured_content=structured, is_error=bool(result.get("isError")))

    return _text_result({"error": f"Unknown tool {name}. Truvek tools start with design_, deliver_ or comply_."}, True)


suite_server = Server(
    "truvek",
    version="1.0.0",
    title="Truvek",
    instructions=INSTRUCTIONS,
    website_url="https://truvek.io",
    on_list_tools=_list_tools,
    on_call_tool=_call_tool,
)
