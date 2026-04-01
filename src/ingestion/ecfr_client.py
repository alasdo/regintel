from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import httpx

ECFR_BASE = "https://www.ecfr.gov/api/versioner/v1/full"
CACHE_DIR = Path("data/ecfr_cache")


def fetch_part_xml(title: int, part: int, as_of_date: date) -> bytes:
    """
    Fetch full XML for a CFR part from the eCFR API and cache it locally.

    The eCFR versioner does not always expose every calendar day as an
    available snapshot. To make the client more robust, this function tries
    the requested date first, then falls back a few days if necessary.

    Args:
        title: CFR title number, e.g. 21
        part: CFR part number, e.g. 211
        as_of_date: Requested version date

    Returns:
        Raw XML bytes for the requested part.

    Raises:
        RuntimeError: If no XML could be retrieved for the requested part
            after trying the fallback dates.
        httpx.HTTPError: For non-404 HTTP failures.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Try the requested date first, then a small fallback window.
    dates_to_try = [as_of_date - timedelta(days=i) for i in range(7)]

    last_error: Exception | None = None

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        for candidate_date in dates_to_try:
            cache_file = CACHE_DIR / (
                f"title-{title}_part-{part}_{candidate_date.isoformat()}.xml"
            )

            if cache_file.exists():
                return cache_file.read_bytes()

            url = f"{ECFR_BASE}/{candidate_date.isoformat()}/title-{title}.xml"
            params = {"part": str(part)}

            try:
                response = client.get(url, params=params)
                response.raise_for_status()

                content = response.content
                if not content.strip():
                    continue

                cache_file.write_bytes(content)
                return content

            except httpx.HTTPStatusError as exc:
                last_error = exc

                # 404 is expected sometimes when the exact snapshot date
                # is unavailable. Keep trying earlier dates.
                if exc.response.status_code == 404:
                    continue

                # For other HTTP errors, fail immediately.
                raise

            except httpx.HTTPError as exc:
                last_error = exc
                raise

    tried = ", ".join(d.isoformat() for d in dates_to_try)
    raise RuntimeError(
        f"Could not fetch XML for title={title}, part={part}. "
        f"Tried dates: {tried}. Last error: {last_error}"
    )