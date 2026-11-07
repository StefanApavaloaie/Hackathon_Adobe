"""Seeds Stripe test mode with cancelled subscribers and creates the offer coupons.

Run from backend/:  .venv/bin/python -m scripts.seed_stripe   (Windows: .\\.venv\\Scripts\\python.exe)

Safe to run more than once: customers whose email already exists are skipped,
and offers that already have a coupon are left alone.
"""

import random
import sys
from datetime import UTC, datetime, timedelta

from stripe import StripeClient

from app.config import get_settings
from app.errors import ServiceNotConfigured
from app.services.email_client import parse_allowlist
from app.services.stripe_client import get_stripe
from app.services.supabase_client import get_supabase

PRODUCT_NAME = "Pro plan"
PRICE_LOOKUP_KEY = "winback_pro_monthly"
PRICE_CENTS = 4900
SIMULATED_COUNT = 200
CHURN_WINDOW_DAYS = 90
TEST_PAYMENT_METHOD = "pm_card_visa"
RANDOM_SEED = 42

STRIPE_FEEDBACK_VALUES = {
    "customer_service",
    "low_quality",
    "missing_features",
    "other",
    "switched_service",
    "too_complex",
    "too_expensive",
    "unused",
}

# (comment, Stripe feedback value). About 50 distinct comments, so the agent
# classifies each one once rather than once per customer.
CANCELLATION_COMMENTS: list[tuple[str, str]] = [
    # Price
    ("Too expensive for a team our size.", "too_expensive"),
    ("We had to cut costs this quarter.", "too_expensive"),
    ("The price went up and our budget didn't.", "too_expensive"),
    ("Can't justify $49 a month for how little we use it.", "too_expensive"),
    ("Our finance team froze all new software spend.", "too_expensive"),
    ("Cheaper tools do most of what we need.", "too_expensive"),
    ("Startup ran low on runway, cutting every subscription.", "too_expensive"),
    ("Would come back if there was a smaller plan.", "too_expensive"),
    ("Paying per month adds up, wanted an annual discount.", "too_expensive"),
    ("Value isn't there at this price point.", "too_expensive"),
    # Missing features
    ("No integration with HubSpot, which we rely on.", "missing_features"),
    ("We needed a proper API for our own dashboards.", "missing_features"),
    ("Missing SSO, so security wouldn't approve it.", "missing_features"),
    ("No mobile app, and the team works on the road.", "missing_features"),
    ("Reporting is too basic; we need custom reports.", "missing_features"),
    ("Can't export data to CSV in the format we need.", "missing_features"),
    ("No multi-language support for our EU customers.", "missing_features"),
    ("We needed role-based permissions for contractors.", "missing_features"),
    ("Waiting for the Slack integration you promised.", "missing_features"),
    ("No way to automate the weekly workflow.", "missing_features"),
    # Switched
    ("Moved to a competitor that bundles this with our CRM.", "switched_service"),
    ("Our parent company standardised on another tool.", "switched_service"),
    ("Switched to an open-source alternative.", "switched_service"),
    ("New manager prefers the tool they used before.", "switched_service"),
    ("Found a tool with better analytics.", "switched_service"),
    ("Consolidating vendors, so we went with an all-in-one suite.", "switched_service"),
    # Unused
    ("Didn't use it enough to keep paying.", "unused"),
    ("Project ended, so we don't need it right now.", "unused"),
    ("Seasonal business, will need it again in spring.", "unused"),
    ("Only one person was using it and they left.", "unused"),
    ("Signed up for a campaign that's now finished.", "unused"),
    ("Forgot we were even subscribed.", "unused"),
    ("Team never really adopted it.", "unused"),
    # Too complex
    ("Too hard to set up without a developer.", "too_complex"),
    ("The interface is confusing for non-technical staff.", "too_complex"),
    ("Onboarding took too long and we gave up.", "too_complex"),
    ("Too many settings; we just wanted something simple.", "too_complex"),
    ("Couldn't figure out how to import our contacts.", "too_complex"),
    # Quality
    ("Too many bugs in the last few releases.", "low_quality"),
    ("The app was slow and kept timing out.", "low_quality"),
    ("Data sync broke twice and we lost work.", "low_quality"),
    ("Emails sent through it kept landing in spam.", "low_quality"),
    ("Outage during our launch week was the last straw.", "low_quality"),
    # Service
    ("Support took a week to reply to a billing issue.", "customer_service"),
    ("Nobody helped when our account was locked.", "customer_service"),
    ("Was charged twice and the refund took ages.", "customer_service"),
    ("Support kept sending us generic help articles.", "customer_service"),
    # Other
    ("Company is shutting down.", "other"),
    ("Merging with another business, will revisit later.", "other"),
    ("Just taking a break for a few months.", "other"),
]

