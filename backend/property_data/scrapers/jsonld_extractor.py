"""
JSON-LD and structured data extractor.

Many property websites embed structured data in <script> tags.
This module extracts that data — it often contains complete
information even when the visible HTML shows NULLs.
"""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup


def extract_jsonld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    """Extract all JSON-LD script blocks from a page."""
    results: list[dict[str, Any]] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        text = script.string or script.get_text() or ""
        text = text.strip()
        if not text:
            continue

        # Sometimes multiple JSON objects are concatenated
        for chunk in _split_json_objects(text):
            try:
                data = json.loads(chunk)
                if isinstance(data, dict):
                    results.append(data)
                elif isinstance(data, list):
                    results.extend(
                        item for item in data if isinstance(item, dict)
                    )
            except (json.JSONDecodeError, ValueError):
                continue

    return results


def extract_next_data(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Extract __NEXT_DATA__ JSON from Next.js pages."""
    for script in soup.find_all("script", id="__NEXT_DATA__"):
        text = script.string or script.get_text() or ""
        text = text.strip()
        if not text:
            continue
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            continue
    return None


def extract_nuxt_data(soup: BeautifulSoup) -> dict[str, Any] | None:
    """Extract __NUXT__ data from Nuxt.js pages."""
    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        if "window.__NUXT__" in text:
            match = re.search(
                r"window\.__NUXT__\s*=\s*(\{.*?\})\s*;?\s*$",
                text,
                re.DOTALL,
            )
            if match:
                try:
                    # Nuxt uses a custom format, try JSON first
                    data = json.loads(match.group(1))
                    if isinstance(data, dict):
                        return data
                except (json.JSONDecodeError, ValueError):
                    pass
    return None


def extract_from_all_sources(
    html: str,
) -> dict[str, Any]:
    """
    Extract structured data from all known sources.

    Returns a merged dict with all found fields.
    """
    soup = BeautifulSoup(html, "lxml")

    merged: dict[str, Any] = {}

    # 1. JSON-LD blocks
    for block in extract_jsonld(soup):
        _deep_merge(merged, block)

    # 2. __NEXT_DATA__
    next_data = extract_next_data(soup)
    if next_data:
        _deep_merge(merged, next_data)

    # 3. __NUXT__
    nuxt_data = extract_nuxt_data(soup)
    if nuxt_data:
        _deep_merge(merged, nuxt_data)

    return merged


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> None:
    """Recursively merge overlay into base."""
    for key, value in overlay.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _split_json_objects(text: str) -> list[str]:
    """Split concatenated JSON objects."""
    chunks: list[str] = []
    depth = 0
    start = -1

    for i, char in enumerate(text):
        if char == "{":
            if depth == 0:
                start = i
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                chunks.append(text[start : i + 1])
                start = -1

    return chunks if chunks else [text]
