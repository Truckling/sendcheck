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
    from starlette.responses import JSONResponse, HTMLResponse
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
    from truvek_comply.server import mcp
    from truvek_comply.checker import check_message as _check_message
    print("[truvek-comply] truvek_comply.server OK", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR importing truvek_comply.server: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

# Disable DNS rebinding protection — we run behind Railway's TLS reverse proxy
# which already handles host validation at the edge. Enabling it here blocks
# legitimate requests because Railway rewrites the Host header internally.
transport_security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

_static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

@mcp.custom_route("/", methods=["GET"])
async def index(request: Request) -> HTMLResponse:
    with open(os.path.join(_static_dir, "index.html"), encoding="utf-8") as f:
        return HTMLResponse(f.read())

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
    return JSONResponse(result)

try:
    app = mcp.streamable_http_app(transport_security=transport_security)
    print("[truvek-comply] streamable_http_app OK", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR creating app: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

print(f"[truvek-comply] Listening on 0.0.0.0:{port}", flush=True)
uvicorn.run(app, host="0.0.0.0", port=port)
