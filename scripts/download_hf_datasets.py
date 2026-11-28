"""
download_hf_datasets.py — Download HuggingFace email/SMS datasets and merge into emails.jsonl.

Freely accessible (no account needed):
  - Harshal3467/multiclass-email-classification                (~2k emails)
  - SetFit/enron_spam                                          (~34k emails)
  - Deysi/spam-detection-dataset                               (~8k emails)
  - locuoco/the-biggest-spam-ham-phish-email-dataset-300000    (~168k emails)
  - marketeam/Marketing-Emails                                 (~16k emails)
  - morningstarxcdcode/adaption-synthetic-marketing-emails     (~16k emails)
  - ucirvine/sms_spam                                          (~5k SMS)
  - vsak/sms_spam_category                                     (~334 marketing SMS)

Requires a free HuggingFace account + token:
  - jason23322/high-accuracy-email-classifier    (~12k emails)
    To unlock: sign up at huggingface.co, go to the dataset page, accept
    the terms, then run: huggingface-cli login

Label mapping target classes:
  marketing, transactional, transactional_with_promotion, unclear

Usage:
    python download_hf_datasets.py              # all accessible datasets
    python download_hf_datasets.py --dry-run    # show counts without writing
    python download_hf_datasets.py --hf-token TOKEN
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
    "Promotions":           "marketing",
    "Newsletters":          "marketing",
    "Finance & Bills":      "transactional",
    "Travel & Bookings":    "transactional",
    "Customer Support":     "transactional",
    "Reminders":            "transactional",
    "Business":             "unclear",
    "Events & Invitations": "unclear",
    "Personal":             None,
    "Job Application":      None,
}

JASON_MAP = {
    "promotions":   "marketing",
    "forum":        "marketing",
    "updates":      "transactional",
    "verify_code":  "transactional",
    "social_media": "unclear",
    "spam":         None,
}

# Enron: ham = internal business / transactional; spam = out of scope
ENRON_MAP = {
    "ham":  "transactional",
    "spam": None,
}

# Deysi: not_spam = mixed (needs pattern classifier to sub-classify);
# spam = out of scope (actual unsolicited spam, not marketing)
DEYSI_MAP = {
    "not_spam": "unclear",
    "spam":     None,
}

# UCI SMS: 0 = ham (legitimate SMS), 1 = spam (unsolicited)
SMS_UCI_MAP = {
    0: "transactional",
    1: None,
}

# locuoco: 0=ham (Enron internal), 1=spam (skip), 2=phishing (skip)
LOCUOCO_MAP = {
    0: "unclear",
    1: None,
    2: None,
}

# marketeam/Marketing-Emails: single column, all marketing
# morningstarxcdcode: 'chosen' column, all marketing (synthetic)

# vsak SMS categories: advertisement=marketing SMS, phising/irrelevant=skip
VSAK_SMS_MAP = {
    "advertisement": "marketing",
    "phising":       None,
    "irrelevant":    None,
}


def make_entry(source_name, original_label, mapped_label, subject, body, channel="email"):
    fingerprint = hashlib.sha256(
        f"{source_name}|{original_label}|{subject}|{body[:200]}".encode()
    ).hexdigest()[:16]
    return {
        "id": f"hf:{source_name}:{fingerprint}",
        "subject": subject or "",
        "sender": "",
        "channel": channel,
        "body_snippet": (body or "")[:500],
        "body": body or "",
        "draft_label": mapped_label,
        "human_label": mapped_label,
        "source": f"hf:{source_name}",
        "original_label": original_label,
    }


def _load(name, split="train"):
    """Load a HF dataset split, return None on failure."""
    try:
        return load_dataset(name, split=split)
    except Exception as e:
        msg = str(e)
        if "gated" in msg or "authenticated" in msg or "authentication" in msg.lower():
            print(f"  Skipped — requires HuggingFace login.")
            print(f"  Run: huggingface-cli login")
        elif "doesn't exist" in msg or "cannot be accessed" in msg:
            print(f"  Not found on Hub.")
        else:
            print(f"  Error: {msg[:120]}")
        return None


def process_harshal(dry_run=False):
    print("\nHarshal3467/multiclass-email-classification...")
    ds = _load("Harshal3467/multiclass-email-classification")
    if ds is None:
        return []
    print(f"  {len(ds)} emails loaded.")
    entries, skipped, mapped = [], Counter(), Counter()
    for row in ds:
        raw_labels = row.get("labels") or []
        label = raw_labels[-1] if raw_labels else ""
        mapped_label = HARSHAL_MAP.get(label)
        if mapped_label is None:
            skipped[label] += 1
            continue
        mapped[mapped_label] += 1
        if not dry_run:
            entries.append(make_entry(
                "Harshal3467", label, mapped_label,
                str(row.get("subject") or ""),
                str(row.get("body") or ""),
            ))
    print(f"  Mapped: {dict(mapped)}  Skipped: {dict(skipped)}")
    return entries


def process_jason(dry_run=False):
    print("\njason23322/high-accuracy-email-classifier...")
    ds = _load("jason23322/high-accuracy-email-classifier")
    if ds is None:
        return []
    print(f"  {len(ds)} emails loaded.")
    entries, skipped, mapped = [], Counter(), Counter()
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
    print(f"  Mapped: {dict(mapped)}  Skipped: {dict(skipped)}")
    return entries


def process_enron(dry_run=False):
    print("\nSetFit/enron_spam (train + test)...")
    entries, skipped, mapped = [], Counter(), Counter()
    for split in ("train", "test"):
        ds = _load("SetFit/enron_spam", split=split)
        if ds is None:
            continue
        print(f"  {split}: {len(ds)} rows")
        for row in ds:
            label = str(row.get("label_text") or "")
            mapped_label = ENRON_MAP.get(label)
            if mapped_label is None:
                skipped[label] += 1
                continue
            subject = str(row.get("subject") or "")
            body = str(row.get("message") or row.get("text") or "")
            mapped[mapped_label] += 1
            if not dry_run:
                entries.append(make_entry("SetFit_enron", label, mapped_label, subject, body))
    print(f"  Mapped: {dict(mapped)}  Skipped: {dict(skipped)}")
    return entries


def process_deysi(dry_run=False):
    print("\nDeysi/spam-detection-dataset...")
    ds = _load("Deysi/spam-detection-dataset")
    if ds is None:
        return []
    print(f"  {len(ds)} rows loaded.")
    entries, skipped, mapped = [], Counter(), Counter()
    for row in ds:
        label = str(row.get("label") or "")
        mapped_label = DEYSI_MAP.get(label)
        if mapped_label is None:
            skipped[label] += 1
            continue
        body = str(row.get("text") or "")
        mapped[mapped_label] += 1
        if not dry_run:
            entries.append(make_entry("Deysi", label, mapped_label, "", body))
    print(f"  Mapped: {dict(mapped)}  Skipped: {dict(skipped)}")
    return entries


def process_uci_sms(dry_run=False):
    print("\nucirvine/sms_spam...")
    ds = _load("ucirvine/sms_spam")
    if ds is None:
        return []
    print(f"  {len(ds)} SMS loaded.")
    entries, skipped, mapped = [], Counter(), Counter()
    for row in ds:
        label = row.get("label")
        mapped_label = SMS_UCI_MAP.get(label)
        if mapped_label is None:
            skipped[str(label)] += 1
            continue
        body = str(row.get("sms") or "")
        mapped[mapped_label] += 1
        if not dry_run:
            entries.append(make_entry("ucirvine_sms", str(label), mapped_label, "", body, channel="sms"))
    print(f"  Mapped: {dict(mapped)}  Skipped: {dict(skipped)}")
    return entries


def process_locuoco(dry_run=False):
    """168k ham Enron emails — mapped to 'unclear' (internal business comms)."""
    print("\nlocuoco/the-biggest-spam-ham-phish-email-dataset-300000...")
    ds = _load("locuoco/the-biggest-spam-ham-phish-email-dataset-300000")
    if ds is None:
        return []
    print(f"  {len(ds)} rows loaded.")
    entries, skipped, mapped = [], Counter(), Counter()
    for row in ds:
        label = row.get("label")
        mapped_label = LOCUOCO_MAP.get(label)
        if mapped_label is None:
            skipped[str(label)] += 1
            continue
        body = str(row.get("text") or "")
        mapped[mapped_label] += 1
        if not dry_run:
            entries.append(make_entry("locuoco", str(label), mapped_label, "", body))
    print(f"  Mapped: {dict(mapped)}  Skipped: {dict(skipped)}")
    return entries


def process_marketeam(dry_run=False):
    """16k marketing emails — single text column with subject+body."""
    print("\nmarketeam/Marketing-Emails...")
    ds = _load("marketeam/Marketing-Emails")
    if ds is None:
        return []
    print(f"  {len(ds)} rows loaded.")
    entries = []
    for row in ds:
        text = str(row.get("0") or "")
        if not text:
            continue
        # Subject is usually the first line
        lines = text.splitlines()
        subject = ""
        body = text
        if lines and lines[0].lower().startswith("subject:"):
            subject = lines[0][8:].strip()
            body = "\n".join(lines[1:]).strip()
        if not dry_run:
            entries.append(make_entry("marketeam", "marketing", "marketing", subject, body))
    mapped = len(entries)
    print(f"  Mapped: {{'marketing': {mapped}}}")
    return entries


def process_morningstar(dry_run=False):
    """16k synthetic marketing emails — use the 'chosen' (improved) version."""
    print("\nmorningstarxcdcode/adaption-synthetic-marketing-emails...")
    ds = _load("morningstarxcdcode/adaption-synthetic-marketing-emails")
    if ds is None:
        return []
    print(f"  {len(ds)} rows loaded.")
    entries = []
    for row in ds:
        text = str(row.get("chosen") or row.get("0") or "")
        if not text:
            continue
        lines = text.splitlines()
        subject = ""
        body = text
        if lines and lines[0].lower().startswith("subject:"):
            subject = lines[0][8:].strip()
            body = "\n".join(lines[1:]).strip()
        if not dry_run:
            entries.append(make_entry("morningstar", "marketing", "marketing", subject, body))
    mapped = len(entries)
    print(f"  Mapped: {{'marketing': {mapped}}}")
    return entries


def process_vsak_sms(dry_run=False):
    """334 marketing SMS — requires streaming due to disk cache limits."""
    print("\nvsak/sms_spam_category (streaming)...")
    try:
        from datasets import load_dataset as _ld
        ds = _ld("vsak/sms_spam_category", split="train", streaming=True)
    except Exception as e:
        print(f"  Failed: {e}")
        return []
    entries, skipped, mapped = [], Counter(), Counter()
    for row in ds:
        label = str(row.get("Spam") or "")
        mapped_label = VSAK_SMS_MAP.get(label)
        if mapped_label is None:
            skipped[label] += 1
            continue
        body = str(row.get("Message") or "")
        mapped[mapped_label] += 1
        if not dry_run:
            entries.append(make_entry("vsak_sms", label, mapped_label, "", body, channel="sms"))
    print(f"  Mapped: {dict(mapped)}  Skipped: {dict(skipped)}")
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
    all_entries += process_enron(args.dry_run)
    all_entries += process_deysi(args.dry_run)
    all_entries += process_locuoco(args.dry_run)
    all_entries += process_marketeam(args.dry_run)
    all_entries += process_morningstar(args.dry_run)
    all_entries += process_uci_sms(args.dry_run)
    all_entries += process_vsak_sms(args.dry_run)

    if args.dry_run:
        total = len(all_entries)
        by_label = Counter(e["human_label"] for e in all_entries)
        by_channel = Counter(e.get("channel", "email") for e in all_entries)
        print(f"\nWould add up to {total} entries")
        print(f"By label:   {dict(by_label)}")
        print(f"By channel: {dict(by_channel)}")
        return

    existing_ids = load_existing_hf_ids()
    new_entries = [e for e in all_entries if e["id"] not in existing_ids]

    with open(OUTPUT_FILE, "a", encoding="utf-8") as fh:
        for e in new_entries:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"\n{len(new_entries)} new entries added ({len(all_entries) - len(new_entries)} already existed).")

    # Final breakdown
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
    for label, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {label}: {count}")

    print(f'\nTo reach 100k+ SMS or fill class gaps, run: python generate_synthetic.py')
    print('Then: python train.py')


if __name__ == "__main__":
    main()
