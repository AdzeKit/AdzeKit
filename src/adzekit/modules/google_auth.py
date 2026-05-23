"""Shared Google Cloud auth helper.

Both the Gmail and Calendar adapters use `gcloud auth application-default
print-access-token` to obtain OAuth access tokens. This module centralizes
that subprocess call so:

  - Error handling is consistent (one GoogleAuthError class, one message
    pointing at the install hint)
  - Tests can monkeypatch one function instead of every adapter
  - A future replacement (e.g., a direct google-auth-oauthlib flow) only
    changes one file
"""

from __future__ import annotations

import shutil
import subprocess


class GoogleAuthError(RuntimeError):
    """Raised when `gcloud` is missing, unauthenticated, or returns an error."""


def get_access_token(*, timeout_s: float = 10.0) -> str:
    """Run `gcloud auth application-default print-access-token` and return the token.

    Raises GoogleAuthError with a useful message when:
      - gcloud is not on PATH
      - gcloud returns a non-zero exit code
      - the subprocess times out
    """
    if not shutil.which("gcloud"):
        raise GoogleAuthError(
            "gcloud CLI is not on PATH. Install the Google Cloud SDK "
            "(https://cloud.google.com/sdk/docs/install) and run "
            "`gcloud auth application-default login` once."
        )
    try:
        result = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired as exc:
        raise GoogleAuthError(
            f"gcloud did not respond within {timeout_s}s"
        ) from exc

    if result.returncode != 0:
        stderr_text = result.stderr.strip()
        raise GoogleAuthError(
            f"gcloud auth failed (rc={result.returncode}): "
            f"{stderr_text or '(no stderr)'}. "
            "Try `gcloud auth application-default login` to refresh."
        )

    token = result.stdout.strip()
    if not token:
        raise GoogleAuthError(
            "gcloud returned an empty token. "
            "Try `gcloud auth application-default login` to re-authenticate."
        )
    return token


def gcloud_available() -> bool:
    """Cheap check: is gcloud on PATH?"""
    return shutil.which("gcloud") is not None
