from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime
from app.database import sync_swiggy_results_collection, sync_swiggy_failed_urls_collection, sync_swiggy_jobs_collection
from app.models import ScrapingResult, FailedURL
import logging
import random
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SwiggyScraper:
    def __init__(self, job_id, num_workers=2):
        self.job_id = job_id
        self.num_workers = num_workers
        
    def _create_driver(self):
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
        
    def scrape_restaurant(self, res_id):
        driver = None
        try:
            time.sleep(random.uniform(2, 4))
            driver = self._create_driver()
            
            # Try different URL formats for Swiggy
            urls_to_try = [
                f"https://www.swiggy.com/restaurants/restaurant-{res_id}",
                f"https://www.swiggy.com/restaurants/-{res_id}",
                f"https://www.swiggy.com/city/delhi/restaurant-{res_id}"
            ]
            
            name = "N/A"
            address = "N/A"
            cost = "N/A"
            final_url = ""
            
            for url in urls_to_try:
                try:
                    driver.get(url)
                    time.sleep(5)
                    final_url = driver.current_url
                    
                    # Check if page loaded successfully (not 404 or error)
                    if "404" not in driver.title.lower() and "error" not in driver.title.lower():
                        
                        # Extract name from title first
                        title_text = driver.title
                        if title_text and 'swiggy' in title_text.lower():
                            # Swiggy titles are usually "Restaurant Name | Area | Swiggy"
                            parts = title_text.split('|')
                            if len(parts) >= 2:
                                potential_name = parts[0].strip()
                                # Skip generic titles
                                if 'order food online' not in potential_name.lower() and len(potential_name) < 50:
                                    name = potential_name
                                if len(parts) >= 3:
                                    address = parts[1].strip()
                        
                        # Try to extract from page elements
                        if name == "N/A":
                            name_selectors = [
                                'h1',
                                '[data-testid="restaurant-name"]',
                                '.restaurant-name',
                                '[class*="RestaurantNameAddress_name"]'
                            ]
                            
                            for selector in name_selectors:
                                try:
                                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                                    text = elem.text.strip()
                                    if text and len(text) > 2 and 'order' not in text.lower():
                                        name = text
                                        break
                                except:
                                    continue
                        
                        # Extract address from URL and page content
                        if address == "N/A":
                            # Extract from URL path (e.g., /city/bangalore/restaurant-name-area-rest123)
                            url_parts = final_url.split('/')
                            if len(url_parts) >= 4:
                                city = url_parts[4] if len(url_parts) > 4 else ""
                                restaurant_part = url_parts[-1] if url_parts else ""
                                # Extract area from restaurant slug
                                if '-rest' in restaurant_part:
                                    slug_parts = restaurant_part.split('-rest')[0].split('-')
                                    if len(slug_parts) > 1:
                                        # Remove restaurant name parts, keep area parts
                                        restaurant_name_words = name.lower().replace("'", "").split()
                                        area_parts = []
                                        for part in slug_parts:
                                            # Skip parts that are in restaurant name
                                            if part.lower() not in restaurant_name_words:
                                                area_parts.append(part)
                                        
                                        if area_parts:
                                            area = ' '.join(area_parts[-2:] if len(area_parts) > 1 else area_parts).title()
                                            if city:
                                                address = f"{area}, {city.title()}"
                                            else:
                                                address = area
                        
                        # Try to extract from page elements
                        if address == "N/A":
                            address_selectors = [
                                '[data-testid="address"]',
                                '.restaurant-address',
                                '[class*="RestaurantNameAddress_area"]',
                                '[class*="address"]',
                                'span:contains("km away")',
                                'div:contains("km away")'
                            ]
                            
                            for selector in address_selectors:
                                try:
                                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                                    text = elem.text.strip()
                                    if text and len(text) > 5 and 'km away' not in text:
                                        address = text
                                        break
                                except:
                                    continue
                        
                        # Extract cost information
                        try:
                            page_text = driver.page_source
                            cost_patterns = [
                                r'₹\d+\s*for\s*two',
                                r'₹\d+\s*for\s*2',
                                r'Cost\s*for\s*two[^₹]*₹\d+[^\n]*'
                            ]
                            for pattern in cost_patterns:
                                matches = re.findall(pattern, page_text, re.IGNORECASE)
                                if matches:
                                    cost = matches[0].strip()
                                    break
                        except:
                            pass
                        
                        # If we got some data, break out of URL loop
                        if name != "N/A":
                            break
                            
                except Exception as e:
                    logger.debug(f"Failed URL {url}: {e}")
                    continue
            
            # If still no name found, mark as 404
            if name == "N/A":
                name = "404"
            
            result = ScrapingResult(
                job_id=self.job_id,
                res_id=str(res_id),
                name=name,
                url=final_url or f"https://www.swiggy.com/restaurants/-{res_id}",
                address=address,
                cost=cost
            )
            
            sync_swiggy_results_collection.insert_one(result.dict())
            logger.info(f"✓ {res_id}: {name}") 
            return True, result
            
        except Exception as e:
            self._save_failed_url(res_id, f"https://www.swiggy.com/restaurants/-{res_id}", None, str(e))
            logger.error(f"✗ {res_id}: {str(e)}")
            return False, None
        finally:
            if driver:
                driver.quit()
    
    def _save_failed_url(self, res_id, url, status_code, error_message):
        failed_url = FailedURL(
            job_id=self.job_id,
            res_id=str(res_id),
            url=url,
            status_code=status_code,
            error_message=error_message,
            retry_count=0
        )
        sync_swiggy_failed_urls_collection.insert_one(failed_url.dict())
    
    def scrape_batch(self, res_ids, iteration=1):
        sync_swiggy_jobs_collection.update_one(
            {"job_id": self.job_id},
            {"$set": {"status": "in_progress", "updated_at": datetime.utcnow()}}
        )
        
        successful = 0
        failed = 0
        
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            future_to_id = {executor.submit(self.scrape_restaurant, res_id): res_id for res_id in res_ids}
            
            for future in as_completed(future_to_id):
                # Check if job was stopped
                job = sync_swiggy_jobs_collection.find_one({"job_id": self.job_id})
                if job and job.get('status') == 'stopped':
                    logger.info(f"🛑 Swiggy job {self.job_id} was stopped, cancelling remaining tasks")
                    # Cancel remaining futures
                    for f in future_to_id:
                        if not f.done():
                            f.cancel()
                    break
                
                try:
                    success, result = future.result()
                    if success:
                        successful += 1
                    else:
                        failed += 1
                    
                    sync_swiggy_jobs_collection.update_one(
                        {"job_id": self.job_id},
                        {
                            "$inc": {
                                "processed_urls": 1,
                                "successful_urls": 1 if success else 0,
                                "failed_urls": 0 if success else 1
                            }
                        }
                    )
                except Exception as e:
                    failed += 1
                    sync_swiggy_jobs_collection.update_one(
                        {"job_id": self.job_id},
                        {"$inc": {"processed_urls": 1, "failed_urls": 1}}
                    )
        
        return successful, failed
    
    def run_with_retries(self, res_ids, max_iterations=3):
        for iteration in range(1, max_iterations + 1):
            if not res_ids:
                break
                
            successful, failed = self.scrape_batch(res_ids, iteration)
            
            if iteration < max_iterations and failed > 0:
                time.sleep(3)
                failed_docs = list(sync_swiggy_failed_urls_collection.find({"job_id": self.job_id}))
                successful_docs = list(sync_swiggy_results_collection.find({"job_id": self.job_id}))
                
                failed_ids = {doc["res_id"] for doc in failed_docs}
                successful_ids = {doc["res_id"] for doc in successful_docs}
                
                res_ids = list(failed_ids - successful_ids)
            else:
                break
        
        sync_swiggy_jobs_collection.update_one(
            {"job_id": self.job_id},
            {"$set": {"status": "completed", "updated_at": datetime.utcnow()}}
        )