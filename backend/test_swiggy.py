#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.swiggy_scraper import SwiggyScraper
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_swiggy_scraper():
    """Test Swiggy scraper with a sample restaurant ID"""
    
    # Test with a known Swiggy restaurant ID
    test_res_id = "393840"  # Different Swiggy restaurant ID
    job_id = "test-swiggy-job"
    
    logger.info(f"Testing Swiggy scraper with restaurant ID: {test_res_id}")
    
    try:
        scraper = SwiggyScraper(job_id, num_workers=1)
        success, result = scraper.scrape_restaurant(test_res_id)
        
        if success:
            logger.info(f"✅ Swiggy scraper working! Extracted:")
            logger.info(f"   Name: {result.name}")
            logger.info(f"   Address: {result.address}")
            logger.info(f"   Cost: {result.cost}")
            logger.info(f"   URL: {result.url}")
        else:
            logger.error("❌ Swiggy scraper failed to extract data")
            
    except Exception as e:
        logger.error(f"❌ Swiggy scraper error: {e}")

if __name__ == "__main__":
    test_swiggy_scraper()