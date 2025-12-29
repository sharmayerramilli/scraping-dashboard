#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.swiggy_scraper import SwiggyScraper
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_specific_swiggy_ids():
    """Test Swiggy scraper with user-provided restaurant IDs"""
    
    # User provided IDs
    test_res_ids = ["5916", "23748", "425"]
    job_id = "test-swiggy-specific"
    
    logger.info(f"Testing Swiggy scraper with IDs: {test_res_ids}")
    
    scraper = SwiggyScraper(job_id, num_workers=1)
    
    for res_id in test_res_ids:
        logger.info(f"\n--- Testing ID: {res_id} ---")
        try:
            success, result = scraper.scrape_restaurant(res_id)
            
            if success:
                logger.info(f"✅ ID {res_id} SUCCESS:")
                logger.info(f"   Name: {result.name}")
                logger.info(f"   Address: {result.address}")
                logger.info(f"   Cost: {result.cost}")
                logger.info(f"   URL: {result.url}")
            else:
                logger.error(f"❌ ID {res_id} FAILED")
                
        except Exception as e:
            logger.error(f"❌ ID {res_id} ERROR: {e}")

if __name__ == "__main__":
    test_specific_swiggy_ids()