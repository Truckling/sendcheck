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


def test_every_path_and_method_is_limited():
    for path, method in [("/", "GET"), ("/health", "GET"), ("/tools", "GET"), ("/llms.txt", "GET"), ("/comply/mcp", "POST"), ("/check", "POST")]:
        app = LimitsMiddleware(ok_app, per_minute=1, trust_proxy=False)
        assert call(app, path=path, method=method)[0] == 200
        assert call(app, path=path, method=method)[0] == 429, path


def test_pages_and_api_share_one_bucket_per_ip():
    app = LimitsMiddleware(ok_app, per_minute=2, trust_proxy=False)
    assert call(app, path="/", method="GET")[0] == 200
    assert call(app, path="/mcp")[0] == 200
    assert call(app, path="/check")[0] == 429


def test_client_ip_is_recorded_for_the_app():
    seen = {}

    async def app_reads_state(scope, receive, send):
        seen["ip"] = scope["state"]["client_ip"]
        await ok_app(scope, receive, send)

    app = LimitsMiddleware(app_reads_state, per_minute=5, trust_proxy=True)
    call(app, headers=[(b"x-real-ip", b"9.9.9.9"), (b"x-forwarded-for", b"9.9.9.9, 100.64.0.1")])
    assert seen["ip"] == "9.9.9.9"


def test_body_over_cap_rejected():
    app = LimitsMiddleware(ok_app, per_minute=10, max_body_bytes=10, trust_proxy=False)
    assert call(app, body=b"x" * 11)[0] == 413
    # No Content-Length: caught while streaming
    assert call(app, body=b"x" * 11, headers=[])[0] == 413


def test_trust_proxy_keys_on_x_real_ip_not_the_changing_edge_address():
    app = LimitsMiddleware(ok_app, per_minute=1, trust_proxy=True)
    # Railway's edge sets X-Real-IP to the caller; the right-most X-Forwarded-For entry is
    # an edge address that changes per request, so it must not split the caller's limit.
    assert call(app, headers=[(b"x-real-ip", b"5.5.5.5"), (b"x-forwarded-for", b"5.5.5.5, 152.233.0.97")])[0] == 200
    assert call(app, headers=[(b"x-real-ip", b"5.5.5.5"), (b"x-forwarded-for", b"5.5.5.5, 152.233.0.98")])[0] == 429
    # A different caller has its own bucket
    assert call(app, headers=[(b"x-real-ip", b"6.6.6.6")])[0] == 200


def test_without_trust_proxy_forwarding_headers_are_ignored():
    app = LimitsMiddleware(ok_app, per_minute=1, trust_proxy=False)
    assert call(app, headers=[(b"x-real-ip", b"1.1.1.1")], client="4.4.4.4")[0] == 200
    assert call(app, headers=[(b"x-real-ip", b"2.2.2.2")], client="4.4.4.4")[0] == 429
