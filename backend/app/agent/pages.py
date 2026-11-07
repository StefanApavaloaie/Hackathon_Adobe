from app.contracts import PageContent

# Instrucțiunile adăugate automat în promptul din strategy.py
PAGE_INSTRUCTIONS = (
    "Address this cohort's actual reasons for cancelling, using their sample comments. "
    "Keep each text field short, direct, and engaging. "
    "NEVER mention prices, discounts, amounts, or percentages (do not use '%' or '$'), "
    "because the backend code will automatically inject the specific offer details later."
)

def fallback_page_content(cohort_label: str, cancel_feedback: str | None) -> PageContent:
    """Returns template copy tailored to the Stripe cancellation reason, used if LLM fails."""
    
    # Default generic fallback
    headline = "Welcome back"
    subheadline = f"We missed you, {cohort_label}."
    reasons = [{"title": "Continuous Improvement", "body": "We are always updating our product based on feedback."}]
    objection_response = "Give us another try. We've improved."
    cta_label = "Claim Your Offer"

    # Tailor based on standard Stripe cancel_feedback reasons
    if cancel_feedback == "too_expensive":
        headline = "More value, less cost"
        subheadline = "We've rethought our pricing to better fit your budget."
        reasons = [{"title": "Better ROI", "body": "Get all the premium features at a fraction of the cost."}]
        objection_response = "We know budget matters. That's why we have a special offer for you."
    elif cancel_feedback == "missing_features":
        headline = "We've been building"
        subheadline = "Check out the new features we added since you left."
        reasons = [{"title": "New Capabilities", "body": "We shipped the tools you were looking for."}]
        objection_response = "Our product grows with your needs."
    elif cancel_feedback == "switched_service":
        headline = "Come back to the best"
        subheadline = "See why customers prefer us over the competition."
        reasons = [{"title": "Superior Workflow", "body": "Everything you need in one unified, seamless platform."}]
        objection_response = "Switching back is easy and totally worth it."
        cta_label = "Switch Back Today"
    elif cancel_feedback == "unused":
        headline = "Get more done, effortlessly"
        subheadline = "We've made it easier than ever to get started and see value."
        reasons = [{"title": "Quick Start", "body": "New templates and guides to help you launch in minutes."}]
        objection_response = "Don't let powerful tools sit idle."
    elif cancel_feedback == "too_complex":
        headline = "Simpler and faster"
        subheadline = "We redesigned our interface for absolute ease of use."
        reasons = [{"title": "Intuitive Design", "body": "A cleaner UI that gets out of your way."}]
        objection_response = "You don't need a manual to use our platform."
    elif cancel_feedback == "low_quality":
        headline = "Quality you can trust"
        subheadline = "We've overhauled our core engine for maximum reliability."
        reasons = [{"title": "Rock Solid", "body": "Lightning-fast performance and incredible uptime."}]
        objection_response = "Experience the difference of our new architecture."
    elif cancel_feedback == "customer_service":
        headline = "We are here for you"
        subheadline = "Experience our revamped priority support."
        reasons = [{"title": "Priority Routing", "body": "Get answers in minutes, not days."}]
        objection_response = "Our new support team is ready and waiting to help."
    
    return PageContent(
        headline=headline,
        subheadline=subheadline,
        reasons=reasons,
        objection_response=objection_response,
        cta_label=cta_label
    )