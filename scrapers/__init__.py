# scrapers/__init__.py

from .base_scraper import BaseScraper
from .eleduck_scraper import EleduckScraper
from .yuanjisong_scraper import YuanjisongScraper
from .sxsoft_scraper import SxsoftScraper
from .scraper_factory import ScraperFactory

__all__ = ['BaseScraper', 'EleduckScraper', 'YuanjisongScraper', 'SxsoftScraper', 'ScraperFactory']