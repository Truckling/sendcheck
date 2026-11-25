"""
fetch_training_data.py — Fetch emails from Gmail and save them as labelled training data.

Usage:
    python fetch_training_data.py               # fetch 500 emails from INBOX
    python fetch_training_data.py --max 1000    # fetch more
    python fetch_training_data.py --append      # append to existing emails.jsonl

The pattern-based classifier generates a draft label for each email.
Run label.py next to review and correct the "unclear" ones.
"""

import argparse
import base64
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from sendcheck.checker import classify_message

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"
OUTPUT_FILE = Path(__file__).parent / "emails.jsonl"


def get_gmail_service():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def decode_body(payload):
    """Extract text from a Gmail message payload, including href URLs."""
    body = ""

    def extract(part):
        nonlocal body
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                body += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif mime == "text/html" and not body:
            data = part.get("body", {}).get("data", "")
            if data:
                html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                hrefs = " ".join(re.findall(r'href=["\']([^"\']+)["\']', html, re.I))
                body += re.sub(r"<[^>]+>", " ", html) + " " + hrefs
        for sub in part.get("parts", []):
            extract(sub)

    extract(payload)
    return body.strip()


def get_header(headers, name):
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def load_existing_ids():
    """Return set of message IDs already in emails.jsonl."""
    if not OUTPUT_FILE.exists():
        return set()
    ids = set()
    with open(OUTPUT_FILE, encoding="utf-8") as fh:
        for line in fh:
            try:
                ids.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=500)
    parser.add_argument("--label", default="INBOX")
    parser.add_argument("--append", action="store_true", help="Append to existing emails.jsonl")
    args = parser.parse_args()

    service = get_gmail_service()

    existing_ids = load_existing_ids() if args.append else set()
    if not args.append and OUTPUT_FILE.exists():
        OUTPUT_FILE.unlink()

    print(f"Fetching up to {args.max} emails from {args.label}...")
    result = service.users().messages().list(
        userId="me", labelIds=[args.label], maxResults=args.max
    ).execute()
    messages = result.get("messages", [])
    print(f"Found {len(messages)} emails.")

    saved = 0
    skipped = 0

    with open(OUTPUT_FILE, "a", encoding="utf-8") as fh:
        for i, msg in enumerate(messages, 1):
            if msg["id"] in existing_ids:
                skipped += 1
                continue

            full = service.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()

            headers = full.get("payload", {}).get("headers", [])
            subject = get_header(headers, "subject") or "(no subject)"
            sender = get_header(headers, "from") or ""
            body = decode_body(full.get("payload", {}))

            # Draft label from the pattern classifier
            classification = classify_message(subject, body)
            draft_label = classification["type"]

            entry = {
                "id": msg["id"],
                "subject": subject,
                "sender": sender,
                # Store a snippet only — not the full body — to keep the file manageable
                "body_snippet": body[:500],
                "body": body,
                "draft_label": draft_label,
                # human_label starts as None — label.py fills this in
                "human_label": None,
            }
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            saved += 1

            if i % 50 == 0:
                print(f"  {i}/{len(messages)} fetched ({saved} saved, {skipped} skipped)...")

    print(f"\nDone. {saved} emails saved to {OUTPUT_FILE}")
    if skipped:
        print(f"{skipped} duplicates skipped.")

    # Print draft label breakdown
    counts: dict[str, int] = {}
    with open(OUTPUT_FILE, encoding="utf-8") as fh:
        for line in fh:
            try:
                label = json.loads(line)["draft_label"]
                counts[label] = counts.get(label, 0) + 1
            except (json.JSONDecodeError, KeyError):
                continue
    print("\nDraft label breakdown:")
    for label, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {label}: {count}")
    print(f'\nRun "python label.py" next to review the unclear ones.')


if __name__ == "__main__":
    main()
