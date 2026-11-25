"""
download_hf_datasets.py — Download HuggingFace email datasets and merge into emails.jsonl.

Freely accessible (no account needed):
  - Harshal3467/multiclass-email-classification (2,105 emails, MIT)

Requires a free HuggingFace account + token:
  - jason23322/high-accuracy-email-classifier (12K emails, Apache 2.0)
    To unlock: sign up at huggingface.co, go to the dataset page and
    accept the terms, then run: huggingface-cli login

Label mapping to SendCheck's four classes:
  marketing, transactional, transactional_with_promotion, unclear

Usage:
    python download_hf_datasets.py              # download all accessible datasets
    python download_hf_datasets.py --dry-run    # show mapping without writing
    python download_hf_datasets.py --hf-token TOKEN  # use a specific HF token
"""

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from datasets import load_dataset
except ImportError:
    print("HuggingFace datasets library not installed.")
    print("Run: pip install datasets --user")
    sys.exit(1)

OUTPUT_FILE = Path(__file__).parent / "emails.jsonl"

# --- Label mappings ---

HARSHAL_MAP = {
    # Clear marketing signals
    "Promotions":           "marketing",
    "Newsletters":          "marketing",
    # Transactional — triggered by user action, no promotional content expected
    "Finance & Bills":      "transactional",
    "Travel & Bookings":    "transactional",
    "Customer Support":     "transactional",
    "Reminders":            "transactional",
    # Ambiguous — keep but flag as unclear
    "Business":             "unclear",
    "Events & Invitations": "unclear",
    # Out of scope — skip
    "Personal":             None,
    "Job Application":      None,
}

JASON_MAP = {
    "promotions":   "marketing",
    "forum":        "marketing",        # community newsletters are commercial
    "updates":      "transactional",    # service/account updates
    "verify_code":  "transactional",    # OTP/auth emails
    "social_media": "unclear",          # social notifications
    "spam":         None,               # skip — spam is out of scope
}


def make_entry(source_name, original_label, mapped_label, subject, body):
    """Create an emails.jsonl entry matching the format from fetch_training_data.py."""
    # Deterministic ID so re-runs don't create duplicates
    fingerprint = hashlib.sha256(f"{source_name}|{original_label}|{subject}|{body}".encode()).hexdigest()[:16]
    return {
        "id": f"hf:{source_name}:{fingerprint}",
        "subject": subject or "",
        "sender": "",
        "body_snippet": (body or "")[:500],
        "body": body or "",
        "draft_label": mapped_label,
        "human_label": mapped_label,  # treat dataset labels as ground truth
        "source": f"hf:{source_name}",
        "original_label": original_label,
    }


def process_harshal(dry_run=False):
    """Process Harshal3467/multiclass-email-classification (no auth needed)."""
    print("\nDownloading Harshal3467/multiclass-email-classification...")
    try:
        ds = load_dataset("Harshal3467/multiclass-email-classification", split="train")
    except Exception as e:
        print(f"  Failed: {e}")
        return []

    print(f"  {len(ds)} emails loaded.")

    entries = []
    skipped = Counter()
    mapped = Counter()

    for row in ds:
        # Labels are a list — take the most specific one (last in list)
        raw_labels = row.get("labels") or []
        label = raw_labels[-1] if raw_labels else ""

        subject = str(row.get("subject") or "")
        body = str(row.get("body") or "")

        mapped_label = HARSHAL_MAP.get(label)
        if mapped_label is None:
            skipped[label] += 1
            continue

        mapped[mapped_label] += 1
        if not dry_run:
            entries.append(make_entry("Harshal3467", label, mapped_label, subject, body))

    print(f"  Mapped:  {dict(mapped)}")
    print(f"  Skipped: {dict(skipped)}")
    return entries


def process_jason(dry_run=False):
    """Process jason23322/high-accuracy-email-classifier (requires HF account)."""
    print("\nDownloading jason23322/high-accuracy-email-classifier...")
    try:
        ds = load_dataset("jason23322/high-accuracy-email-classifier", split="train")
    except Exception as e:
        msg = str(e)
        if "gated" in msg or "authenticated" in msg or "authentication" in msg.lower():
            print("  Skipped — dataset requires a HuggingFace account.")
            print("  To unlock:")
            print("    1. Sign up at huggingface.co (free)")
            print("    2. Go to huggingface.co/datasets/jason23322/high-accuracy-email-classifier")
            print("    3. Accept the dataset terms")
            print("    4. Run: huggingface-cli login")
            print("    5. Re-run this script")
        else:
            print(f"  Failed: {msg[:120]}")
        return []

    print(f"  {len(ds)} emails loaded.")

    entries = []
    skipped = Counter()
    mapped = Counter()

    for row in ds:
        label = str(row.get("label") or row.get("category") or row.get("class") or "")
        body = str(row.get("text") or row.get("body") or row.get("email") or row.get("content") or "")
        subject = str(row.get("subject") or "")

        mapped_label = JASON_MAP.get(label)
        if mapped_label is None:
            skipped[label] += 1
            continue

        mapped[mapped_label] += 1
        if not dry_run:
            entries.append(make_entry("jason23322", label, mapped_label, subject, body))

    print(f"  Mapped:  {dict(mapped)}")
    print(f"  Skipped: {dict(skipped)}")
    return entries


def load_existing_hf_ids():
    if not OUTPUT_FILE.exists():
        return set()
    ids = set()
    with open(OUTPUT_FILE, encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
                if e.get("source", "").startswith("hf:"):
                    ids.add(e["id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return ids


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--hf-token", help="HuggingFace API token for gated datasets")
    args = parser.parse_args()

    if args.hf_token:
        os.environ["HF_TOKEN"] = args.hf_token

    if args.dry_run:
        print("Dry run — nothing will be written.\n")

    all_entries = []
    all_entries += process_harshal(args.dry_run)
    all_entries += process_jason(args.dry_run)

    if args.dry_run:
        print(f"\nWould add up to {len(all_entries)} entries to emails.jsonl")
        return

    existing_ids = load_existing_hf_ids()
    new_entries = [e for e in all_entries if e["id"] not in existing_ids]

    with open(OUTPUT_FILE, "a", encoding="utf-8") as fh:
        for e in new_entries:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"\n{len(new_entries)} entries added to {OUTPUT_FILE}")

    # Final breakdown
    all_emails = []
    with open(OUTPUT_FILE, encoding="utf-8") as fh:
        for line in fh:
            try:
                all_emails.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    effective = lambda e: e.get("human_label") or e.get("draft_label")
    counts = Counter(effective(e) for e in all_emails if effective(e))

    print(f"\nTotal dataset: {len(all_emails)} emails")
    print("Label breakdown:")
    for label, count in sorted(counts.items(), key=lambda x: -x[1]):
        pct = count / len(all_emails) * 100
        print(f"  {label}: {count} ({pct:.0f}%)")

    print('\nRun "python train.py" to retrain with the expanded dataset.')


if __name__ == "__main__":
    main()
