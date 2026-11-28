"""
generate_templates.py — Template-based synthetic training data generator.

Generates realistic labelled emails and SMS using randomised templates.
No API or internet connection needed. Run locally, runs fast.

Usage:
    python generate_templates.py                        # 100k SMS + 5k email top-ups
    python generate_templates.py --channel sms --count 100000
    python generate_templates.py --channel email --label transactional_with_promotion --count 5000
    python generate_templates.py --dry-run              # show counts without writing
"""

import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUTPUT_FILE = Path(__file__).parent / "emails.jsonl"
random.seed(42)

VALID_LABELS   = ("marketing", "transactional", "transactional_with_promotion", "unclear")
VALID_CHANNELS = ("email", "sms")

# ── Vocabulary pools ────────────────────────────────────────────────────────

BRANDS = [
    "Cotton On", "Kmart", "Big W", "JB Hi-Fi", "Harvey Norman", "Myer", "David Jones",
    "Woolworths", "Coles", "Aldi", "IGA", "Chemist Warehouse", "Priceline", "Terry White",
    "Uber Eats", "DoorDash", "Menulog", "Deliveroo", "McDonald's", "KFC", "Hungry Jack's",
    "Domino's", "Pizza Hut", "Subway", "Grill'd", "Nando's", "Guzman y Gomez",
    "Qantas", "Virgin Australia", "Jetstar", "Rex Airlines", "Tigerair",
    "Airbnb", "Booking.com", "Expedia", "Hotels.com", "Wotif",
    "CommBank", "Westpac", "ANZ", "NAB", "Bendigo Bank", "Macquarie", "ING",
    "Telstra", "Optus", "Vodafone", "Boost Mobile", "Belong",
    "Netflix", "Stan", "Binge", "Foxtel", "Disney+", "Apple TV+",
    "Officeworks", "Bunnings", "IKEA", "Fantastic Furniture", "Amart",
    "Rebel Sport", "Anaconda", "BCF", "Decathlon", "Lorna Jane", "Lululemon",
    "THE ICONIC", "ASOS", "Catch", "Kogan", "Amazon AU", "eBay AU",
    "Canva", "Atlassian", "Xero", "MYOB", "Seek", "REA Group",
    "Medibank", "Bupa", "nib", "HCF", "HBF",
    "Fitness First", "Anytime Fitness", "F45", "Gold's Gym", "Snap Fitness",
    "Petbarn", "Petstock", "City Farmers",
    "Dan Murphy's", "BWS", "First Choice Liquor",
    "Mecca", "Sephora", "Adore Beauty",
]

PRODUCTS = [
    "order", "delivery", "booking", "subscription", "account", "membership",
    "purchase", "reservation", "appointment", "shipment", "package",
]

DISCOUNTS = [
    "10%", "15%", "20%", "25%", "30%", "40%", "50%",
    "$5", "$10", "$15", "$20", "$25", "$50",
]

AMOUNTS = [
    "$12.99", "$19.95", "$24.99", "$34.95", "$49.99", "$59.95", "$79.00",
    "$89.95", "$99.00", "$119.99", "$149.95", "$199.00", "$249.95", "$299.00",
]

REFS = [lambda: f"#{random.randint(100000, 999999)}", lambda: f"ORD-{random.randint(10000,99999)}"]

DATES = [
    "today", "tomorrow", "this Saturday", "this Sunday", "Monday",
    "Tuesday", "Wednesday", "Thursday", "Friday",
    "2 Jan", "15 Jan", "3 Feb", "20 Feb", "5 Mar", "18 Mar",
]

TIMES = [
    "9am", "10am", "11am", "12pm", "1pm", "2pm", "3pm", "4pm", "5pm", "6pm",
]

UNSUBSCRIBE_SMS = [
    "Reply STOP to opt out.",
    "Txt STOP to unsubscribe.",
    "Reply STOP to end.",
    "To stop msgs reply STOP.",
    "Opt out: reply STOP.",
]

UNSUBSCRIBE_EMAIL = [
    "Unsubscribe | Manage preferences | Privacy policy",
    "To unsubscribe from these emails, click here.",
    "You can unsubscribe at any time by clicking the link below.",
    "Unsubscribe from this list.",
]

