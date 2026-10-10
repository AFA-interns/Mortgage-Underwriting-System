"""
Tests for comparable property matching and retrieval.

Tests the database repository's find_comparables function
and the fuzzy matching logic used for cross-source deduplication.
"""

import pytest

from property_data.scrapers.matcher import (
    compute_match_score,
    match_listings,
    normalize_text,
)
from property_data.scrapers.merger import merge_sources


class TestFindComparables:
    """Tests for comparable property matching logic."""

    def test_exact_match_returns_score_1(self):
        """Identical listings should have a perfect match score."""
        listing_a = {
            "locality": "Whitefield",
            "area_sqft": 1200,
            "bedrooms": 2,
            "price": 12000000,
        }
        listing_b = {
            "locality": "Whitefield",
            "area_sqft": 1200,
            "bedrooms": 2,
            "price": 12000000,
        }

        score = compute_match_score(listing_a, listing_b)
        assert score == 1.0

    def test_similar_area_scores_high(self):
        """Listings with similar area should score above 0.7."""
        listing_a = {
            "locality": "Whitefield",
            "area_sqft": 1200,
            "bedrooms": 2,
            "price": 12000000,
        }
        listing_b = {
            "locality": "Whitefield",
            "area_sqft": 1250,
            "bedrooms": 2,
            "price": 12500000,
        }

        score = compute_match_score(listing_a, listing_b)
        assert score > 0.7

    def test_different_bhk_scores_low(self):
        """Listings with different BHK should score below 0.5."""
        listing_a = {
            "locality": "Whitefield",
            "area_sqft": 1200,
            "bedrooms": 2,
            "price": 12000000,
        }
        listing_b = {
            "locality": "Whitefield",
            "area_sqft": 1200,
            "bedrooms": 4,
            "price": 12000000,
        }

        score = compute_match_score(listing_a, listing_b)
        assert score < 0.5

    def test_different_locality_scores_low(self):
        """Listings in different localities should score below 0.5."""
        listing_a = {
            "locality": "Whitefield",
            "area_sqft": 1200,
            "bedrooms": 2,
            "price": 12000000,
        }
        listing_b = {
            "locality": "Andheri West",
            "area_sqft": 1200,
            "bedrooms": 2,
            "price": 12000000,
        }

        score = compute_match_score(listing_a, listing_b)
        assert score < 0.5

    def test_missing_fields_handled_gracefully(self):
        """Listings with missing fields should not crash."""
        listing_a = {"locality": "Whitefield"}
        listing_b = {"locality": "Whitefield"}

        score = compute_match_score(listing_a, listing_b)
        assert score > 0.0

    def test_empty_listings_return_zero(self):
        """Empty listings should return a score of 0."""
        score = compute_match_score({}, {})
        assert score == 0.0


class TestMatchListings:
    """Tests for matching listings across sources."""

    def test_match_identical_listings(self):
        """Identical listings from different sources should match."""
        source_a = [
            {
                "locality": "Whitefield",
                "area_sqft": 1200,
                "bedrooms": 2,
                "price": 12000000,
            }
        ]
        source_b = [
            {
                "locality": "Whitefield",
                "area_sqft": 1200,
                "bedrooms": 2,
                "price": 12000000,
            }
        ]

        matches = match_listings(source_a, source_b, threshold=0.6)
        assert len(matches) == 1
        assert matches[0][2] == 1.0

    def test_no_match_below_threshold(self):
        """Listings below the threshold should not match."""
        source_a = [
            {
                "locality": "Whitefield",
                "area_sqft": 1200,
                "bedrooms": 2,
                "price": 12000000,
            }
        ]
        source_b = [
            {
                "locality": "Andheri West",
                "area_sqft": 5000,
                "bedrooms": 4,
                "price": 50000000,
            }
        ]

        matches = match_listings(source_a, source_b, threshold=0.6)
        assert len(matches) == 0

    def test_one_to_one_matching(self):
        """Each listing can only be matched once."""
        source_a = [
            {
                "locality": "Whitefield",
                "area_sqft": 1200,
                "bedrooms": 2,
                "price": 12000000,
            }
        ]
        source_b = [
            {
                "locality": "Whitefield",
                "area_sqft": 1200,
                "bedrooms": 2,
                "price": 12000000,
            },
            {
                "locality": "Whitefield",
                "area_sqft": 1200,
                "bedrooms": 2,
                "price": 12000000,
            },
        ]

        matches = match_listings(source_a, source_b, threshold=0.6)
        assert len(matches) == 1

    def test_empty_inputs_return_empty(self):
        """Empty inputs should return empty matches."""
        assert match_listings([], [], threshold=0.6) == []
        assert match_listings([{"locality": "X"}], [], threshold=0.6) == []
        assert match_listings([], [{"locality": "X"}], threshold=0.6) == []


class TestMergeSourcesForComparables:
    """Tests for merging sources to produce comparable listings."""

    def test_merge_fills_null_fields(self):
        """Merging should fill NULL fields from other sources."""
        sources = {
            "square_yards": [
                {
                    "source": "square_yards",
                    "locality": "Whitefield",
                    "price": 12000000,
                    "area_sqft": 1200,
                    "bedrooms": 2,
                    "bathrooms": None,
                    "furnishing": None,
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
                    "furnishing": "Furnished",
                }
            ],
        }

        merged = merge_sources(sources, threshold=0.6)

        assert len(merged) == 1
        assert merged[0]["bathrooms"] == 2
        assert merged[0]["furnishing"] == "Furnished"
        assert merged[0]["source_count"] == 2

    def test_merge_preserves_all_unique_listings(self):
        """Listings that don't match any other source should still be included."""
        sources = {
            "square_yards": [
                {
                    "source": "square_yards",
                    "locality": "Whitefield",
                    "price": 12000000,
                    "area_sqft": 1200,
                    "bedrooms": 2,
                }
            ],
            "housing": [
                {
                    "source": "housing",
                    "locality": "Andheri West",
                    "price": 20000000,
                    "area_sqft": 1500,
                    "bedrooms": 3,
                }
            ],
        }

        merged = merge_sources(sources, threshold=0.6)

        assert len(merged) == 2

    def test_merge_computes_quality_scores(self):
        """All merged listings should have quality scores."""
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
        assert "data_quality_score" in merged[0]
        assert merged[0]["data_quality_score"] > 0

    def test_merge_sorts_by_quality(self):
        """Merged listings should be sorted by quality score descending."""
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
                },
                {
                    "source": "square_yards",
                    "locality": "Whitefield",
                    "price": 10000000,
                    "area_sqft": 1000,
                    "bedrooms": 2,
                },
            ]
        }

        merged = merge_sources(sources)

        assert len(merged) == 2
        assert merged[0]["data_quality_score"] >= merged[1]["data_quality_score"]


class TestNormalizeText:
    """Tests for text normalization used in matching."""

    def test_strips_whitespace(self):
        assert normalize_text("  Whitefield  ") == "whitefield"

    def test_removes_special_characters(self):
        assert normalize_text("Whitefield, Bangalore!") == "whitefield bangalore"

    def test_collapses_multiple_spaces(self):
        assert normalize_text("White   field") == "white field"

    def test_handles_none(self):
        assert normalize_text(None) == ""

    def test_handles_empty_string(self):
        assert normalize_text("") == ""
