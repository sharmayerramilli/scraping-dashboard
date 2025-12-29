#!/usr/bin/env python3
"""Test script to verify scraper functionality"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from scraper import ZomatoScraper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_single_scrape():
    """Test scraping a single restaurant"""
    test_res_id = "20752747"
    job_id = "test_job_001"
    
    logger.info(f"Testing scraper with res_id: {test_res_id}")
    
    scraper = ZomatoScraper(job_id, num_workers=1)
    success, result = scraper.scrape_restaurant(test_res_id)
    
    if success:
        logger.info("✅ Scraping successful!")
        logger.info(f"Name: {result.name}")
        logger.info(f"Cuisine: {result.cuisine}")
        logger.info(f"Rating: {result.rating}")
        logger.info(f"Address: {result.address}")
        logger.info(f"Phone: {result.phone}")
        logger.info(f"URL: {result.url}")
    else:
        logger.error("❌ Scraping failed!")
        return False
    
    return True

if __name__ == "__main__":
    success = test_single_scrape()
    sys.exit(0 if success else 1)
