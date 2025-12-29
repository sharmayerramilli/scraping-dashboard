import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime
from app.database import sync_results_collection, sync_failed_urls_collection, sync_jobs_collection
from app.models import ScrapingResult, FailedURL
import logging
import random
import re
import json
import socket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ZomatoScraper:
    def __init__(self, job_id, num_workers=3):
        self.job_id = job_id
        self.num_workers = num_workers
        # Use the short URL format which redirects to full URL
        self.base_url = "https://zoma.to/r/{res_id}"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'DNT': '1',
            'Sec-GPC': '1'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Test network connectivity
        self._test_connectivity()
        
    def _test_connectivity(self):
        """Test network connectivity to Zomato"""
        try:
            # Test DNS resolution
            socket.gethostbyname('zoma.to')
            logger.info("✅ Network connectivity test passed")
        except socket.gaierror as e:
            logger.error(f"❌ DNS resolution failed for zoma.to: {e}")
            logger.error("Please check your internet connection")
        except Exception as e:
            logger.error(f"❌ Network connectivity test failed: {e}")
        
    def extract_from_json_ld(self, soup):
        """Extract data from JSON-LD structured data"""
        data = {}
        try:
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    json_data = json.loads(script.string)
                    
                    # Handle both single objects and arrays
                    if isinstance(json_data, list):
                        for item in json_data:
                            if item.get('@type') == 'Restaurant':
                                data['name'] = item.get('name')
                                data['rating'] = item.get('aggregateRating', {}).get('ratingValue')
                                
                                address_data = item.get('address', {})
                                if isinstance(address_data, dict):
                                    address_parts = [
                                        address_data.get('streetAddress', ''),
                                        address_data.get('addressLocality', ''),
                                        address_data.get('addressRegion', ''),
                                        address_data.get('postalCode', '')
                                    ]
                                    data['address'] = ', '.join(filter(None, address_parts))
                                
                                data['phone'] = item.get('telephone')
                                
                                cuisine = item.get('servesCuisine')
                                if isinstance(cuisine, list):
                                    data['cuisine'] = ', '.join(cuisine)
                                elif cuisine:
                                    data['cuisine'] = cuisine
                                    
                    elif isinstance(json_data, dict) and json_data.get('@type') == 'Restaurant':
                        data['name'] = json_data.get('name')
                        data['rating'] = json_data.get('aggregateRating', {}).get('ratingValue')
                        
                        address_data = json_data.get('address', {})
                        if isinstance(address_data, dict):
                            address_parts = [
                                address_data.get('streetAddress', ''),
                                address_data.get('addressLocality', ''),
                                address_data.get('addressRegion', ''),
                                address_data.get('postalCode', '')
                            ]
                            data['address'] = ', '.join(filter(None, address_parts))
                        
                        data['phone'] = json_data.get('telephone')
                        
                        cuisine = json_data.get('servesCuisine')
                        if isinstance(cuisine, list):
                            data['cuisine'] = ', '.join(cuisine)
                        elif cuisine:
                            data['cuisine'] = cuisine
                            
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.debug(f"Error extracting JSON-LD: {e}")
        
        return data
    
    def extract_from_meta_tags(self, soup):
        """Extract data from meta tags"""
        data = {}
        
        # Try og:title for name
        og_title = soup.find('meta', property='og:title')
        if og_title:
            data['name'] = og_title.get('content', '').strip()
        
        # Try description for cuisine/info
        description = soup.find('meta', {'name': 'description'})
        if description:
            desc_text = description.get('content', '')
            # Often contains cuisine in format "Italian, Chinese"
            if ',' in desc_text and not data.get('cuisine'):
                data['cuisine'] = desc_text.split('|')[0].strip()
        
        return data
    
    def scrape_restaurant(self, res_id):
        """Scrape a single restaurant page"""
        url = self.base_url.format(res_id=res_id)
        
        try:
            # Add random delay to avoid rate limiting
            time.sleep(random.uniform(2, 5))
            
            # Make request with redirects
            response = self.session.get(url, timeout=30, allow_redirects=True)
            
            # Handle different status codes
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Get final redirected URL
                final_url = response.url
                
                # Debug: Log the actual URL being scraped
                logger.debug(f"Scraping URL: {final_url} for res_id: {res_id}")
                
                # Initialize data dictionary
                extracted_data = {
                    'name': None,
                    'address': None,
                    'cost': None
                }
                
                # Try to get name from page title
                title = soup.find('title')
                if title:
                    title_text = title.get_text(strip=True)
                    if 'zomato' in title_text.lower():
                        name_part = title_text.split('|')[0].strip()
                        name_part = name_part.split(',')[0].strip()
                        if len(name_part) > 2:
                            extracted_data['name'] = name_part
                
                # Extract location from title
                if title and ',' in title_text and '|' in title_text:
                    location_part = title_text.split('|')[0].strip()
                    if ',' in location_part:
                        location = location_part.split(',', 1)[1].strip()
                        if len(location) > 2:
                            extracted_data['address'] = location
                
                # Look for cost/price information
                cost_selectors = [
                    '[data-testid="cost-for-two"]',
                    '.cost-for-two',
                    '[class*="cost"]',
                    '[class*="price"]'
                ]
                for selector in cost_selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        cost_text = elem.get_text(strip=True)
                        if cost_text and ('₹' in cost_text or 'cost' in cost_text.lower()):
                            extracted_data['cost'] = cost_text
                            break
                
                # Create result
                result = ScrapingResult(
                    job_id=self.job_id,
                    res_id=str(res_id),
                    name=extracted_data['name'] or "N/A",
                    url=final_url,
                    address=extracted_data['address'] or "N/A",
                    cost=extracted_data['cost'] or "N/A"
                )
                
                # Save to MongoDB
                sync_results_collection.insert_one(result.dict())
                
                # Log with actual extracted data
                logger.info(f"✓ Scraped {res_id}: {extracted_data['name']} | Address: {extracted_data['address']} | Cost: {extracted_data['cost']}")
                
                return True, result
                
            elif response.status_code == 403:
                error_msg = f"Access forbidden (403) - Zomato blocked the request"
                self._save_failed_url(res_id, url, response.status_code, error_msg)
                logger.warning(f"✗ Blocked {res_id}: {error_msg}")
                return False, None
            elif response.status_code == 404:
                error_msg = f"Restaurant not found (404)"
                self._save_failed_url(res_id, url, response.status_code, error_msg)
                logger.warning(f"✗ Not found {res_id}: {error_msg}")
                return False, None
            else:
                error_msg = f"HTTP {response.status_code}"
                self._save_failed_url(res_id, url, response.status_code, error_msg)
                logger.warning(f"✗ Failed {res_id}: {error_msg}")
                return False, None
                
        except requests.exceptions.Timeout:
            error_msg = "Request timeout"
            self._save_failed_url(res_id, url, None, error_msg)
            logger.error(f"✗ Timeout for {res_id}")
            return False, None
        except requests.exceptions.ConnectionError:
            error_msg = "Connection error"
            self._save_failed_url(res_id, url, None, error_msg)
            logger.error(f"✗ Connection error for {res_id}")
            return False, None
        except Exception as e:
            error_msg = str(e)
            self._save_failed_url(res_id, url, None, error_msg)
            logger.error(f"✗ Error scraping {res_id}: {error_msg}")
            return False, None
    
    def _save_failed_url(self, res_id, url, status_code, error_message):
        """Save failed URL to database"""
        existing = sync_failed_urls_collection.find_one({
            "job_id": self.job_id,
            "res_id": str(res_id)
        })
        
        if existing:
            sync_failed_urls_collection.update_one(
                {"job_id": self.job_id, "res_id": str(res_id)},
                {
                    "$set": {
                        "status_code": status_code,
                        "error_message": error_message,
                        "last_attempt": datetime.utcnow()
                    },
                    "$inc": {"retry_count": 1}
                }
            )
        else:
            failed_url = FailedURL(
                job_id=self.job_id,
                res_id=str(res_id),
                url=url,
                status_code=status_code,
                error_message=error_message,
                retry_count=0
            )
            sync_failed_urls_collection.insert_one(failed_url.dict())
    
    def scrape_batch(self, res_ids, iteration=1):
        """Scrape multiple restaurant IDs with workers"""
        logger.info(f"Starting iteration {iteration} with {len(res_ids)} URLs and {self.num_workers} workers")
        
        sync_jobs_collection.update_one(
            {"job_id": self.job_id},
            {
                "$set": {
                    "status": "in_progress",
                    "current_iteration": iteration,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        successful = 0
        failed = 0
        
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            future_to_id = {executor.submit(self.scrape_restaurant, res_id): res_id for res_id in res_ids}
            
            for future in as_completed(future_to_id):
                res_id = future_to_id[future]
                try:
                    success, result = future.result()
                    if success:
                        successful += 1
                    else:
                        failed += 1
                    
                    sync_jobs_collection.update_one(
                        {"job_id": self.job_id},
                        {
                            "$inc": {
                                "processed_urls": 1,
                                "successful_urls": 1 if success else 0,
                                "failed_urls": 0 if success else 1
                            },
                            "$set": {"updated_at": datetime.utcnow()}
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Worker error for {res_id}: {e}")
                    failed += 1
                    
                    sync_jobs_collection.update_one(
                        {"job_id": self.job_id},
                        {
                            "$inc": {
                                "processed_urls": 1,
                                "failed_urls": 1
                            },
                            "$set": {"updated_at": datetime.utcnow()}
                        }
                    )
        
        logger.info(f"Iteration {iteration} completed: {successful} successful, {failed} failed")
        return successful, failed
    
    def run_with_retries(self, res_ids, max_iterations=3):
        """Run scraping with retry logic"""
        current_ids = res_ids
        
        for iteration in range(1, max_iterations + 1):
            if not current_ids:
                logger.info("No URLs to process")
                break
                
            successful, failed = self.scrape_batch(current_ids, iteration)
            
            if iteration < max_iterations and failed > 0:
                logger.info(f"Preparing retry iteration {iteration + 1}")
                time.sleep(3)
                
                failed_docs = list(sync_failed_urls_collection.find({
                    "job_id": self.job_id,
                    "retry_count": {"$lte": iteration}
                }))
                
                failed_ids_set = {doc["res_id"] for doc in failed_docs}
                
                successful_docs = sync_results_collection.find({
                    "job_id": self.job_id
                })
                successful_ids_set = {doc["res_id"] for doc in successful_docs}
                
                current_ids = list(failed_ids_set - successful_ids_set)
                
                logger.info(f"Retrying {len(current_ids)} failed URLs")
                
                if not current_ids:
                    logger.info("All URLs succeed
Average Cost
₹100 for one order (approx.)ed, no need to retry")
                    break
            else:
                break
        
        job = sync_jobs_collection.find_one({"job_id": self.job_id})
        
        total_urls = job['total_urls']
        successful_urls = job['successful_urls']
        failed_urls = total_urls - successful_urls
        
        sync_jobs_collection.update_one(
            {"job_id": self.job_id},
            {
                "$set": {
                    "status": "completed",
                    "processed_urls": total_urls,
                    "failed_urls": failed_urls,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"Scraping job {self.job_id} completed: {successful_urls} successful, {failed_urls} failed")
