"""Email validator module.

Provides email validation using only Python stdlib, no regex.
"""

# Character sets for validation
LOCAL_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._%-+")
DOMAIN_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")


def validate_email(email: str) -> bool:
    """Validate email address according to specified rules.

    Args:
        email: The email address to validate.

    Returns:
        True if valid, False otherwise.
    """
    # Rule 1: Exactly one @ symbol
    if email.count("@") != 1:
        return False

    # Rule 2: Split into local and domain parts
    local, domain = email.split("@", 1)

    # Rule 3: Local part must be 1-64 characters
    if not (1 <= len(local) <= 64):
        return False

    # Rule 4: Domain part must be 1-255 characters
    if not (1 <= len(domain) <= 255):
        return False

    # Rule 5: Domain must contain at least one dot
    if "." not in domain:
        return False

    # Rule 6: No consecutive dots anywhere
    if ".." in email:
        return False

    # Rule 7: No leading dot in local part
    if local.startswith("."):
        return False

    # Rule 8: No trailing dot in local part
    if local.endswith("."):
        return False

    # Rule 9: No leading dot in domain part
    if domain.startswith("."):
        return False

    # Rule 10: No trailing dot in domain part
    if domain.endswith("."):
        return False

    # Rule 11: Only allowed characters
    if not all(c in LOCAL_ALLOWED for c in local):
        return False

    if not all(c in DOMAIN_ALLOWED for c in domain):
        return False

    return True
