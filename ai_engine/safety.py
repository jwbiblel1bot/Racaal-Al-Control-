def validate_input(message: str) -> bool:
    if not isinstance(message, str):
        return False

    message = message.strip()

    if not message:
        return False

    if len(message) > 12000:
        return False

    return True
