"""
gmail_test.py — Pull marketing emails from Gmail and run them through SendCheck.

Usage:
    python gmail_test.py                  # checks last 20 emails in inbox
    python gmail_test.py --label INBOX    # specify a label
    python gmail_test.py --max 50         # check more emails

Output: prints a summary table and writes report.txt in this folder.
"""

import argparse
import base64
import os
import sys
import re
from pathlib import Path
from datetime import datetime

# Force UTF-8 output so emoji in subject lines don't crash on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add the project root to the path so we can import sendcheck
sys.path.insert(0, str(Path(__file__).parent.parent))

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from sendcheck.checker import check_message

# Only read access — we never send or modify anything
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

CREDS_FILE = Path(__file__).parent / "credentials.json"
TOKEN_FILE = Path(__file__).parent / "token.json"


def get_gmail_service():
    """Authenticate and return a Gmail API client."""
    creds = None

    # Reuse a saved token if we have one
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid token, do the browser login flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def decode_body(payload):
    """Extract plain text body from a Gmail message payload."""
    body = ""

    def extract(part):
        nonlocal body
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                body += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif mime == "text/html" and not body:
            # Fall back to HTML if no plain text
            data = part.get("body", {}).get("data", "")
            if data:
                html = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                # Pull href values out first — unsubscribe links often live in href
                # attributes with generic link text like "click here"
                hrefs = " ".join(re.findall(r'href=["\']([^"\']+)["\']', html, re.I))
                body += re.sub(r"<[^>]+>", " ", html) + " " + hrefs
        for sub in part.get("parts", []):
            extract(sub)

    extract(payload)
    return body.strip()


def get_header(headers, name):
    """Get a header value by name from a list of header dicts."""
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def fetch_emails(service, label, max_results):
    """Return a list of (subject, sender, body) tuples."""
    print(f"Fetching up to {max_results} emails from label: {label}...")
    result = service.users().messages().list(
        userId="me", labelIds=[label], maxResults=max_results
    ).execute()

    messages = result.get("messages", [])
    if not messages:
        print("No emails found.")
        return []

    emails = []
    for i, msg in enumerate(messages, 1):
        full = service.users().messages().get(
            userId="me", id=msg["id"], format="full"
        ).execute()
        headers = full.get("payload", {}).get("headers", [])
        subject = get_header(headers, "subject") or "(no subject)"
        sender = get_header(headers, "from") or "(unknown sender)"
        body = decode_body(full.get("payload", {}))
        emails.append((subject, sender, body))
        print(f"  Fetched {i}/{len(messages)}: {subject[:60]}")

    return emails


def run_checks(emails):
    """Run each email through check_message and return results."""
    results = []
    for subject, sender, body in emails:
        result = check_message(
            subject=subject,
            body=body,
            channel="email",
            # We don't know consent status from the inbox — flag as unknown
            consent="unknown",
            # We can check if sender info appears in the body
            sender_identified=bool(re.search(r"(@|\+61|\.com\.au|pty ltd|abn)", body, re.I)),
        )
        results.append({
            "subject": subject,
            "sender": sender,
            "verdict": result["verdict"],
            "classification": result["classification"]["type"],
            "findings": result["findings"],
        })
    return results


def print_report(results, output_file):
    """Print a summary table and write full report to file."""
    counts = {"pass": 0, "review": 0, "block": 0}
    lines = []

    lines.append(f"SendCheck Gmail Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"Emails checked: {len(results)}")
    lines.append("")
    lines.append(f"{'VERDICT':<8} {'TYPE':<30} {'SUBJECT':<55} SENDER")
    lines.append("-" * 120)

    for r in results:
        counts[r["verdict"]] += 1
        lines.append(
            f"{r['verdict'].upper():<8} {r['classification']:<30} "
            f"{r['subject'][:54]:<55} {r['sender'][:40]}"
        )
        for f in r["findings"]:
            lines.append(f"         [{f['severity'].upper()}] {f['rule_id']} — {f['trigger']}")
        if r["findings"]:
            lines.append("")

    lines.append("")
    lines.append(f"Summary: {counts['pass']} pass / {counts['review']} review / {counts['block']} block")

    report = "\n".join(lines)
    print("\n" + report)

    Path(output_file).write_text(report, encoding="utf-8")
    print(f"\nFull report saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Test SendCheck against real Gmail emails.")
    parser.add_argument("--label", default="INBOX", help="Gmail label to fetch from (default: INBOX)")
    parser.add_argument("--max", type=int, default=20, help="Max number of emails to check (default: 20)")
    args = parser.parse_args()

    service = get_gmail_service()
    emails = fetch_emails(service, args.label, args.max)
    if not emails:
        return

    results = run_checks(emails)
    output_file = Path(__file__).parent / "report.txt"
    print_report(results, output_file)


if __name__ == "__main__":
    main()
