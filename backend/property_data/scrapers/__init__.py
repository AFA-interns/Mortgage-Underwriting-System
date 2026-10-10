"""Multi-source property scraper package."""

from property_data.scrapers.jsonld_extractor import extract_from_all_sources
from property_data.scrapers.matcher import match_listings, compute_match_score
from property_data.scrapers.merger import merge_sources, merge_two_listings
from property_data.scrapers.quality import compute_quality_score, get_quality_label
from property_data.scrapers.squareyards_v2 import SquareYardsScraperV2
from property_data.scrapers.housing import HousingScraper
from property_data.scrapers.magicbricks import MagicBricksScraper

__all__ = [
    "extract_from_all_sources",
    "match_listings",
    "compute_match_score",
    "merge_sources",
    "merge_two_listings",
    "compute_quality_score",
    "get_quality_label",
    "SquareYardsScraperV2",
    "HousingScraper",
    "MagicBricksScraper",
]