ADDRESSES = [
    "Level 5, 100 Harris St, Pyrmont NSW 2009",
    "Tower 1, 100 Barangaroo Ave, Sydney NSW 2000",
    "680 George St, Sydney NSW 2000",
    "360 Collins St, Melbourne VIC 3000",
    "250 St Georges Tce, Perth WA 6000",
    "PO Box 1234, South Melbourne VIC 3205",
    "GPO Box 9999, Brisbane QLD 4001",
]


def ref():
    return random.choice(REFS)()


def brand():
    return random.choice(BRANDS)


def product():
    return random.choice(PRODUCTS)


def discount():
    return random.choice(DISCOUNTS)


def amount():
    return random.choice(AMOUNTS)


def date():
    return random.choice(DATES)


def time_():
    return random.choice(TIMES)


def unsub_sms():
    return random.choice(UNSUBSCRIBE_SMS)


def unsub_email():
    return random.choice(UNSUBSCRIBE_EMAIL)


def address():
    return random.choice(ADDRESSES)


# ── SMS Templates ────────────────────────────────────────────────────────────

def sms_marketing():
    templates = [
        f"{brand()}: {discount()} off sitewide this weekend only. Shop now: [link] {unsub_sms()}",
        f"[{brand()}] Flash sale! Save {discount()} on selected items — today only. [link] {unsub_sms()}",
        f"{brand()} VIP: You have a {discount()} off voucher waiting. Use it before {date()}. [link] {unsub_sms()}",
        f"Hi! {brand()} here. Members get {discount()} off everything {date()} and {date()}. Tap to shop: [link] {unsub_sms()}",
        f"Your {brand()} reward: {discount()} off your next order. Expires {date()}. [link] {unsub_sms()}",
        f"{brand()} sale starts {date()}! Up to {discount()} off. Be first: [link] {unsub_sms()}",
        f"[{brand()}] New arrivals are here — {discount()} off for members this week. [link] {unsub_sms()}",
        f"Don't miss it — {brand()} clearance: up to {discount()} off. Ends {date()}. [link] {unsub_sms()}",
        f"{brand()}: Spend {amount()} or more and get {discount()} off. Valid {date()}. [link] {unsub_sms()}",
        f"Exclusive offer from {brand()}: {discount()} off your next purchase. Shop: [link] {unsub_sms()}",
        f"[{brand()}] Your points are expiring! Redeem before {date()} for {discount()} off. [link] {unsub_sms()}",
        f"{brand()} double points {date()} only. Shop now: [link] {unsub_sms()}",
        f"Back in stock at {brand()}! Get it now with {discount()} off. [link] {unsub_sms()}",
        f"{brand()}: Refer a friend and you both get {discount()} off. Share: [link] {unsub_sms()}",
        f"[{brand()}] We miss you! Here's {discount()} off to welcome you back. [link] {unsub_sms()}",
    ]
    return random.choice(templates)


def sms_transactional():
    templates = [
        f"{brand()}: Your {product()} {ref()} has been confirmed. Total: {amount()}. Track: [link]",
        f"[{brand()}] Your order {ref()} is on its way! Expected delivery: {date()}. Track: [link]",
        f"{brand()}: Delivery update — your {product()} arrives {date()} between {time_()} and {time_()}.",
        f"[{brand()}] Verification code: {random.randint(100000,999999)}. Valid 10 mins. Don't share this code.",
        f"{brand()}: Your appointment is confirmed for {date()} at {time_()}. Ref: {ref()}. Reply CANCEL to cancel.",
        f"[{brand()}] Payment of {amount()} received. Receipt {ref()}. Thank you.",
        f"{brand()}: Your booking {ref()} is confirmed. {date()} at {time_()}. Need help? Reply to this message.",
        f"[{brand()}] Your account password was changed. If this wasn't you, call us immediately.",
        f"{brand()}: Your subscription renews {date()} for {amount()}. Manage: [link]",
        f"[{brand()}] We attempted delivery of your {product()} {date()}. Rebook: [link]",
        f"{brand()}: Your return {ref()} has been received. Refund of {amount()} within 5 business days.",
        f"[{brand()}] Reminder: your appointment is {date()} at {time_()}. Reply YES to confirm or NO to cancel.",
        f"{brand()}: Your order {ref()} has been picked up by the courier. ETA: {date()}.",
        f"[{brand()}] One-time code: {random.randint(100000,999999)}. Use this to verify your login.",
        f"{brand()}: Your {product()} is ready for collection at [store]. Ref: {ref()}.",
    ]
    return random.choice(templates)


