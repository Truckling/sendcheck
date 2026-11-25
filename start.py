"""
Standalone entry point for Railway deployment.
Runs the SendCheck MCP server in HTTP mode on $PORT.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, Mount
from sendcheck.server import mcp


def health(request):
    return JSONResponse({"status": "ok", "service": "sendcheck"})


def make_app():
    mcp_app = mcp.streamable_http_app()
    return Starlette(routes=[
        Route("/health", health),
        Mount("/", app=mcp_app),
    ])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting SendCheck MCP server on port {port}", flush=True)
    app = make_app()
    uvicorn.run(app, host="0.0.0.0", port=port)
