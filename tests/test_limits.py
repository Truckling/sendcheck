# test_limits.py - Rate limit and body cap on the hosted endpoints

import asyncio

from truvek_comply.limits import LimitsMiddleware


async def ok_app(scope, receive, send):
    """Stand-in for the real app: reads the whole body, then replies 200."""
    while True:
        message = await receive()
        if not message.get("more_body"):
            break
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


def call(app, path="/mcp", method="POST", body=b"{}", headers=None, client="1.2.3.4"):
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers or [(b"content-length", str(len(body)).encode())],
        "client": (client, 1234),
    }
    sent = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    asyncio.run(app(scope, receive, send))
    return sent[0]["status"], dict(sent[0]["headers"]), sent[-1].get("body", b"")


def test_allows_up_to_limit_then_429_with_retry_after():
    app = LimitsMiddleware(ok_app, per_minute=3, trust_proxy=False)
    assert [call(app)[0] for _ in range(3)] == [200, 200, 200]
    status, headers, body = call(app)
    assert status == 429
    assert int(headers[b"retry-after"]) > 0
    assert b"retry" in body.lower()


def test_limit_is_per_ip():
    app = LimitsMiddleware(ok_app, per_minute=1, trust_proxy=False)
    assert call(app, client="1.1.1.1")[0] == 200
    assert call(app, client="2.2.2.2")[0] == 200
    assert call(app, client="1.1.1.1")[0] == 429


def test_get_requests_and_other_paths_not_limited():
    app = LimitsMiddleware(ok_app, per_minute=1, trust_proxy=False)
    for _ in range(3):
        assert call(app, path="/", method="GET")[0] == 200
        assert call(app, path="/health", method="GET")[0] == 200


def test_body_over_cap_rejected():
    app = LimitsMiddleware(ok_app, per_minute=10, max_body_bytes=10, trust_proxy=False)
    assert call(app, body=b"x" * 11)[0] == 413
    # No Content-Length: caught while streaming
    assert call(app, body=b"x" * 11, headers=[])[0] == 413


def test_trust_proxy_uses_rightmost_forwarded_ip():
    app = LimitsMiddleware(ok_app, per_minute=1, trust_proxy=True)
    # Caller fakes the left-hand entry each time; the proxy-added right-hand IP is what counts
    assert call(app, headers=[(b"x-forwarded-for", b"9.9.9.1, 5.5.5.5")])[0] == 200
    assert call(app, headers=[(b"x-forwarded-for", b"9.9.9.2, 5.5.5.5")])[0] == 429
