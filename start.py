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
    from starlette.responses import JSONResponse
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
    print("[truvek-comply] truvek_comply.server OK", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR importing truvek_comply.server: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

# PUBLIC_HOST is set in Railway environment variables to the public domain,
# e.g. web-production-a78fb254.up.railway.app or truvek.io
# Without it, the MCP DNS-rebinding protection blocks all external requests.
public_host = os.environ.get("PUBLIC_HOST", "")
allowed_hosts = ["localhost", f"localhost:{port}"]
if public_host:
    allowed_hosts.append(public_host)
    print(f"[truvek-comply] Allowing host: {public_host}", flush=True)
else:
    print("[truvek-comply] WARNING: PUBLIC_HOST not set — only localhost allowed", flush=True)

transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=allowed_hosts,
    allowed_origins=[f"https://{h}" for h in allowed_hosts if not h.startswith("localhost")],
)

# Add /health directly to the MCPServer — avoids wrapping in a second Starlette app
# which breaks the streamable-http routing context.
@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "truvek-comply"})

try:
    app = mcp.streamable_http_app(transport_security=transport_security)
    print("[truvek-comply] streamable_http_app OK", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR creating app: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

print(f"[truvek-comply] Listening on 0.0.0.0:{port}", flush=True)
uvicorn.run(app, host="0.0.0.0", port=port)
