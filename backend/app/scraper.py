from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime
from app.database import sync_results_collection, sync_failed_urls_collection, sync_jobs_collection
from app.models import ScrapingResult, FailedURL
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ZomatoScraper:
    def __init__(self, job_id, num_workers=2):
        self.job_id = job_id
        self.num_workers = num_workers
        self.base_url = "https://www.zomato.com/webroutes/getPage"
        
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
            url = f"https://zoma.to/r/{res_id}"
            driver.get(url)
            
            # Wait for redirect and page load
            time.sleep(5)
            
            name = "N/A"
            address = "N/A"
            cost = "N/A"
            final_url = driver.current_url
            
            # Try multiple selectors for restaurant name
            name_selectors = [
                'h1[data-testid="restaurant-name"]',
                'h1',
                '.restaurant-name',
                '[class*="restaurant-name"]'
            ]
            
            for selector in name_selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    text = elem.text.strip()
                    if text and len(text) > 2 and 'checkout' not in text.lower():
                        name = text
                        break
                except:
                    continue
            
            # If no name found, try title
            if name == "N/A":
                title_text = driver.title
                if title_text and 'zomato' in title_text.lower():
                    name_part = title_text.split('|')[0].strip()
                    if ',' in name_part:
                        name = name_part.split(',')[0].strip()
                        address = name_part.split(',', 1)[1].strip()
                    else:
                        name = name_part
            
            # Try to get address from multiple sources
            address_selectors = [
                '[data-testid="address"]',
                '.restaurant-address',
                '[class*="address"]',
                'p:contains("Address")',
                'div:contains("Address")',
                'span:contains("Address")'
            ]
            
            # First try structured address selectors
            for selector in address_selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    text = elem.text.strip()
                    if text and len(text) > 5 and 'address' not in text.lower():
                        address = text
                        break
                except:
                    continue
            
            # Extract address from title if not found yet
            if address == "N/A":
                title_text = driver.title
                if title_text and 'zomato' in title_text.lower():
                    name_part = title_text.split('|')[0].strip()
                    if ',' in name_part:
                        address = name_part.split(',', 1)[1].strip()
            
            # Try to get cost - look for rupee symbol and cost text
            cost_selectors = [
                '[data-testid="cost-for-two"]',
                '.cost-for-two',
                '[class*="cost"]'
            ]
            
            for selector in cost_selectors:
                try:
                    elem = driver.find_element(By.CSS_SELECTOR, selector)
                    text = elem.text.strip()
                    if text and '₹' in text:
                        # Extract just the cost part
                        import re
                        cost_match = re.search(r'₹\d+[^\n]*', text)
                        if cost_match:
                            cost = cost_match.group(0)
                        else:
                            cost = text
                        break
                except:
                    continue
            
            # If no structured cost found, search page text
            if cost == "N/A":
                try:
                    page_text = driver.page_source
                    import re
                    # Look for cost patterns
                    cost_patterns = [
                        r'₹\d+\s*for\s*one\s*order',
                        r'₹\d+\s*for\s*two',
                        r'Average\s*Cost[^₹]*₹\d+[^\n]*'
                    ]
                    for pattern in cost_patterns:
                        matches = re.findall(pattern, page_text, re.IGNORECASE)
                        if matches:
                            cost = matches[0].strip()
                            break
                except:
                    pass
            
            result = ScrapingResult(
                job_id=self.job_id,
                res_id=str(res_id),
                name=name,
                url=final_url,
                address=address,
                cost=cost
            )
            
            sync_results_collection.insert_one(result.dict())
            logger.info(f"✓ {res_id}: {name}")
            return True, result
            
        except Exception as e:
            self._save_failed_url(res_id, f"https://www.zomato.com/r/{res_id}", None, str(e))
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
        sync_failed_urls_collection.insert_one(failed_url.dict())
    
    def scrape_batch(self, res_ids, iteration=1):
        sync_jobs_collection.update_one(
            {"job_id": self.job_id},
            {"$set": {"status": "in_progress", "updated_at": datetime.utcnow()}}
        )
        
        successful = 0
        failed = 0
        
        with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            future_to_id = {executor.submit(self.scrape_restaurant, res_id): res_id for res_id in res_ids}
            
            for future in as_completed(future_to_id):
                # Check if job was stopped
                job = sync_jobs_collection.find_one({"job_id": self.job_id})
                if job and job.get('status') == 'stopped':
                    logger.info(f"🛑 Job {self.job_id} was stopped, cancelling remaining tasks")
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
                    
                    sync_jobs_collection.update_one(
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
                    sync_jobs_collection.update_one(
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
                failed_docs = list(sync_failed_urls_collection.find({"job_id": self.job_id}))
                successful_docs = list(sync_results_collection.find({"job_id": self.job_id}))
                
                failed_ids = {doc["res_id"] for doc in failed_docs}
                successful_ids = {doc["res_id"] for doc in successful_docs}
                
                res_ids = list(failed_ids - successful_ids)
            else:
                break
        
        sync_jobs_collection.update_one(
            {"job_id": self.job_id},
            {"$set": {"status": "completed", "updated_at": datetime.utcnow()}}
        )
