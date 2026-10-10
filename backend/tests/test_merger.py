"""Tests for multi-source data merger."""

import pytest

from property_data.scrapers.merger import merge_sources, merge_two_listings, _is_empty


class TestIsEmpty:
    """Tests for _is_empty helper."""

    def test_none_is_empty(self):
        assert _is_empty(None) is True

    def test_empty_string_is_empty(self):
        assert _is_empty("") is True

    def test_whitespace_string_is_empty(self):
        assert _is_empty("   ") is True

    def test_zero_is_empty(self):
        assert _is_empty(0) is True

    def test_valid_value_not_empty(self):
        assert _is_empty("Whitefield") is False
        assert _is_empty(1200) is False


class TestMergeTwoListings:
    """Tests for merge_two_listings function."""

    def test_fill_null_fields(self):
        """Fill NULL fields in base with overlay values."""
        base = {
            "source": "square_yards",
            "locality": "Whitefield",
            "bathrooms": None,
            "furnishing": None,
            "sources": ["square_yards"],
            "imputed_fields": [],
        }
        overlay = {
            "source": "housing",
            "locality": "Whitefield",
            "bathrooms": 2,
            "furnishing": "Furnished",
        }

        merged = merge_two_listings(base, overlay)

        assert merged["bathrooms"] == 2
        assert merged["furnishing"] == "Furnished"
        assert "bathrooms" in merged["imputed_fields"]
        assert "furnishing" in merged["imputed_fields"]

    def test_no_overwrite_existing(self):
        """Don't overwrite existing non-NULL values."""
        base = {
            "source": "square_yards",
            "locality": "Whitefield",
            "bathrooms": 3,
            "sources": ["square_yards"],
            "imputed_fields": [],
        }
        overlay = {
            "source": "housing",
            "locality": "Whitefield",
            "bathrooms": 2,
        }

        merged = merge_two_listings(base, overlay)

        assert merged["bathrooms"] == 3  # Keep original

    def test_merge_sources(self):
        """Merge source lists."""
        base = {
            "source": "square_yards",
            "sources": ["square_yards"],
            "imputed_fields": [],
        }
        overlay = {
            "source": "housing",
            "sources": ["housing"],
        }

        merged = merge_two_listings(base, overlay)

        assert "square_yards" in merged["sources"]
        assert "housing" in merged["sources"]
        assert merged["source_count"] == 2


class TestMergeSources:
    """Tests for merge_sources function."""

    def test_single_source(self):
        """Single source returns listings with quality scores."""
        sources = {
            "square_yards": [
                {
                    "source": "square_yards",
                    "locality": "Whitefield",
                    "price": 12000000,
                    "area_sqft": 1200,
                    "bedrooms": 2,
                }
            ]
        }

        merged = merge_sources(sources)

        assert len(merged) == 1
        assert "data_quality_score" in merged[0]
        assert "sources" in merged[0]

    def test_merge_two_sources(self):
        """Merge listings from two sources."""
        sources = {
            "square_yards": [
                {
                    "source": "square_yards",
                    "locality": "Whitefield",
                    "price": 12000000,
                    "area_sqft": 1200,
                    "bedrooms": 2,
                    "bathrooms": None,
                }
            ],
            "housing": [
                {
                    "source": "housing",
                    "locality": "Whitefield",
                    "price": 12000000,
                    "area_sqft": 1200,
                    "bedrooms": 2,
                    "bathrooms": 2,
                }
            ],
        }

        merged = merge_sources(sources, threshold=0.6)

        # Should have 1 merged listing (matched)
        assert len(merged) == 1
        assert merged[0]["bathrooms"] == 2  # Filled from housing
        assert merged[0]["source_count"] == 2

    def test_empty_sources(self):
        """Handle empty sources."""
        assert merge_sources({}) == []

    def test_quality_score_computed(self):
        """Quality scores are computed for all listings."""
        sources = {
            "square_yards": [
                {
                    "source": "square_yards",
                    "locality": "Whitefield",
                    "price": 12000000,
                    "area_sqft": 1200,
                    "bedrooms": 2,
                    "bathrooms": 2,
                    "furnishing": "Furnished",
                    "floor": 5,
                    "total_floors": 10,
                    "property_age": 2,
                    "parking": 1,
                    "pincode": "560066",
                }
            ]
        }

        merged = merge_sources(sources)

        assert len(merged) == 1
        assert merged[0]["data_quality_score"] > 80  # High quality
        assert merged[0]["quality_completeness"] == 100.0
