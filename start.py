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
print(f"[truvek-comply] sys.path: {sys.path[:3]}", flush=True)

try:
    import uvicorn
    print("[truvek-comply] uvicorn OK", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR importing uvicorn: {e}", flush=True)
    sys.exit(1)

try:
    import mcp
    print(f"[truvek-comply] mcp OK", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR importing mcp: {e}", flush=True)
    sys.exit(1)

try:
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route, Mount
    print("[truvek-comply] starlette OK", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR importing starlette: {e}", flush=True)
    sys.exit(1)

try:
    from truvek_comply.server import mcp as sendcheck_mcp
    print("[truvek-comply] truvek_comply.server OK", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR importing truvek_comply.server: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

try:
    mcp_app = sendcheck_mcp.streamable_http_app()
    print("[truvek-comply] streamable_http_app OK", flush=True)
except Exception as e:
    print(f"[truvek-comply] ERROR creating app: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)


def health(request):
    return JSONResponse({"status": "ok", "service": "truvek-comply"})


app = Starlette(routes=[
    Route("/health", health),
    Mount("/", app=mcp_app),
])

print(f"[truvek-comply] Listening on 0.0.0.0:{port}", flush=True)
uvicorn.run(app, host="0.0.0.0", port=port)
