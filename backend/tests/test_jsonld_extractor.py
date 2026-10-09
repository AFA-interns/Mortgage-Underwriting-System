"""Tests for JSON-LD and structured data extraction."""

import pytest
from bs4 import BeautifulSoup

from property_data.scrapers.jsonld_extractor import (
    extract_jsonld,
    extract_next_data,
    extract_from_all_sources,
)


class TestExtractJsonLd:
    """Tests for extract_jsonld function."""

    def test_extract_simple_jsonld(self):
        """Extract a single JSON-LD block."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "Test Property"}
        </script>
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        results = extract_jsonld(soup)

        assert len(results) == 1
        assert results[0]["@type"] == "Product"
        assert results[0]["name"] == "Test Property"

    def test_extract_multiple_jsonld_blocks(self):
        """Extract multiple JSON-LD blocks."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"@type": "Product", "name": "Property 1"}
        </script>
        <script type="application/ld+json">
        {"@type": "Product", "name": "Property 2"}
        </script>
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        results = extract_jsonld(soup)

        assert len(results) == 2
        assert results[0]["name"] == "Property 1"
        assert results[1]["name"] == "Property 2"

    def test_extract_empty_jsonld(self):
        """Handle empty JSON-LD blocks gracefully."""
        html = """
        <html><head>
        <script type="application/ld+json"></script>
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        results = extract_jsonld(soup)

        assert len(results) == 0

    def test_extract_invalid_json(self):
        """Handle invalid JSON gracefully."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {invalid json content}
        </script>
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        results = extract_jsonld(soup)

        assert len(results) == 0

    def test_extract_concatenated_json(self):
        """Handle concatenated JSON objects."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"name": "Property 1"}{"name": "Property 2"}
        </script>
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        results = extract_jsonld(soup)

        assert len(results) == 2


class TestExtractNextData:
    """Tests for extract_next_data function."""

    def test_extract_next_data(self):
        """Extract __NEXT_DATA__ JSON."""
        html = """
        <html><head>
        <script id="__NEXT_DATA__">
        {"props": {"pageProps": {"property": {"name": "Test"}}}}
        </script>
        </head><body></body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        result = extract_next_data(soup)

        assert result is not None
        assert result["props"]["pageProps"]["property"]["name"] == "Test"

    def test_extract_next_data_missing(self):
        """Return None when __NEXT_DATA__ is not present."""
        html = "<html><head></head><body></body></html>"
        soup = BeautifulSoup(html, "lxml")
        result = extract_next_data(soup)

        assert result is None


class TestExtractFromAllSources:
    """Tests for extract_from_all_sources function."""

    def test_merge_jsonld_and_next_data(self):
        """Merge data from JSON-LD and __NEXT_DATA__."""
        html = """
        <html><head>
        <script type="application/ld+json">
        {"address": {"addressLocality": "Whitefield"}}
        </script>
        <script id="__NEXT_DATA__">
        {"props": {"pageProps": {"price": 12000000}}}
        </script>
        </head><body></body></html>
        """
        result = extract_from_all_sources(html)

        assert "address" in result
        assert result["address"]["addressLocality"] == "Whitefield"
        assert "props" in result
        assert result["props"]["pageProps"]["price"] == 12000000

    def test_empty_html(self):
        """Handle empty HTML gracefully."""
        result = extract_from_all_sources("<html></html>")

        assert result == {}