def sms_transactional_with_promotion():
    transactional_parts = [
        f"Your order {ref()} has shipped.",
        f"Delivery confirmed for {date()}.",
        f"Your booking {ref()} is confirmed for {date()} at {time_()}.",
        f"Payment of {amount()} received.",
        f"Your appointment is set for {date()} at {time_()}.",
        f"Your return has been processed. Refund of {amount()} on its way.",
    ]
    promo_parts = [
        f"While you wait, save {discount()} on your next order: [link] {unsub_sms()}",
        f"Plus, enjoy {discount()} off your next purchase. Shop: [link] {unsub_sms()}",
        f"As a thank you, here's {discount()} off anything in-store. Valid {date()}. {unsub_sms()}",
        f"Don't miss our sale — up to {discount()} off. [link] {unsub_sms()}",
        f"Treat yourself: {discount()} off selected items this week. [link] {unsub_sms()}",
    ]
    b = brand()
    return f"[{b}] {random.choice(transactional_parts)} {random.choice(promo_parts)}"


def sms_unclear():
    templates = [
        f"[{brand()}] Your account has been updated. Log in to review your details: [link]",
        f"{brand()}: We have an update about your {product()}. See details: [link]",
        f"[{brand()}] Important information about your account. Please review: [link]",
        f"{brand()}: Your preferences have been saved. View them here: [link]",
        f"[{brand()}] We've made some changes you should know about. Read more: [link]",
        f"{brand()}: A note about your recent activity. See details: [link]",
        f"[{brand()}] Please review the latest update to your {product()}. [link]",
        f"{brand()}: Action may be required on your account. Check now: [link]",
        f"[{brand()}] Your {date()} summary is ready to view. [link]",
        f"{brand()}: We noticed something on your account. Please check: [link]",
        f"[{brand()}] Your request has been received. We'll be in touch shortly.",
        f"{brand()}: Thanks for getting in touch. Someone will respond within 24 hours.",
        f"[{brand()}] Just a heads up — things are changing on {date()}. Details: [link]",
        f"{brand()}: Quick update on your {product()}. No action needed. [link]",
        f"[{brand()}] Your {product()} details have been updated. Any questions? Reply here.",
    ]
    return random.choice(templates)


# ── Email Templates ──────────────────────────────────────────────────────────

def email_transactional_with_promotion():
    b = brand()
    r = ref()
    amt = amount()
    d = date()
    disc = discount()

    transactional_subjects = [
        f"Your order {r} has shipped",
        f"Booking confirmation {r}",
        f"Your receipt from {b}",
        f"Your {b} order is on its way",
        f"Delivery update for {r}",
        f"Your appointment confirmation",
        f"Payment confirmed — {r}",
        f"Your subscription renewal",
        f"Order {r} — ready for collection",
        f"Return processed — {r}",
    ]

    transactional_bodies = [
        f"Hi,\n\nYour order {r} from {b} has been dispatched and is on its way.\n\nOrder total: {amt}\nExpected delivery: {d}\n\nTrack your order: [tracking link]\n\n",
        f"Hi,\n\nThanks for your booking with {b}. Here are your details:\n\nBooking ref: {r}\nDate: {d}\nTotal charged: {amt}\n\n",
        f"Hi,\n\nYour payment of {amt} has been received. Your receipt number is {r}.\n\nThank you for shopping with {b}.\n\n",
        f"Hi,\n\nYour order {r} is ready for collection at your selected {b} store. Bring this email or your order number.\n\n",
        f"Hi,\n\nWe've processed your return {r}. A refund of {amt} will appear in your account within 5 business days.\n\n",
    ]

    promo_bodies = [
        f"──────────────────────\nWhile we have your attention — members get {disc} off sitewide this {d}. Shop the sale: [link]\n──────────────────────\n\n",
        f"──────────────────────\nAs a thank you for your order, here's {disc} off your next purchase. Use code at checkout: [link]\n──────────────────────\n\n",
        f"──────────────────────\nDon't miss our {d} sale — up to {disc} off selected items. Shop now: [link]\n──────────────────────\n\n",
        f"──────────────────────\nYou might also like these new arrivals. Save {disc} this week only: [link]\n──────────────────────\n\n",
        f"──────────────────────\nComplete your collection — {disc} off matching items. Limited stock. Shop: [link]\n──────────────────────\n\n",
    ]

    footers = [
        f"{unsub_email()}\n{b} | {address()}",
        f"{address()}\n\n{unsub_email()}",
        f"{b} Pty Ltd | {address()}\n{unsub_email()}",
    ]

    subject = random.choice(transactional_subjects)
    body = random.choice(transactional_bodies) + random.choice(promo_bodies) + random.choice(footers)
    return subject, body


