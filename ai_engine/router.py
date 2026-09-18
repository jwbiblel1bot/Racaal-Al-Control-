def route_message(message: str) -> str:
    """Basic intent router; more advanced routing comes later."""
    text = message.strip().lower()

    if not text:
        return "empty"

    bible_terms = [
        "bible", "scripture", "verse", "jesus", "jehovah", "god",
        "prayer", "faith", "forgiveness", "christian"
    ]

    if any(term in text for term in bible_terms):
        return "bible"

    return "general"
