"""Tests for fuzzy property matching across sources."""

import pytest

from property_data.scrapers.matcher import (
    normalize_text,
    compute_match_score,
    match_listings,
)


class TestNormalizeText:
    """Tests for normalize_text function."""

    def test_basic_normalization(self):
        assert normalize_text("  Whitefield  ") == "whitefield"

    def test_special_characters(self):
        assert normalize_text("Whitefield, Bangalore!") == "whitefield bangalore"

    def test_multiple_spaces(self):
        assert normalize_text("White   field") == "white field"

    def test_none_input(self):
        assert normalize_text(None) == ""

    def test_empty_string(self):
        assert normalize_text("") == ""


class TestComputeMatchScore:
    """Tests for compute_match_score function."""

    def test_perfect_match(self):
        """Identical listings should score 1.0."""
        a = {
            "locality": "Whitefield",
            "area_sqft": 1200,
            "bedrooms": 2,
            "price": 12000000,
        }
        b = {
            "locality": "Whitefield",
            "area_sqft": 1200,
            "bedrooms": 2,
            "price": 12000000,
        }

        score = compute_match_score(a, b)
        assert score == 1.0

    def test_partial_match(self):
        """Similar but not identical listings."""
        a = {
            "locality": "Whitefield",
            "area_sqft": 1200,
            "bedrooms": 2,
            "price": 12000000,
        }
        b = {
            "locality": "Whitefield",
            "area_sqft": 1250,
            "bedrooms": 2,
            "price": 12500000,
        }

        score = compute_match_score(a, b)
        assert 0.7 < score < 1.0

    def test_different_locality(self):
        """Different localities should score low."""
        a = {
            "locality": "Whitefield",
            "area_sqft": 1200,
            "bedrooms": 2,
            "price": 12000000,
        }
        b = {
            "locality": "Andheri West",
            "area_sqft": 1200,
            "bedrooms": 2,
            "price": 12000000,
        }

        score = compute_match_score(a, b)
        assert score < 0.5

    def test_missing_fields(self):
        """Handle missing fields gracefully."""
        a = {"locality": "Whitefield", "area_sqft": 1200}
        b = {"locality": "Whitefield", "area_sqft": 1200}

        score = compute_match_score(a, b)
        assert score > 0.0

    def test_empty_listings(self):
        """Empty listings should score 0."""
        score = compute_match_score({}, {})
        assert score == 0.0


class TestMatchListings:
    """Tests for match_listings function."""

    def test_basic_matching(self):
        """Match listings from two sources."""
        listings_a = [
            {
                "locality": "Whitefield",
                "area_sqft": 1200,
                "bedrooms": 2,
                "price": 12000000,
            }
        ]
        listings_b = [
            {
                "locality": "Whitefield",
                "area_sqft": 1200,
                "bedrooms": 2,
                "price": 12000000,
            }
        ]

        matches = match_listings(listings_a, listings_b, threshold=0.6)

        assert len(matches) == 1
        assert matches[0][2] == 1.0  # score

    def test_no_match_below_threshold(self):
        """No matches when below threshold."""
        listings_a = [
            {
                "locality": "Whitefield",
                "area_sqft": 1200,
                "bedrooms": 2,
                "price": 12000000,
            }
        ]
        listings_b = [
            {
                "locality": "Andheri West",
                "area_sqft": 5000,
                "bedrooms": 4,
                "price": 50000000,
            }
        ]

        matches = match_listings(listings_a, listings_b, threshold=0.6)

        assert len(matches) == 0

    def test_one_to_one_matching(self):
        """Each listing can only be matched once."""
        listings_a = [
            {
                "locality": "Whitefield",
                "area_sqft": 1200,
                "bedrooms": 2,
                "price": 12000000,
            }
        ]
        listings_b = [
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

        matches = match_listings(listings_a, listings_b, threshold=0.6)

        assert len(matches) == 1

    def test_empty_inputs(self):
        """Handle empty inputs."""
        assert match_listings([], [], threshold=0.6) == []
        assert match_listings([{"locality": "X"}], [], threshold=0.6) == []
        assert match_listings([], [{"locality": "X"}], threshold=0.6) == []
