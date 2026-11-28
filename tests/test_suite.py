# test_suite.py - The combined endpoint (/mcp), the shared response shape, /tools and /llms.txt

import asyncio
import json
from types import SimpleNamespace

from truvek_comply import docs, suite
from truvek_comply.server import check_message, classify_message, explain_rule, list_rules
from mcp.types import CallToolRequestParams

DESIGN_TOOLS = [
    {"name": "design_compile", "description": "Compiles a layout. More text.", "inputSchema": {"type": "object", "properties": {"layout": {"type": "object"}, "dialect": {"type": "string", "enum": ["app", "braze"], "default": "app"}}, "required": ["layout"]}},
    {"name": "deliver_send_requirements", "description": "Headers and send code.", "inputSchema": {"type": "object", "properties": {"provider": {"type": "string"}}, "required": ["provider"]}},
]


class FakeDesign:
    def __init__(self, reply=None):
        self.calls = []
        self.reply = reply

    async def list_tools(self):
        return DESIGN_TOOLS

    async def call(self, method, params, client_ip):
        self.calls.append((method, params, client_ip))
        return self.reply


def run(coro):
    return asyncio.run(coro)


def ctx_with_ip(ip):
    return SimpleNamespace(request=SimpleNamespace(scope={"state": {"client_ip": ip}}))


def call_tool(name, args, ctx=None):
    result = run(suite._call_tool(ctx or ctx_with_ip("1.2.3.4"), CallToolRequestParams(name=name, arguments=args)))
    return result, json.loads(result.content[0].text)


# ---- the shared shape on Comply's own tools ----

def test_every_comply_tool_returns_verdict_findings_next_tool():
    outputs = [
        check_message("Sale", "50% off today"),
        classify_message("Your order shipped", "Tracking number 123"),
        explain_rule("consent_missing"),
        explain_rule("no_such_rule"),
        list_rules(),
    ]
    for out in outputs:
        assert list(out)[:3] == ["verdict", "findings", "next_tool"]
        assert out["verdict"] in ("pass", "review", "block", "info")


def test_findings_have_plain_titles_and_standard_fields():
    out = check_message("Last chance to win", "Buy your tickets now")
    for f in out["findings"]:
        assert list(f)[:4] == ["rule", "title", "scope", "line"] and "fix" in f
        assert f["title"][0].isupper() and "_" not in f["title"] and "—" not in f["title"]
        assert "—" not in f["trigger"] and "=" not in f["trigger"]


def test_next_tool_follows_the_loop():
    assert check_message("Sale", "50% off")["next_tool"] == "check_message"
    passed = check_message("Your order shipped", "Order 123 shipped. Acme Pty Ltd, 1 George Street, Brisbane QLD 4000", consent="express", sender_identified=True)
    assert passed["verdict"] == "pass"
    assert passed["next_tool"] == "deliver_send_requirements"
    assert passed["next_tool_server"] == "https://design.truvek.io/mcp"


# ---- the combined endpoint ----

def test_lists_design_tools_then_prefixed_comply_tools(monkeypatch):
    monkeypatch.setattr(suite, "design", FakeDesign())
    names = [t.name for t in run(suite.all_tools())]
    assert names[:2] == ["design_compile", "deliver_send_requirements"]
    assert set(names[2:]) == {"comply_check_message", "comply_classify_message", "comply_explain_rule", "comply_list_rules"}


def test_comply_descriptions_use_prefixed_names(monkeypatch):
    monkeypatch.setattr(suite, "design", FakeDesign())
    tools = {t.name: t for t in run(suite.all_tools())}
    assert "comply_list_rules" in tools["comply_explain_rule"].description


def test_comply_call_rewrites_next_tool_to_suite_names():
    result, body = call_tool("comply_check_message", {"subject": "Your order shipped", "body": "Order 123 shipped. Acme Pty Ltd, 1 George Street, Brisbane QLD 4000", "consent": "express", "sender_identified": True})
    assert not result.is_error
    assert body["next_tool"] == "deliver_send_requirements"
    assert "next_tool_server" not in body
    _, blocked = call_tool("comply_check_message", {"subject": "Sale", "body": "50% off"})
    assert blocked["next_tool"] == "comply_check_message"


def test_design_call_is_relayed_with_caller_ip_and_names_rewritten(monkeypatch):
    reply = {"result": {"content": [{"type": "text", "text": json.dumps({"verdict": "pass", "findings": [], "next_tool": "check_message", "next_tool_server": "https://truvek.io/comply/mcp"})}]}}
    fake = FakeDesign(reply)
    monkeypatch.setattr(suite, "design", fake)
    result, body = call_tool("design_compile", {"layout": {}}, ctx_with_ip("9.9.9.9"))
    assert fake.calls == [("tools/call", {"name": "design_compile", "arguments": {"layout": {}}}, "9.9.9.9")]
    assert body["next_tool"] == "comply_check_message"
    assert "next_tool_server" not in body
    assert result.structured_content["verdict"] == "pass"


def test_design_errors_and_unknown_tools_are_clear(monkeypatch):
    monkeypatch.setattr(suite, "design", FakeDesign({"error": {"code": -32602, "message": "Invalid arguments"}}))
    result, body = call_tool("design_lint", {})
    assert result.is_error and body["error"] == "Invalid arguments"
    result, body = call_tool("send_everything", {})
    assert result.is_error and "design_, deliver_ or comply_" in body["error"]
    result, body = call_tool("comply_check_message", {"subject": "x"})
    assert result.is_error and "Invalid arguments" in body["error"]


# ---- /tools and /llms.txt ----

def test_tools_page_and_llms_txt_cover_every_tool(monkeypatch):
    monkeypatch.setattr(suite, "design", FakeDesign())
    tools = run(suite.all_tools())
    page = docs.tools_page(tools)
    text = docs.llms_txt(tools)
    for t in tools:
        assert f'id="{t.name}"' in page
        assert f"- {t.name}:" in text
    assert "dialect" in page and "app or braze, default app" in page
    assert "https://truvek.io/mcp" in text and "next_tool" in text
    assert "—" not in page and "—" not in text
