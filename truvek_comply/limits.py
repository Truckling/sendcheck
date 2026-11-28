"""
limits.py - Rate limit and body size cap for the hosted server.

Wraps the whole web app. Every request, on every path and method, counts
against the caller's IP. Over the limit, the caller gets a 429 that says when
to retry. The body size cap applies to requests that carry a body.

The caller's IP is also stored in scope["state"]["client_ip"], so the combined
MCP endpoint can pass it on to Truvek Design and the limit there stays per caller.

Written as plain ASGI middleware (not Starlette's BaseHTTPMiddleware) so the
MCP server's streamed responses pass straight through untouched.
"""

import json
import os
import time
from collections import defaultdict, deque

WINDOW_SECONDS = 60


def _json_response(status: int, payload: dict, extra_headers=()):
    body = json.dumps(payload).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    headers += list(extra_headers)
    return status, headers, body


class LimitsMiddleware:
    def __init__(self, app, per_minute: int | None = None, max_body_bytes: int = 1_000_000, trust_proxy: bool | None = None):
        self.app = app
        self.per_minute = per_minute or int(os.environ.get("RATE_LIMIT_PER_MIN", "120"))
        self.max_body_bytes = max_body_bytes
        if trust_proxy is None:
            # Railway sets RAILWAY_ENVIRONMENT itself. Behind its proxy every request
            # arrives from the proxy's IP, so without this all callers share one limit.
            default = "true" if os.environ.get("RAILWAY_ENVIRONMENT") else "false"
            trust_proxy = os.environ.get("TRUST_PROXY", default).lower() == "true"
        self.trust_proxy = trust_proxy
        self.hits: dict[str, deque] = defaultdict(deque)

    def client_ip(self, scope) -> str:
        if self.trust_proxy:
            # Railway's edge overwrites X-Real-IP with the caller's address on every public
            # request, replacing any copy the caller sent (checked 28 Nov 2026). The right-most
            # X-Forwarded-For entry is not usable: it is one of many edge addresses, so keying on
            # it spread each caller across many buckets. Inside Railway's private network there
            # is no edge, and the only callers are our own services (the combined endpoint).
            for name, value in scope.get("headers", []):
                if name == b"x-real-ip" and value.strip():
                    return value.decode().strip()
        client = scope.get("client")
        return client[0] if client else "unknown"

    def allow(self, ip: str) -> tuple[bool, int]:
        """Record a hit. Returns (allowed, seconds until a slot frees up)."""
        now = time.monotonic()
        window = self.hits[ip]
        while window and now - window[0] > WINDOW_SECONDS:
            window.popleft()
        if len(window) >= self.per_minute:
            return False, int(WINDOW_SECONDS - (now - window[0])) + 1
        window.append(now)
        # Drop idle IPs now and then so memory stays flat
        if len(self.hits) > 10_000:
            for key in [k for k, v in self.hits.items() if not v or now - v[-1] > WINDOW_SECONDS]:
                del self.hits[key]
        return True, 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def reply(status, payload, extra_headers=()):
            status, headers, body = _json_response(status, payload, extra_headers)
            await send({"type": "http.response.start", "status": status, "headers": headers})
            await send({"type": "http.response.body", "body": body})

        ip = self.client_ip(scope)
        scope.setdefault("state", {})["client_ip"] = ip
        allowed, retry_after = self.allow(ip)
        if not allowed:
            return await reply(
                429,
                {
                    "error": "rate_limited",
                    "message": f"Limit is {self.per_minute} requests per minute per IP. Wait {retry_after} seconds, then retry the same request.",
                    "retry_after_seconds": retry_after,
                },
                [(b"retry-after", str(retry_after).encode())],
            )

        too_big = {
            "error": "body_too_large",
            "message": f"Request body is over {self.max_body_bytes} bytes. Send only the subject and body text of one message.",
        }
        for name, value in scope.get("headers", []):
            if name == b"content-length" and value.isdigit() and int(value) > self.max_body_bytes:
                return await reply(413, too_big)

        # Also count bytes as they stream in, for requests without Content-Length
        received = 0

        async def capped_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    raise BodyTooLarge()
            return message

        try:
            await self.app(scope, capped_receive, send)
        except BodyTooLarge:
            await reply(413, too_big)


class BodyTooLarge(Exception):
    pass
