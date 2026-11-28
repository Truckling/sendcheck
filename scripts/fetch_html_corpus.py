"""
fetch_html_corpus.py - Save real marketing emails as HTML for local regression testing.

Usage:
    python scripts/fetch_html_corpus.py                  # 100 recent Promotions emails
    python scripts/fetch_html_corpus.py --max 200 --query "category:updates newer_than:90d"

Output goes to ../truvek-corpus/ (next to this repo, outside git) so real
email content can never be committed. Each email is saved as:
    <id>.html   the HTML part, exactly as sent
    <id>.json   subject, sender domain, plain text part

Personal data note: these are your own inbox emails. They stay on this
machine. Never copy them into a repo, test fixture or the website.
"""

import argparse
import base64
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent))

from fetch_training_data import get_gmail_service, get_header  # reuse read-only sign-in

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "truvek-corpus"


def find_part(payload, mime):
    """Return the decoded body of the first part with this MIME type."""
    if payload.get("mimeType") == mime:
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    for sub in payload.get("parts", []):
        found = find_part(sub, mime)
        if found:
            return found
    return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", default="default")
    parser.add_argument("--max", type=int, default=100)
    parser.add_argument("--query", default="category:promotions newer_than:60d")
    args = parser.parse_args()

    CORPUS_DIR.mkdir(exist_ok=True)
    service = get_gmail_service(args.account)

    ids, page = [], None
    while len(ids) < args.max:
        resp = service.users().messages().list(
            userId="me", q=args.query, maxResults=min(100, args.max - len(ids)), pageToken=page
        ).execute()
        ids += [m["id"] for m in resp.get("messages", [])]
        page = resp.get("nextPageToken")
        if not page:
            break

    saved = 0
    for msg_id in ids:
        if (CORPUS_DIR / f"{msg_id}.html").exists():
            continue
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        payload = msg["payload"]
        html = find_part(payload, "text/html")
        if not html:
            continue  # plain-text only, nothing for the HTML linter
        sender = get_header(payload["headers"], "From")
        meta = {
            "id": msg_id,
            "subject": get_header(payload["headers"], "Subject"),
            # Domain only: enough to group by sender without keeping full addresses
            "sender_domain": sender.rsplit("@", 1)[-1].strip("> ").lower() if "@" in sender else "",
            "list_unsubscribe": bool(get_header(payload["headers"], "List-Unsubscribe")),
            "list_unsubscribe_post": bool(get_header(payload["headers"], "List-Unsubscribe-Post")),
            "text": find_part(payload, "text/plain"),
        }
        (CORPUS_DIR / f"{msg_id}.html").write_text(html, encoding="utf-8")
        (CORPUS_DIR / f"{msg_id}.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        saved += 1

    print(f"Saved {saved} new emails to {CORPUS_DIR} ({len(ids)} matched the query).")


if __name__ == "__main__":
    main()
