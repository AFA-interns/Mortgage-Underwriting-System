"""
Setup script to install Playwright and Chromium.

Run this once before using the scraper:
    python setup_playwright.py
"""

import subprocess
import sys


def main():
    print("Installing Playwright...")
    subprocess.check_call([
        sys.executable, "-m", "pip", "install", "playwright"
    ])

    print("\nInstalling Chromium browser...")
    subprocess.check_call([
        sys.executable, "-m", "playwright", "install", "chromium"
    ])

    print("\nPlaywright setup complete!")
    print("\nTest with:")
    print("  python -m property_data.scrapers.runner --city Bangalore --bhk 2 --limit 5")


if __name__ == "__main__":
    main()
