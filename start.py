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

@mcp.custom_route("/extract-image", methods=["POST"])
async def extract_image(request: Request) -> JSONResponse:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return JSONResponse({"error": "Image extraction not configured on this server."}, status_code=503)
    try:
        body = await request.json()
        data_url = str(body.get("image", ""))
        if not data_url:
            return JSONResponse({"error": "No image provided."}, status_code=400)
        # Parse data URL: "data:image/png;base64,<data>"
        if "," in data_url:
            header, b64 = data_url.split(",", 1)
            media_type = header.split(":")[1].split(";")[0] if ":" in header else "image/jpeg"
        else:
            b64, media_type = data_url, "image/jpeg"
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                    {"type": "text", "text": "Extract all readable text from this email screenshot. Return only the text content, preserving structure where possible. Include the subject line if visible. No commentary."}
                ]
            }]
        )
        return JSONResponse({"text": msg.content[0].text})
    except Exception as e:
        return JSONResponse({"error": f"Could not read image: {e}"}, status_code=500)


@mcp.custom_route("/check", methods=["POST"])
async def check(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)
    subject = str(body.get("subject", "")).strip()
    text = str(body.get("body", "")).strip()
    channel = str(body.get("channel", "email")).strip()
    if not text:
        return JSONResponse({"error": "body is required"}, status_code=400)
    if channel not in ("email", "sms"):
        channel = "email"
    result = _check_message(subject, text, channel, consent="unknown", sender_identified=False)
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
