"""
Standalone entry point for Railway deployment.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

port = int(os.environ.get("PORT", 8000))
print(f"[truvek-comply] Starting on port {port}", flush=True)
print(f"[truvek-comply] Python {sys.version}", flush=True)

try:
    import uvicorn
    print("[truvek-comply] uvicorn OK", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR importing uvicorn: {e}", flush=True)
    sys.exit(1)

try:
    from starlette.requests import Request
    from starlette.responses import JSONResponse, HTMLResponse, PlainTextResponse, Response
    print("[truvek-comply] starlette OK", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR importing starlette: {e}", flush=True)
    sys.exit(1)

try:
    from mcp.server.transport_security import TransportSecuritySettings
    print("[truvek-comply] transport_security OK", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR importing transport_security: {e}", flush=True)
    sys.exit(1)

try:
    from truvek_comply.server import mcp, with_next_tool as _with_next_tool
    from truvek_comply import suite as _suite, docs as _docs
    from truvek_comply.checker import check_message as _check_message
    print("[truvek-comply] truvek_comply.server OK", flush=True)
    from truvek_comply import ml_classifier
    # Logged so a deploy that silently falls back to patterns is visible
    print(f"[truvek-comply] ML model loaded: {ml_classifier._load()}", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR importing truvek_comply.server: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

# Disable DNS rebinding protection — we run behind Railway's TLS reverse proxy
# which already handles host validation at the edge. Enabling it here blocks
# legitimate requests because Railway rewrites the Host header internally.
transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def _page(name: str) -> HTMLResponse:
    with open(os.path.join(_static_dir, name), encoding="utf-8") as f:
        return HTMLResponse(f.read())


@mcp.custom_route("/", methods=["GET"])
async def index(request: Request) -> HTMLResponse:
    # The Truvek suite: the agent loop and one install command
    return _page("index.html")

@mcp.custom_route("/comply", methods=["GET"])
async def comply_page(request: Request) -> HTMLResponse:
    return _page("comply.html")

@mcp.custom_route("/design", methods=["GET"])
async def design_page(request: Request) -> HTMLResponse:
    # Truvek Design's product page. The Design MCP server itself runs separately at design.truvek.io
    return _page("design.html")

@mcp.custom_route("/truvek.css", methods=["GET"])
async def stylesheet(request: Request) -> Response:
    with open(os.path.join(_static_dir, "truvek.css"), encoding="utf-8") as f:
        return Response(f.read(), media_type="text/css", headers={"cache-control": "public, max-age=3600"})

@mcp.custom_route("/tools", methods=["GET"])
async def tools_page(request: Request) -> HTMLResponse:
    return HTMLResponse(_docs.tools_page(await _suite.all_tools()))

@mcp.custom_route("/llms.txt", methods=["GET"])
async def llms_txt(request: Request) -> PlainTextResponse:
    return PlainTextResponse(_docs.llms_txt(await _suite.all_tools()))

@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "truvek-comply"})

@mcp.custom_route("/check", methods=["POST"])
async def check(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    subject  = str(body.get("subject", "")).strip()
    text     = str(body.get("body", "")).strip()
    channel  = str(body.get("channel", "email")).strip()
    consent  = str(body.get("consent", "unknown")).strip()
    sender_identified = bool(body.get("sender_identified", False))
    if not text:
        return JSONResponse({"error": "body is required"}, status_code=400)
    if channel not in ("email", "sms"):
        channel = "email"
    if consent not in ("express", "inferred", "none", "unknown"):
        consent = "unknown"
    result = _check_message(subject, text, channel, consent=consent, sender_identified=sender_identified)
    return JSONResponse(_with_next_tool(result))

# get_evidence reads a log shared by every caller of this server, so on the
# hosted endpoint one user could read another's check records. Local installs keep it.
mcp.remove_tool("get_evidence")

try:
    from contextlib import AsyncExitStack, asynccontextmanager
    from starlette.applications import Starlette
    from truvek_comply.limits import LimitsMiddleware

    # Two MCP endpoints in one app:
    #   /comply/mcp  Comply only, original tool names (check_message and the rest)
    #   /mcp         every Truvek tool: comply_* here, design_* relayed to Truvek Design
    comply_app = mcp.streamable_http_app(streamable_http_path="/comply/mcp", transport_security=transport_security)
    suite_app = _suite.suite_server.streamable_http_app(streamable_http_path="/mcp", transport_security=transport_security)

    @asynccontextmanager
    async def lifespan(app):
        async with AsyncExitStack() as stack:
            await stack.enter_async_context(comply_app.router.lifespan_context(comply_app))
            await stack.enter_async_context(suite_app.router.lifespan_context(suite_app))
            yield

    suite_routes = [r for r in suite_app.routes if getattr(r, "path", "") == "/mcp"]
    site = Starlette(routes=list(comply_app.routes) + suite_routes, lifespan=lifespan)
    # Per-IP rate limit (RATE_LIMIT_PER_MIN, default 120) on every path, and a 1 MB body cap.
    # On Railway the caller's IP is read from X-Forwarded-For automatically (see limits.py).
    app = LimitsMiddleware(site)
    print("[truvek-comply] streamable_http_app OK (/mcp suite, /comply/mcp)", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR creating app: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

if __name__ == "__main__":
    print(f"[truvek-comply] Listening on 0.0.0.0:{port}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=port)
