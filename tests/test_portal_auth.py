"""
Tests for portal_auth JWT claims parsing, Graph token identification, and session hooking.
Licensed under GNU AGPLv3.
"""

import base64
import json
from unittest.mock import MagicMock
from intune_visual_doc.auth.portal_auth import (
    parse_jwt_claims,
    is_graph_token,
    extract_tokens_from_page,
)


def _make_mock_jwt(claims: dict) -> str:
    h = base64.urlsafe_b64encode(b'{"alg":"none"}').decode().rstrip("=")
    p = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"{h}.{p}.mocksignature"


def test_parse_jwt_claims_valid():
    """Verify claim decoding and padding resolution."""
    claims = {"aud": "https://graph.microsoft.com", "upn": "admin@contoso.com"}
    token = _make_mock_jwt(claims)
    decoded = parse_jwt_claims(token)
    assert decoded["aud"] == "https://graph.microsoft.com"
    assert decoded["upn"] == "admin@contoso.com"


def test_is_graph_token_detection():
    """Verify identification of Microsoft Graph audience and user extraction."""
    graph_token = _make_mock_jwt({"aud": "https://graph.microsoft.com", "upn": "user@district.org"})
    is_graph, upn = is_graph_token(graph_token)
    assert is_graph
    assert upn == "user@district.org"

    arm_token = _make_mock_jwt({"aud": "https://management.azure.com", "upn": "other@district.org"})
    is_graph, _ = is_graph_token(arm_token)
    assert not is_graph


def test_extract_tokens_from_page():
    """Verify token extraction from evaluated browser session and local storage."""
    mock_page = MagicMock()
    mock_page.evaluate.return_value = [
        "eyJhbGciOiJub25lIn0.eyJhdWQiOiAiaHR0cHM6Ly9ncmFwaC5taWNyb3NvZnQuY29tIiwgInVwbiI6ICJ0ZXN0In0.sig" + ("a" * 100),
    ]
    tokens = extract_tokens_from_page(mock_page)
    assert len(tokens) == 1
    assert "eyJ" in tokens[0]
