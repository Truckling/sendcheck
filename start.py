"""
Standalone entry point for Railway/Render deployment.
Runs the SendCheck MCP server in HTTP mode on $PORT.
"""
import os
import sys

# Make the sendcheck package importable from the repo root
sys.path.insert(0, os.path.dirname(__file__))

from sendcheck.server import mcp

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting SendCheck MCP server on port {port}", flush=True)
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
