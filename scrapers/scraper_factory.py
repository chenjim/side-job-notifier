# scrapers/scraper_factory.py

from typing import Dict, Any
from .base_scraper import BaseScraper
from .eleduck_scraper import EleduckScraper
from .yuanjisong_scraper import YuanjisongScraper
from .sxsoft_scraper import SxsoftScraper
from .shixian_scraper import ShixianScraper
from .v2ex_scraper import V2exScraper

class ScraperFactory:
    """抓取器工厂类，根据网站类型创建对应的抓取器。"""
    
    _scrapers = {
        'eleduck': EleduckScraper,
        'yuanjisong': YuanjisongScraper,
        'sxsoft': SxsoftScraper,
        'shixian': ShixianScraper,
        'v2ex': V2exScraper,
        # 后续可以添加更多抓取器
        # 'other_site': OtherSiteScraper,
    }
    
    @classmethod
    def create_scraper(cls, site_key: str, site_config: Dict[str, Any]) -> BaseScraper:
        """创建指定网站的抓取器实例。
        
        Args:
            site_key: 网站标识符
            site_config: 网站配置信息
            
        Returns:
            BaseScraper: 对应的抓取器实例
            
        Raises:
            ValueError: 当网站类型不支持时
        """
        if site_key not in cls._scrapers:
            raise ValueError(f"不支持的网站类型: {site_key}")
        
        scraper_class = cls._scrapers[site_key]
        return scraper_class(site_config['url'], site_config['keywords'])
    
    @classmethod
    def get_supported_sites(cls) -> list:
        """获取支持的网站列表。
        
        Returns:
            list: 支持的网站标识符列表
        """
        return list(cls._scrapers.keys())