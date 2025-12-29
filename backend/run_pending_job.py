#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import sync_jobs_collection
from app.scraper import ZomatoScraper
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_pending_job():
    """Run the first pending job found"""
    # Get a pending job
    job = sync_jobs_collection.find_one({'status': 'pending'})
    
    if not job:
        logger.info("No pending jobs found")
        return
    
    job_id = job['job_id']
    total_urls = job['total_urls']
    
    logger.info(f"Found pending job {job_id} with {total_urls} URLs")
    
    # For demo purposes, let's use some test restaurant IDs
    # In a real scenario, these would be stored with the job
    test_res_ids = ["20752747", "20752748", "20752749"][:total_urls]
    
    logger.info(f"Running scraper for job {job_id} with IDs: {test_res_ids}")
    
    try:
        scraper = ZomatoScraper(job_id, num_workers=1)
        scraper.run_with_retries(test_res_ids, max_iterations=2)
        logger.info(f"✅ Completed scraping job {job_id}")
    except Exception as e:
        logger.error(f"❌ Scraping error for job {job_id}: {e}")

if __name__ == "__main__":
    run_pending_job()