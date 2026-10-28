"""Password policy.

Length is the single biggest factor in password strength, so the floor is 10
rather than the common 8. The rest rejects the handful of patterns that make a
long password weak anyway: a single repeated character, a pure number, and
passwords built from the user's own email address.

Deliberately *not* required: forced mixed case, digits and symbols. Composition
rules push people toward predictable substitutions and are no longer
recommended by NIST.
"""

from __future__ import annotations

import re

from app.errors import WeakPassword

# Short blocklist of passwords that appear at the very top of every breach
# corpus. Not a substitute for a full list, and said so in the docs.
COMMON = {
    "password", "password1", "password123", "123456", "12345678", "123456789",
    "1234567890", "qwerty", "qwerty123", "abc123", "letmein", "welcome",
    "admin", "administrator", "iloveyou", "monkey", "dragon", "football",
    "baseball", "sunshine", "princess", "passw0rd", "trustno1", "changeme",
    "secret", "default", "login", "test1234", "projectrevive",
}


def validate_password(password: str, *, email: str, minimum: int) -> None:
    """Raise WeakPassword with a specific, actionable reason."""
    if len(password) < minimum:
        raise WeakPassword(
            f"Use at least {minimum} characters. Length matters more than "
            "symbols, so a short phrase you can remember works well."
        )

    if password.lower() in COMMON:
        raise WeakPassword(
            "That is one of the most commonly used passwords, so it is among "
            "the first any attacker tries. Choose something else."
        )

    if len(set(password)) < 5:
        raise WeakPassword(
            "That password repeats too few distinct characters. Mix in more."
        )

    if password.isdigit():
        raise WeakPassword(
            "A password made only of digits is quick to guess. Add words."
        )

    local_part = email.split("@", 1)[0].lower()
    if len(local_part) >= 4 and local_part in password.lower():
        raise WeakPassword(
            "That password contains your email address, which is the first "
            "thing anyone would try. Choose something unrelated to it."
        )

    if re.fullmatch(r"(.+?)\1+", password):
        raise WeakPassword(
            "That password is a short sequence repeated. Choose something less "
            "predictable."
        )
