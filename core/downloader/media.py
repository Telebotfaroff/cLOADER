"""Helpers for media-oriented downloads.

Provider-specific extraction (for example, supported video platforms) will be
implemented separately. This module currently provides conservative filename
helpers so the core HTTP downloader stays provider-agnostic.
"""

from pathlib import Path
from urllib.parse import unquote, urlparse


def filename_from_url(url: str, fallback: str = "download") -> str:
    """Extract a reasonable filename from a URL path."""
    path_name = Path(unquote(urlparse(url).path)).name
    return path_name or fallback
