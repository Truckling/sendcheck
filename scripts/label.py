"""
label.py — Review and correct draft labels on emails.jsonl.

Shows each "unclear" email (and optionally all emails) and lets you
confirm or correct the label. Press Enter to accept the draft label.

Usage:
    python label.py              # review only "unclear" emails
    python label.py --all        # review every email
    python label.py --redo       # clear all human labels and start fresh
"""

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_FILE = Path(__file__).parent / "emails.jsonl"

LABELS = {
    "m": "marketing",
    "t": "transactional",
    "p": "transactional_with_promotion",
    "u": "unclear",
}

LABEL_HELP = "[m]arketing  [t]ransactional  [p]romotional-transactional  [u]nclear  [s]kip  [q]uit"


def load_emails():
    if not DATA_FILE.exists():
        print("emails.jsonl not found. Run fetch_training_data.py first.")
        sys.exit(1)
    emails = []
    with open(DATA_FILE, encoding="utf-8") as fh:
        for line in fh:
            try:
                emails.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return emails


def save_emails(emails):
    with open(DATA_FILE, "w", encoding="utf-8") as fh:
        for e in emails:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Review all emails, not just unclear")
    parser.add_argument("--redo", action="store_true", help="Clear human labels and start fresh")
    args = parser.parse_args()

    emails = load_emails()

    if args.redo:
        for e in emails:
            e["human_label"] = None
        save_emails(emails)
        print("All human labels cleared.")

    to_review = [
        e for e in emails
        if args.all or e.get("human_label") is None
    ]

    if not to_review:
        print("Nothing to label. All emails already have a human label.")
        labelled = sum(1 for e in emails if e.get("human_label"))
        print(f"Total labelled: {labelled}/{len(emails)}")
        return

    print(f"\n{len(to_review)} emails to review.")
    print(LABEL_HELP)
    print("Press Enter to accept the draft label.\n")

    labelled_this_session = 0

    for i, email in enumerate(to_review, 1):
        draft = email.get("draft_label", "unclear")
        print(f"[{i}/{len(to_review)}] {email['subject'][:70]}")
        print(f"  From: {email.get('sender', '')[:60]}")
        print(f"  Snippet: {email.get('body_snippet', '')[:120].strip()}")
        print(f"  Draft label: {draft}")

        while True:
            try:
                raw = input("  Label (Enter=accept): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nStopped.")
                save_emails(emails)
                print(f"Progress saved. {labelled_this_session} labelled this session.")
                return

            if raw == "":
                # Accept draft
                email["human_label"] = draft
                labelled_this_session += 1
                break
            elif raw == "s":
                # Skip — leave human_label as None
                break
            elif raw == "q":
                save_emails(emails)
                print(f"\nStopped. {labelled_this_session} labelled this session.")
                return
            elif raw in LABELS:
                email["human_label"] = LABELS[raw]
                labelled_this_session += 1
                break
            else:
                print(f"  Unknown key. {LABEL_HELP}")

        print()

    save_emails(emails)
    total_labelled = sum(1 for e in emails if e.get("human_label"))
    print(f"Done. {labelled_this_session} labelled this session.")
    print(f"Total labelled: {total_labelled}/{len(emails)}")
    print('Run "python train.py" when you have enough labels.')


if __name__ == "__main__":
    main()