FIRST_NAMES = [
    "Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Avery", "Quinn",
    "Maria", "David", "Aisha", "Wei", "Lukas", "Sofia", "Omar", "Elena", "Kenji", "Priya",
]
LAST_NAMES = [
    "Smith", "Garcia", "Chen", "Novak", "Okafor", "Rossi", "Kim", "Silva", "Müller", "Patel",
    "Popescu", "Johnson", "Nguyen", "Kowalski", "Haddad", "Larsen", "Costa", "Ivanova", "Brown", "Sato",
]


def simulated_customer_specs(count: int, now: datetime, seed: int = RANDOM_SEED) -> list[dict]:
    """Fictional customers. Every comment is used at least once; the rest are random."""
    rng = random.Random(seed)
    pairs = list(CANCELLATION_COMMENTS)
    rng.shuffle(pairs)
    pairs += [rng.choice(CANCELLATION_COMMENTS) for _ in range(count - len(pairs))]
    specs = []
    for number, (comment, feedback) in enumerate(pairs[:count], start=1):
        churned_at = now - timedelta(seconds=rng.uniform(60, CHURN_WINDOW_DAYS * 86400))
        specs.append({
            "email": f"user{number:03d}@example.com",
            "name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
            "comment": comment,
            "feedback": feedback,
            "churned_at": churned_at.isoformat(timespec="seconds"),
            "simulated": True,
        })
    return specs


def live_customer_specs(allowlist: list[str], now: datetime) -> list[dict]:
    """One real team inbox per allow-listed address, churned recently with a common reason."""
    specs = []
    for index, email in enumerate(allowlist):
        comment, feedback = CANCELLATION_COMMENTS[index % len(CANCELLATION_COMMENTS)]
        local = email.split("@")[0].replace(".", " ").replace("_", " ").title()
        specs.append({
            "email": email,
            "name": local,
            "comment": comment,
            "feedback": feedback,
            "churned_at": (now - timedelta(days=7 + index)).isoformat(timespec="seconds"),
            "simulated": False,
        })
    return specs


def new_specs(specs: list[dict], existing_emails: set[str]) -> list[dict]:
    existing = {email.lower() for email in existing_emails}
    return [spec for spec in specs if spec["email"].lower() not in existing]


def offers_needing_coupons(offers: list[dict]) -> list[dict]:
    return [offer for offer in offers if offer["percent_off"] > 0 and not offer.get("stripe_coupon_id")]


def coupon_id_for(offer: dict) -> str:
    """A fixed coupon ID, so a rerun after a database reset finds the existing coupon."""
    return f"winback_{offer['percent_off']}pct_{offer['duration_months']}m"


def coupon_params(offer: dict) -> dict:
    return {
        "id": coupon_id_for(offer),
        "name": offer["label"],
        "percent_off": offer["percent_off"],
        "duration": "repeating",
        "duration_in_months": offer["duration_months"],
    }


# --- Stripe and Supabase calls ---------------------------------------------


