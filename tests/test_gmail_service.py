"""Tests for Gmail payload parsing helpers."""

from adzekit.services.gmail import _extract_body


def test_extract_body_decodes_unpadded_base64url():
    payload = {
        "mimeType": "text/plain",
        "body": {"data": "SGVsbG8"},
    }

    assert _extract_body(payload) == "Hello"


def test_extract_body_returns_empty_for_invalid_payload():
    payload = {
        "mimeType": "text/plain",
        "body": {"data": "***not-valid-base64***"},
    }

    assert _extract_body(payload) == ""


def test_extract_body_falls_back_to_nested_parts():
    payload = {
        "mimeType": "multipart/alternative",
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {"data": "TmVzdGVkIGJvZHk"},
            }
        ],
    }

    assert _extract_body(payload) == "Nested body"
