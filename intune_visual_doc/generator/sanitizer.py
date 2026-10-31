"""
Secret and sensitive information sanitizer.
Masks credentials, pre-shared keys, and sensitive tokens unless explicitly bypassed.
"""

import re
from typing import Any, Dict, List, Union

SENSITIVE_KEY_PATTERNS = [
    r"password",
    r"presharedkey",
    r"secret",
    r"privatekey",
    r"apikey",
    r"token",
    r"passphrase",
    r"credential",
    r"wifikey",
    r"radiussecret",
]

SECRET_REGEX = re.compile("|".join(SENSITIVE_KEY_PATTERNS), re.IGNORECASE)


def sanitize_value(key: str, value: Any, unsanitize: bool = False) -> Any:
    """
    Mask sensitive values if the setting key indicates a credential or secret.
    If unsanitize is True, returns original value unmodified.
    """
    if unsanitize or value is None:
        return value

    if isinstance(value, str):
        if SECRET_REGEX.search(key):
            return "[MASKED: ********]"
        # Mask long hex or base64 tokens that look like keys
        if len(value) > 30 and re.match(r"^[A-Za-z0-9+/=_-]{30,}$", value):
            return f"[MASKED: {value[:4]}...{value[-4:]}]"

    elif isinstance(value, dict):
        return {k: sanitize_value(k, v, unsanitize) for k, v in value.items()}
    elif isinstance(value, list):
        return [sanitize_value(key, item, unsanitize) for item in value]

    return value


def sanitize_settings_list(settings: List[Dict[str, Any]], unsanitize: bool = False) -> List[Dict[str, Any]]:
    """Sanitize all entries in a list of setting dicts."""
    cleaned = []
    for s in settings:
        k = s.get("name", "")
        v = s.get("value")
        cleaned.append({
            **s,
            "value": sanitize_value(k, v, unsanitize),
        })
    return cleaned