def email_marketing():
    b = brand()
    disc = discount()
    d = date()
    amt = amount()

    subjects = [
        f"{disc} off everything at {b} — today only",
        f"Your exclusive {b} offer inside",
        f"New arrivals at {b} — shop the latest",
        f"{b} sale starts {d}: up to {disc} off",
        f"Members only: {disc} off at {b}",
        f"Don't miss the {b} weekend sale",
        f"You've earned a {b} reward",
        f"Back in stock at {b}",
        f"{b}: Last chance — sale ends {d}",
        f"We miss you — here's {disc} off at {b}",
    ]

    bodies = [
        f"Hi,\n\nShop the {b} {d} sale and save {disc} on selected items. This offer ends at midnight.\n\nShop now: [link]\n\n{unsub_email()}\n{b} | {address()}",
        f"Hi,\n\nAs a valued {b} member, you have access to our exclusive {disc} off event. Valid {d} only.\n\nClaim your discount: [link]\n\n{unsub_email()}\n{b} | {address()}",
        f"Hi,\n\nNew arrivals are here at {b}. Plus, spend {amt} or more and save {disc} — {d} only.\n\nShop new arrivals: [link]\n\n{unsub_email()}\n{b} | {address()}",
        f"Hi,\n\nWe've got something for you: {disc} off your next purchase at {b}. No minimum spend.\n\nShop now: [link]\n\nOffer expires {d}.\n\n{unsub_email()}\n{b} | {address()}",
        f"Hi,\n\nIt's been a while! To welcome you back, here's {disc} off at {b}. Valid until {d}.\n\nGet your discount: [link]\n\n{unsub_email()}\n{b} | {address()}",
    ]

    return random.choice(subjects), random.choice(bodies)


def email_transactional():
    b = brand()
    r = ref()
    amt = amount()
    d = date()
    t = time_()

    subjects = [
        f"Your order {r} has been confirmed",
        f"Order {r} is on its way",
        f"Your {b} booking is confirmed",
        f"Receipt from {b} — {r}",
        f"Delivery update for your {b} order",
        f"Your {b} appointment: {d} at {t}",
        f"Your {b} account — password changed",
        f"Your {b} subscription renewal",
        f"Refund processed — {r}",
        f"Your {b} order is ready for collection",
    ]

    bodies = [
        f"Hi,\n\nYour order {r} from {b} has been confirmed.\n\nOrder total: {amt}\nExpected delivery: {d}\n\nTrack your order: [link]\n\n{b} | {address()}",
        f"Hi,\n\nGreat news — your {b} order {r} has been dispatched and is on its way to you.\n\nEstimated arrival: {d}\n\nTrack: [link]\n\n{b} | {address()}",
        f"Hi,\n\nYour booking with {b} is confirmed.\n\nDate: {d}\nTime: {t}\nRef: {r}\nTotal: {amt}\n\nNeed to change anything? Contact us: [link]\n\n{b} | {address()}",
        f"Hi,\n\nThanks for shopping with {b}. Here's your receipt.\n\nRef: {r}\nAmount: {amt}\nDate: {d}\n\nView your order: [link]\n\n{b} | {address()}",
        f"Hi,\n\nYour {b} password was changed on {d} at {t}. If this wasn't you, please contact us immediately.\n\n{b} | {address()}",
    ]

    return random.choice(subjects), random.choice(bodies)