def ensure_price(stripe: StripeClient) -> str:
    prices = stripe.v1.prices.list({"lookup_keys": [PRICE_LOOKUP_KEY], "active": True, "limit": 1})
    if prices.data:
        print(f"Price {PRICE_LOOKUP_KEY} exists")
        return prices.data[0].id
    product = stripe.v1.products.create({"name": PRODUCT_NAME})
    price = stripe.v1.prices.create({
        "product": product.id,
        "unit_amount": PRICE_CENTS,
        "currency": "usd",
        "recurring": {"interval": "month"},
        "lookup_key": PRICE_LOOKUP_KEY,
    })
    print(f"Created {PRODUCT_NAME} at ${PRICE_CENTS / 100:.0f}/month")
    return price.id


def existing_customer_emails(stripe: StripeClient) -> set[str]:
    emails = set()
    for customer in stripe.v1.customers.list({"limit": 100}).auto_paging_iter():
        if customer.email:
            emails.add(customer.email.lower())
    return emails


def create_cancelled_subscriber(stripe: StripeClient, spec: dict, price_id: str) -> None:
    metadata = {"simulated": str(spec["simulated"]).lower(), "churned_at": spec["churned_at"]}
    customer = stripe.v1.customers.create({
        "email": spec["email"],
        "name": spec["name"],
        "payment_method": TEST_PAYMENT_METHOD,
        "invoice_settings": {"default_payment_method": TEST_PAYMENT_METHOD},
        "metadata": metadata,
    })
    subscription = stripe.v1.subscriptions.create({
        "customer": customer.id,
        "items": [{"price": price_id}],
        "metadata": metadata,
    })
    stripe.v1.subscriptions.cancel(
        subscription.id,
        {"cancellation_details": {"feedback": spec["feedback"], "comment": spec["comment"]}},
    )


def seed_customers(stripe: StripeClient, price_id: str, specs: list[dict]) -> None:
    todo = new_specs(specs, existing_customer_emails(stripe))
    print(f"{len(specs) - len(todo)} customers already exist, creating {len(todo)}")
    for done, spec in enumerate(todo, start=1):
        create_cancelled_subscriber(stripe, spec, price_id)
        if done % 20 == 0 or done == len(todo):
            print(f"  {done}/{len(todo)}")


def ensure_coupon(stripe: StripeClient, offer: dict) -> str:
    coupon_id = coupon_id_for(offer)
    found = stripe.v1.coupons.list({"limit": 100}).auto_paging_iter()
    if any(coupon.id == coupon_id for coupon in found):
        return coupon_id
    return stripe.v1.coupons.create(coupon_params(offer)).id


def seed_coupons(stripe: StripeClient) -> None:
    db = get_supabase()
    offers = db.table("offers").select("*").execute().data
    if not offers:
        sys.exit("No offers found. Run supabase/seed/offers.sql first.")
    todo = offers_needing_coupons(offers)
    print(f"{len(todo)} offers need a coupon")
    for offer in todo:
        coupon_id = ensure_coupon(stripe, offer)
        db.table("offers").update({"stripe_coupon_id": coupon_id}).eq("id", offer["id"]).execute()
        print(f"  {offer['label']}: {coupon_id}")


def main() -> None:
    settings = get_settings()
    stripe = get_stripe()  # Refuses anything but an sk_test_ key, via Settings.
    get_supabase()  # Fail before touching Stripe if Supabase isn't configured.
    allowlist = parse_allowlist(settings.recipient_allowlist)
    if not allowlist:
        print("Warning: RECIPIENT_ALLOWLIST is empty, so no live customers will be created.")

    now = datetime.now(UTC)
    price_id = ensure_price(stripe)
    seed_customers(
        stripe,
        price_id,
        simulated_customer_specs(SIMULATED_COUNT, now) + live_customer_specs(allowlist, now),
    )
    seed_coupons(stripe)
    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except ServiceNotConfigured as exc:
        sys.exit(f"{exc}. Fill in backend/.env first.")
