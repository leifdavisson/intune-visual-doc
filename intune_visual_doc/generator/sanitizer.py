"""
Secret and sensitive information sanitizer.
Masks credentials, pre-shared keys, and sensitive tokens unless explicitly bypassed.
Licensed under GNU AGPLv3.
"""

import re
from typing import Any, Dict, List, Union

# Keys that represent sensitive credentials
SENSITIVE_KEY_PATTERNS = [
    r"presharedkey",
    r"privatekey",
    r"apikey",
    r"wifikey",
    r"radiussecret",
    r"clientsecret",
    r"sharedsecret",
    r"appsecret",
    r"accountpassword",
    r"adminpassword",
    r"userpassword",
    r"rootpassword",
    r"proxypassword",
    r"^password$",
    r"^secret$",
    r"^token$",
    r"^passphrase$",
    r"^credential$",
]

SECRET_REGEX = re.compile("|".join(SENSITIVE_KEY_PATTERNS), re.IGNORECASE)

# Structural and schema keys that must never be treated as credentials
STRUCTURAL_KEYS = {
    "id",
    "groupid",
    "sourceid",
    "settingdefinitionid",
    "definitionid",
    "settinginstancetemplateid",
    "settingvaluetemplateid",
    "templateid",
    "displayname",
    "name",
    "description",
    "category",
    "category_label",
    "platform",
    "platforms",
    "technologies",
    "version",
    "@odata.type",
    "@odata.context",
    "rolescopetagids",
    "deviceandappmanagementassignmentfilterid",
    "deviceandappmanagementassignmentfiltertype",
    "source",
    "type",
}

# Policy schema parameter suffixes that must never be masked as secrets
POLICY_METADATA_SUFFIXES = (
    "type",
    "required",
    "length",
    "days",
    "age",
    "count",
    "history",
    "minutes",
    "blocksimple",
    "complexity",
    "expiration",
    "enabled",
    "format",
    "rule",
    "definition",
    "definitionid",
    "id",
    "state",
    "scope",
    "tag",
    "ranges",
    "quality",
    "status",
    "method",
    "mode",
)

GUID_REGEX = re.compile(
    r"^\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?$"
)


def _is_secret_key(key: str) -> bool:
    """Check if key represents a credential rather than schema metadata."""
    k_lower = key.lower()
    if k_lower in STRUCTURAL_KEYS or k_lower.endswith("id"):
        return False
    if any(k_lower.endswith(s) for s in POLICY_METADATA_SUFFIXES):
        return False
    return bool(SECRET_REGEX.search(key))


def _is_structural_value(value: str) -> bool:
    """Check if value is an identifier, setting definition, URL, or GUID."""
    if GUID_REGEX.match(value):
        return True
    if value.startswith(("device_vendor_msft_", "user_vendor_msft_", "#microsoft.graph.", "http://", "https://")):
        return True
    return False


def sanitize_value(key: str, value: Any, unsanitize: bool = False) -> Any:
    """
    Mask sensitive values if the setting key indicates a credential or secret.
    If unsanitize is True, returns original value unmodified.
    Preserves schema identifiers, GUIDs, and Settings Catalog definition IDs.
    """
    if unsanitize or value is None:
        return value

    if isinstance(value, str):
        if _is_secret_key(key):
            return "[MASKED: ********]"

        k_lower = key.lower()
        if (
            len(value) > 30
            and k_lower not in STRUCTURAL_KEYS
            and not k_lower.endswith("id")
            and not any(k_lower.endswith(s) for s in POLICY_METADATA_SUFFIXES)
            and not _is_structural_value(value)
            and re.match(r"^[A-Za-z0-9+/=_-]{30,}$", value)
        ):
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