def email_unclear():
    b = brand()
    d = date()

    subjects = [
        f"An update from {b}",
        f"Important information about your {b} account",
        f"Your {b} summary",
        f"A note from {b}",
        f"Changes to your {b} plan",
    ]

    bodies = [
        f"Hi,\n\nWe wanted to let you know about some changes at {b}. Please review the details here: [link]\n\n{b} | {address()}",
        f"Hi,\n\nYour {b} account summary for {d} is ready. View it here: [link]\n\n{b} | {address()}",
        f"Hi,\n\nThere's been an update to your {b} preferences. If you have questions, reply to this email.\n\n{b} | {address()}",
    ]

    return random.choice(subjects), random.choice(bodies)


# ── Generation ───────────────────────────────────────────────────────────────

SMS_GENERATORS = {
    "marketing":                   sms_marketing,
    "transactional":               sms_transactional,
    "transactional_with_promotion": sms_transactional_with_promotion,
    "unclear":                     sms_unclear,
}

EMAIL_GENERATORS = {
    "marketing":                   email_marketing,
    "transactional":               email_transactional,
    "transactional_with_promotion": email_transactional_with_promotion,
    "unclear":                     email_unclear,
}


def fingerprint(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def load_existing_fps():
    if not OUTPUT_FILE.exists():
        return set()
    fps = set()
    with open(OUTPUT_FILE, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                e = json.loads(line)
                if e.get("source", "").startswith("template:"):
                    fps.add(e["id"].split(":")[-1])
            except (json.JSONDecodeError, KeyError):
                continue
    return fps


def make_entry(channel, label, subject, body):
    fp = fingerprint(f"{label}|{subject}|{body}")
    return {
        "id": f"template:{channel}:{label}:{fp}",
        "subject": subject,
        "sender": "",
        "channel": channel,
        "body_snippet": body[:500],
        "body": body,
        "draft_label": label,
        "human_label": label,
        "source": f"template:{channel}",
        "original_label": label,
    }, fp


def generate(channel, label, count, existing_fps, dry_run=False):
    generators = SMS_GENERATORS if channel == "sms" else EMAIL_GENERATORS
    gen = generators.get(label)
    if gen is None:
        print(f"  No template for {channel}/{label}")
        return []

    entries = []
    attempts = 0
    max_attempts = count * 10

    while len(entries) < count and attempts < max_attempts:
        attempts += 1
        result = gen()
        if isinstance(result, tuple):
            subject, body = result
        else:
            subject, body = "", result

        entry, fp = make_entry(channel, label, subject, body)
        if fp in existing_fps:
            continue
        existing_fps.add(fp)
        if not dry_run:
            entries.append(entry)
        else:
            entries.append(None)  # count only

    if len(entries) < count:
        print(f"  Warning: only generated {len(entries)}/{count} unique entries (template variety exhausted).")
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", choices=VALID_CHANNELS, default=None,
                        help="Channel to generate (default: both)")
    parser.add_argument("--label", choices=VALID_LABELS, default=None,
                        help="Label to generate (default: all labels)")
    parser.add_argument("--count", type=int, default=None,
                        help="Total examples. Default: 100000 SMS + 5000 email transactional_with_promotion")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    existing_fps = load_existing_fps()
    total_written = 0

    # Build work list
    tasks = []
    if args.channel and args.label and args.count:
        tasks = [(args.channel, args.label, args.count)]
    elif args.channel and args.label:
        tasks = [(args.channel, args.label, 25000)]
    elif args.channel == "sms" or args.channel is None:
        per = (args.count or 100000) // 4
        for lbl in VALID_LABELS:
            tasks.append(("sms", lbl, per))
    if args.channel == "email" or args.channel is None:
        # Top up thin email classes
        tasks.append(("email", "transactional_with_promotion", args.count or 5000))

    with open(OUTPUT_FILE, "a", encoding="utf-8") as fh:
        for channel, label, count in tasks:
            print(f"\nGenerating {count} {channel}/{label}...")
            entries = generate(channel, label, count, existing_fps, dry_run=args.dry_run)
            if not args.dry_run:
                for e in entries:
                    fh.write(json.dumps(e, ensure_ascii=False) + "\n")
            total_written += len(entries)
            print(f"  Done: {len(entries)}")

    print(f"\nTotal written: {total_written}")

    if args.dry_run:
        print("(dry run — nothing written)")
        return

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
    for lbl, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {lbl}: {cnt}")
    print("\nRun: python train.py")


if __name__ == "__main__":
    main()
