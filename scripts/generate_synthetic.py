"""
generate_synthetic.py — Generate synthetic labelled emails and SMS using Claude.

Generates training examples for classes and channels that lack enough real data.
Requires ANTHROPIC_API_KEY in the environment.

Usage:
    python generate_synthetic.py --channel sms --label marketing --count 1000
    python generate_synthetic.py --channel email --label transactional_with_promotion --count 500
    python generate_synthetic.py --channel sms --count 10000   # all SMS labels

    # To reach 100k SMS across all labels:
    python generate_synthetic.py --channel sms --count 33000 --label marketing
    python generate_synthetic.py --channel sms --count 33000 --label transactional
    python generate_synthetic.py --channel sms --count 34000 --label unclear

Output is appended to scripts/emails.jsonl in the same format as other sources.
Duplicates are skipped based on a content fingerprint.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import anthropic
except ImportError:
    print("anthropic library not installed. Run: pip install anthropic --user")
    sys.exit(1)

OUTPUT_FILE = Path(__file__).parent / "emails.jsonl"

VALID_LABELS   = ("marketing", "transactional", "transactional_with_promotion", "unclear")
VALID_CHANNELS = ("email", "sms")

# --- Prompts ---

PROMPTS = {
    ("email", "marketing"): """Write {n} distinct marketing email examples. Each is a real-world commercial email a brand might send: newsletters, promotions, sale announcements, product launches, re-engagement campaigns. Vary the industry (retail, SaaS, travel, food, finance, health). Include subject lines. Format each as:
---
Subject: <subject>
Body: <body>
---
Only output the emails. No commentary.""",

    ("email", "transactional"): """Write {n} distinct transactional email examples. These are triggered by user actions: order confirmations, shipping notifications, password resets, account alerts, booking confirmations, legal notices, invoices, receipts. No promotional content. Vary the industry. Format each as:
---
Subject: <subject>
Body: <body>
---
Only output the emails. No commentary.""",

    ("email", "transactional_with_promotion"): """Write {n} email examples where a transactional email (order, receipt, shipping, account notice) also contains a promotional section (upsell, cross-sell, discount, sale banner). The email starts transactional then includes a promotional block. Vary the industry. Format each as:
---
Subject: <subject>
Body: <body>
---
Only output the emails. No commentary.""",

    ("email", "unclear"): """Write {n} email examples that are ambiguous — they could be transactional or marketing but it's not obvious. Examples: internal newsletters, event invitations, account update notices, community digests, HR announcements. Vary the industry. Format each as:
---
Subject: <subject>
Body: <body>
---
Only output the emails. No commentary.""",

    ("sms", "marketing"): """Write {n} distinct marketing SMS messages a brand might send. Keep each under 160 characters. Vary the industry (retail, food, travel, services). Include things like sale announcements, flash offers, event reminders, loyalty rewards. Format each on its own line, prefixed with SMS:
SMS: <message>
Only output the messages. No commentary.""",

    ("sms", "transactional"): """Write {n} transactional SMS messages triggered by user actions: delivery updates, appointment reminders, verification codes, booking confirmations, payment receipts, fraud alerts. No promotional content. Keep each under 160 characters. Format each on its own line, prefixed with SMS:
SMS: <message>
Only output the messages. No commentary.""",

    ("sms", "transactional_with_promotion"): """Write {n} SMS messages where a transactional notification (delivery update, appointment reminder, booking) also includes a promotional element (discount offer, upsell). Keep each under 200 characters. Format each on its own line, prefixed with SMS:
SMS: <message>
Only output the messages. No commentary.""",

    ("sms", "unclear"): """Write {n} SMS messages that are ambiguous — could be transactional or marketing. Examples: "Your account is updated", "We have news for you", "Your request has been processed — plus a note about your plan". Keep each under 160 characters. Format each on its own line, prefixed with SMS:
SMS: <message>
Only output the messages. No commentary.""",
}

BATCH_SIZE = 50  # examples per API call


def load_existing_fingerprints():
    if not OUTPUT_FILE.exists():
        return set()
    fps = set()
    with open(OUTPUT_FILE, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                e = json.loads(line)
                if e.get("source", "").startswith("synthetic:"):
                    fps.add(e["id"].split(":")[-1])
            except (json.JSONDecodeError, KeyError):
                continue
    return fps


def fingerprint(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def parse_email_response(text):
    """Parse --- Subject: / Body: blocks from Claude response."""
    entries = []
    for block in text.split("---"):
        block = block.strip()
        if not block:
            continue
        subject = ""
        body_lines = []
        in_body = False
        for line in block.splitlines():
            if line.lower().startswith("subject:"):
                subject = line[8:].strip()
            elif line.lower().startswith("body:"):
                in_body = True
                rest = line[5:].strip()
                if rest:
                    body_lines.append(rest)
            elif in_body:
                body_lines.append(line)
        body = "\n".join(body_lines).strip()
        if body:
            entries.append((subject, body))
    return entries


def parse_sms_response(text):
    """Parse SMS: <message> lines from Claude response."""
    messages = []
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("sms:"):
            msg = line[4:].strip()
            if msg:
                messages.append(msg)
    return messages


def generate_batch(client, channel, label, n):
    prompt_template = PROMPTS.get((channel, label))
    if not prompt_template:
        raise ValueError(f"No prompt for channel={channel} label={label}")

    prompt = prompt_template.format(n=n)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text

    if channel == "sms":
        items = parse_sms_response(text)
        return [("", msg) for msg in items]
    else:
        return parse_email_response(text)


def make_entry(channel, label, subject, body, fp):
    return {
        "id": f"synthetic:{channel}:{label}:{fp}",
        "subject": subject,
        "sender": "",
        "channel": channel,
        "body_snippet": body[:500],
        "body": body,
        "draft_label": label,
        "human_label": label,
        "source": f"synthetic:{channel}",
        "original_label": label,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", choices=VALID_CHANNELS, default="sms")
    parser.add_argument("--label", choices=VALID_LABELS,
                        help="Class to generate. Omit to generate all labels equally.")
    parser.add_argument("--count", type=int, default=1000,
                        help="Total examples to generate (across all labels if --label omitted)")
    parser.add_argument("--api-key", help="Anthropic API key (or set ANTHROPIC_API_KEY env var)")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set. Pass --api-key or set the env var.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    labels_to_generate = [args.label] if args.label else list(VALID_LABELS)
    per_label = args.count // len(labels_to_generate)
    remainder = args.count % len(labels_to_generate)

    existing_fps = load_existing_fingerprints()
    total_written = 0

    for i, label in enumerate(labels_to_generate):
        target = per_label + (1 if i < remainder else 0)
        generated = 0
        print(f"\n[{label} / {args.channel}] target={target}")

        with open(OUTPUT_FILE, "a", encoding="utf-8") as fh:
            while generated < target:
                batch_n = min(BATCH_SIZE, target - generated)
                try:
                    items = generate_batch(client, args.channel, label, batch_n)
                except Exception as e:
                    print(f"  API error: {e} — retrying in 10s")
                    time.sleep(10)
                    continue

                written_this_batch = 0
                for subject, body in items:
                    fp = fingerprint(f"{label}|{subject}|{body}")
                    if fp in existing_fps:
                        continue
                    existing_fps.add(fp)
                    entry = make_entry(args.channel, label, subject, body, fp)
                    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    generated += 1
                    written_this_batch += 1
                    total_written += 1

                print(f"  +{written_this_batch} ({generated}/{target})")
                # Avoid hammering the API
                if generated < target:
                    time.sleep(1)

    print(f"\nDone. {total_written} examples written to {OUTPUT_FILE}")

    # Summary
    all_data = []
    with open(OUTPUT_FILE, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                all_data.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    effective = lambda e: e.get("human_label") or e.get("draft_label")
    counts = Counter(effective(e) for e in all_data if effective(e))
    channels = Counter(e.get("channel", "email") for e in all_data)
    print(f"\nTotal dataset: {len(all_data)} entries")
    print(f"By channel: {dict(channels)}")
    print("By label:")
    for lbl, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {lbl}: {count}")
    print('\nRun: python train.py')


if __name__ == "__main__":
    main()
