"""Gmail adapter: preflight validation for the inbox-triage skill family.

The inbox-triage skill already does the actual Gmail work (fetch metadata,
classify, draft replies, batch-modify). This adapter exists to:

  1. Validate that gcloud auth is set up (the precondition for everything else).
  2. Surface whether the expected AdzeKit labels exist and cache their IDs.
  3. Be the canonical place to put Gmail-related config in the future
     (custom label sets, sender-elevation rules, signature templates).

The adapter is "stateless" today — install reports + caches; uninstall is
a no-op since there are no files to remove. Status answers "could the
inbox-triage skill run right now?"
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from adzekit.config import Settings, get_settings
from adzekit.modules.google_auth import (
    GoogleAuthError,
    gcloud_available,
    get_access_token,
)

GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

# Labels the inbox-triage skill expects to find.
EXPECTED_LABELS = ("AdzeKit/ActionRequired", "AdzeKit/Urgent")


def _gmail_get(path: str, token: str) -> dict[str, Any]:
    """Perform an authenticated GET against the Gmail REST API."""
    req = urllib.request.Request(
        f"{GMAIL_API_BASE}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def list_labels(token: str) -> list[dict[str, str]]:
    """Return the user's Gmail labels as [{id, name, type}, ...]."""
    payload = _gmail_get("/labels", token)
    return [
        {"id": lbl["id"], "name": lbl["name"], "type": lbl.get("type", "user")}
        for lbl in payload.get("labels", [])
    ]


def install_gmail(settings: Settings | None = None) -> dict[str, Any]:
    """Verify gcloud auth + Gmail API access + check for expected labels."""
    settings = settings or get_settings()
    try:
        token = get_access_token()
    except GoogleAuthError as exc:
        return {
            "adapter": "gmail",
            "installed": False,
            "reason": str(exc),
        }
    try:
        labels = list_labels(token)
    except urllib.error.HTTPError as exc:
        return {
            "adapter": "gmail",
            "installed": False,
            "reason": f"Gmail API returned HTTP {exc.code}: {exc.reason}",
        }
    except urllib.error.URLError as exc:
        return {
            "adapter": "gmail",
            "installed": False,
            "reason": f"Gmail API unreachable: {exc.reason}",
        }

    label_names = {lbl["name"] for lbl in labels}
    missing = [name for name in EXPECTED_LABELS if name not in label_names]
    label_id_map = {lbl["name"]: lbl["id"] for lbl in labels if lbl["name"] in EXPECTED_LABELS}

    # Cache the label-name → id map so the inbox-triage skill doesn't
    # have to refetch it. Lives under drafts/.gateway/ for symmetry with
    # the gateway's session DB (also gitignored).
    cache_dir = settings.drafts_dir / ".adapters"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "gmail-labels.json"
    cache_path.write_text(
        json.dumps({"labels": label_id_map, "missing": missing}, indent=2),
        encoding="utf-8",
    )

    return {
        "adapter": "gmail",
        "installed": True,
        "labels_total": len(labels),
        "expected_labels_found": len(EXPECTED_LABELS) - len(missing),
        "missing_labels": missing,
        "cache_path": str(cache_path),
    }


def status_gmail(settings: Settings | None = None) -> dict[str, Any]:
    """Report whether Gmail is usable right now."""
    settings = settings or get_settings()
    if not gcloud_available():
        return {
            "adapter": "gmail",
            "ready": False,
            "reason": "gcloud not on PATH",
        }
    try:
        token = get_access_token()
    except GoogleAuthError as exc:
        return {
            "adapter": "gmail",
            "ready": False,
            "reason": str(exc),
        }
    cache_path = settings.drafts_dir / ".adapters" / "gmail-labels.json"
    cached: dict[str, Any] = {}
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cached = {}
    return {
        "adapter": "gmail",
        "ready": True,
        "token_present": bool(token),
        "cache_present": cache_path.exists(),
        "cached_labels": cached.get("labels", {}),
        "missing_labels": cached.get("missing", list(EXPECTED_LABELS)),
    }


def uninstall_gmail(settings: Settings | None = None) -> dict[str, Any]:
    """Remove the cached label map. gcloud auth is left intact."""
    settings = settings or get_settings()
    cache_path = settings.drafts_dir / ".adapters" / "gmail-labels.json"
    removed = False
    if cache_path.exists():
        cache_path.unlink()
        removed = True
    return {
        "adapter": "gmail",
        "removed_cache": removed,
        "note": "gcloud auth was not touched; run `gcloud auth application-default revoke` separately if desired.",
    }
