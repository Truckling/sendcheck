"""
Standalone entry point for Railway deployment.
Runs the SendCheck MCP server in HTTP mode on $PORT.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import uvicorn
from sendcheck.server import mcp

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting SendCheck MCP server on port {port}", flush=True)
    app = mcp.streamable_http_app()
    uvicorn.run(app, host="0.0.0.0", port=port)
