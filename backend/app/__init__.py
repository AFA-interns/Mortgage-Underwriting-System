"""Mortgage underwriting backend. Loads backend/.env (if present) at import."""
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
