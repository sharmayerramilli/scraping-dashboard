import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime
from app.database import sync_results_collection, sync_failed_urls_collection, sync_jobs_collection
from app.models import ScrapingResult, FailedURL
import logging
import random
import json
import re
import uuid

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BlinkitScraper:
    def __init__(self, job_id, num_workers=2):
        self.job_id = job_id
        self.num_workers = num_workers
        
        # Multiple user agents to rotate
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0'
        ]
        
        # Location coordinates for different cities
        self.locations = [
            {'lat': '28.7041', 'lon': '77.1025', 'city': 'Delhi'},
            {'lat': '19.0760', 'lon': '72.8777', 'city': 'Mumbai'},
            {'lat': '12.9716', 'lon': '77.5946', 'city': 'Bangalore'},
            {'lat': '17.3850', 'lon': '78.4867', 'city': 'Hyderabad'},
            {'lat': '22.5726', 'lon': '88.3639', 'city': 'Kolkata'}
        ]
        
        self.session = requests.Session()
        self.session.max_redirects = 10
        
    def _get_random_headers(self):
        """Generate random headers for each request"""
        location = random.choice(self.locations)
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,hi;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'lat': location['lat'],
            'lon': location['lon']
        }
    
    def scrape_product(self, product_id):
        """Scrape a single product from Blinkit with multiple fallback methods"""
        try:
            # Check if job is stopped
            job = sync_jobs_collection.find_one({"job_id": self.job_id})
            if job and job.get('status') == 'stopped':
                logger.info(f"Job {self.job_id} stopped, skipping {product_id}")
                return False, None
            
            # Add random delay to avoid rate limiting
            time.sleep(random.uniform(2, 4))
            
            # Try multiple methods in order
            methods = [
                self._try_direct_product_page,
                self._try_search_api,
                self._try_mobile_api
            ]
            
            for method in methods:
                try:
                    success, result = method(product_id)
                    if success:
                        return True, result
                except Exception as e:
                    logger.debug(f"Method {method.__name__} failed for {product_id}: {e}")
                    continue
            
            # If all methods failed
            error_msg = "All scraping methods failed"
            self._save_failed_url(product_id, f"https://blinkit.com/product/{product_id}", None, error_msg)
            logger.warning(f"✗ Failed {product_id}: {error_msg}")
            return False, None
                
        except requests.exceptions.Timeout:
            error_msg = "Request timeout"
            self._save_failed_url(product_id, f"https://blinkit.com/product/{product_id}", None, error_msg)
            logger.error(f"✗ Timeout for {product_id}")
            return False, None
        except requests.exceptions.ConnectionError:
            error_msg = "Connection error"
            self._save_failed_url(product_id, f"https://blinkit.com/product/{product_id}", None, error_msg)
            logger.error(f"✗ Connection error for {product_id}")
            return False, None
        except Exception as e:
            error_msg = str(e)
            self._save_failed_url(product_id, f"https://blinkit.com/product/{product_id}", None, error_msg)
            logger.error(f"✗ Error scraping {product_id}: {error_msg}")
            return False, None
    
    def _try_direct_product_page(self, product_id):
        """Try scraping from direct product page"""
        headers = self._get_random_headers()
        
        # Try different URL patterns
        url_patterns = [
            f"https://blinkit.com/prn/product/prid/{product_id}",
            f"https://blinkit.com/product/{product_id}",
            f"https://blinkit.com/p/{product_id}"
        ]
        
        for product_url in url_patterns:
            try:
                response = self.session.get(product_url, headers=headers, timeout=25, allow_redirects=True)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    extracted_data = self._extract_from_html(soup, product_id, response.url)
                    
                    if extracted_data and extracted_data.get('name') != 'N/A':
                        result = ScrapingResult(
                            job_id=self.job_id,
                            res_id=str(product_id),
                            name=extracted_data.get('name', 'N/A'),
                            cuisine=extracted_data.get('category', 'N/A'),
                            rating=extracted_data.get('rating', 'N/A'),
                            address=extracted_data.get('brand', 'N/A'),
                            phone=extracted_data.get('unit', 'N/A'),
                            url=response.url,
                            status="success",
                            status_code=response.status_code
                        )
                        
                        sync_results_collection.insert_one(result.dict())
                        logger.info(f"✓ [DIRECT] Scraped {product_id}: {extracted_data.get('name')}")
                        return True, result
                        
                elif response.status_code == 403:
                    # Try with different headers on 403
                    time.sleep(random.uniform(3, 6))
                    continue
                    
            except Exception as e:
                logger.debug(f"Direct page method failed for {product_url}: {e}")
                continue
        
        return False, None
    
    def _try_search_api(self, product_id):
        """Try using Blinkit search API"""
        headers = self._get_random_headers()
        headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'Referer': 'https://blinkit.com/',
            'Origin': 'https://blinkit.com'
        })
        
        search_endpoints = [
            "https://blinkit.com/v6/search/products",
            "https://blinkit.com/v2/search",
            "https://blinkit.com/api/v1/search"
        ]
        
        for endpoint in search_endpoints:
            try:
                params = {
                    'search_type': 0,
                    'q': str(product_id),
                    'size': 1
                }
                
                response = self.session.get(endpoint, headers=headers, params=params, timeout=20)
                
                if response.status_code == 200:
                    data = response.json()
                    extracted_data = self._extract_from_search_api(data, product_id)
                    
                    if extracted_data and extracted_data.get('name') != 'N/A':
                        result = ScrapingResult(
                            job_id=self.job_id,
                            res_id=str(product_id),
                            name=extracted_data.get('name', 'N/A'),
                            cuisine=extracted_data.get('category', 'N/A'),
                            rating=extracted_data.get('rating', 'N/A'),
                            address=extracted_data.get('brand', 'N/A'),
                            phone=extracted_data.get('unit', 'N/A'),
                            url=f"https://blinkit.com/product/{product_id}",
                            status="success",
                            status_code=response.status_code
                        )
                        
                        sync_results_collection.insert_one(result.dict())
                        logger.info(f"✓ [API] Scraped {product_id}: {extracted_data.get('name')}")
                        return True, result
                        
            except Exception as e:
                logger.debug(f"Search API method failed for {endpoint}: {e}")
                continue
        
        return False, None
    
    def _try_mobile_api(self, product_id):
        """Try using mobile API endpoints"""
        headers = {
            'User-Agent': 'Blinkit/1.0 (Android 12; Mobile)',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'app_client': 'consumer_android',
            'app_version': '4.20.4',
            'device_id': str(uuid.uuid4()),
            'lat': '28.7041',
            'lon': '77.1025'
        }
        
        mobile_endpoints = [
            f"https://blinkit.com/v1/products/{product_id}",
            f"https://blinkit.com/v2/products/{product_id}",
            f"https://blinkit.com/mobile/v1/product/{product_id}"
        ]
        
        for endpoint in mobile_endpoints:
            try:
                response = self.session.get(endpoint, headers=headers, timeout=20)
                
                if response.status_code == 200:
                    data = response.json()
                    extracted_data = self._extract_from_mobile_api(data, product_id)
                    
                    if extracted_data and extracted_data.get('name') != 'N/A':
                        result = ScrapingResult(
                            job_id=self.job_id,
                            res_id=str(product_id),
                            name=extracted_data.get('name', 'N/A'),
                            cuisine=extracted_data.get('category', 'N/A'),
                            rating=extracted_data.get('rating', 'N/A'),
                            address=extracted_data.get('brand', 'N/A'),
                            phone=extracted_data.get('unit', 'N/A'),
                            url=f"https://blinkit.com/product/{product_id}",
                            status="success",
                            status_code=response.status_code
                        )
                        
                        sync_results_collection.insert_one(result.dict())
                        logger.info(f"✓ [MOBILE] Scraped {product_id}: {extracted_data.get('name')}")
                        return True, result
                        
            except Exception as e:
                logger.debug(f"Mobile API method failed for {endpoint}: {e}")
                continue
        
        return False, None
    
    def _extract_from_html(self, soup, product_id, url):
        """Extract product data from HTML"""
        extracted = {
            'name': 'N/A',
            'category': 'N/A',
            'rating': 'N/A',
            'brand': 'N/A',
            'unit': 'N/A',
            'price': 'N/A'
        }
        
        try:
            # Try to find JSON-LD data
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        if data.get('@type') == 'Product':
                            extracted['name'] = data.get('name', 'N/A')
                            extracted['brand'] = data.get('brand', {}).get('name', 'N/A')
                            
                            # Get price
                            offers = data.get('offers', {})
                            if offers:
                                price = offers.get('price')
                                if price:
                                    extracted['price'] = f"₹{price}"
                            
                            # Get rating
                            rating_data = data.get('aggregateRating', {})
                            if rating_data:
                                extracted['rating'] = str(rating_data.get('ratingValue', 'N/A'))
                except:
                    continue
            
            # Try meta tags
            if extracted['name'] == 'N/A':
                og_title = soup.find('meta', property='og:title')
                if og_title:
                    extracted['name'] = og_title.get('content', 'N/A')
            
            # Try to find product name in title
            if extracted['name'] == 'N/A':
                title = soup.find('title')
                if title:
                    title_text = title.get_text()
                    # Remove "Buy" and "Online at Best Price" type text
                    title_text = re.sub(r'Buy\s+|Online.*|at Best Price.*|\|.*Blinkit.*', '', title_text, flags=re.IGNORECASE).strip()
                    if title_text:
                        extracted['name'] = title_text
            
            # Try to find price
            if extracted['price'] == 'N/A':
                price_patterns = [
                    r'₹\s*(\d+(?:\.\d+)?)',
                    r'Rs\.?\s*(\d+(?:\.\d+)?)',
                ]
                page_text = soup.get_text()
                for pattern in price_patterns:
                    matches = re.findall(pattern, page_text)
                    if matches:
                        extracted['price'] = f"₹{matches[0]}"
                        break
            
            # Try to find category from breadcrumb or nav
            breadcrumb = soup.find('nav', {'aria-label': 'breadcrumb'})
            if breadcrumb:
                links = breadcrumb.find_all('a')
                if len(links) > 1:
                    extracted['category'] = links[-1].get_text(strip=True)
            
            # Try to find unit/quantity
            unit_patterns = [
                r'(\d+\s*(?:g|kg|ml|l|gm|pieces?|pcs?|pack))',
            ]
            page_text = soup.get_text()
            for pattern in unit_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    extracted['unit'] = matches[0]
                    break
                    
        except Exception as e:
            logger.debug(f"Error extracting from HTML: {e}")
        
        return extracted
    
    def _extract_from_search_api(self, data, product_id):
        """Extract product data from search API response"""
        extracted = {
            'name': 'N/A',
            'category': 'N/A',
            'rating': 'N/A',
            'brand': 'N/A',
            'unit': 'N/A',
            'price': 'N/A'
        }
        
        try:
            # Try different response structures
            if 'objects' in data:
                for obj in data['objects']:
                    if str(obj.get('id')) == str(product_id):
                        extracted['name'] = obj.get('name', obj.get('display_name', 'N/A'))
                        extracted['price'] = f"₹{obj.get('price', obj.get('mrp', 'N/A'))}"
                        extracted['unit'] = obj.get('unit', obj.get('unit_type', 'N/A'))
                        extracted['brand'] = obj.get('brand', obj.get('brand_name', 'N/A'))
                        
                        # Get category
                        if 'l1_category' in obj:
                            extracted['category'] = obj['l1_category'].get('name', 'N/A')
                        elif 'category' in obj:
                            extracted['category'] = obj['category'].get('name', obj['category'])
                        
                        break
            
            elif 'products' in data:
                for product in data['products']:
                    if str(product.get('id')) == str(product_id):
                        extracted['name'] = product.get('name', 'N/A')
                        extracted['price'] = f"₹{product.get('price', 'N/A')}"
                        extracted['unit'] = product.get('unit', 'N/A')
                        extracted['brand'] = product.get('brand', 'N/A')
                        extracted['category'] = product.get('category', 'N/A')
                        break
                        
        except Exception as e:
            logger.debug(f"Error extracting from search API: {e}")
        
        return extracted
    
    def _extract_from_mobile_api(self, data, product_id):
        """Extract product data from mobile API response"""
        extracted = {
            'name': 'N/A',
            'category': 'N/A',
            'rating': 'N/A',
            'brand': 'N/A',
            'unit': 'N/A',
            'price': 'N/A'
        }
        
        try:
            if 'product' in data:
                product = data['product']
            elif 'data' in data:
                product = data['data']
            else:
                product = data
            
            extracted['name'] = product.get('name', product.get('display_name', 'N/A'))
            extracted['price'] = f"₹{product.get('price', product.get('mrp', 'N/A'))}"
            extracted['unit'] = product.get('unit', product.get('unit_type', 'N/A'))
            extracted['brand'] = product.get('brand', product.get('brand_name', 'N/A'))
            extracted['category'] = product.get('category', product.get('category_name', 'N/A'))
            
            # Try to get rating
            if 'rating' in product:
                extracted['rating'] = str(product['rating'])
            elif 'average_rating' in product:
                extracted['rating'] = str(product['average_rating'])
                        
        except Exception as e:
            logger.debug(f"Error extracting from mobile API: {e}")
        
        return extracted
    
    def _save_failed_url(self, product_id, url, status_code, error_message):
        """Save failed URL to database"""
        existing = sync_failed_urls_collection.find_one({
            "job_id": self.job_id,
            "res_id": str(product_id)
        })
        
        if existing:
            sync_failed_urls_collection.update_one(
                {"job_id": self.job_id, "res_id": str(product_id)},
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
                res_id=str(product_id),
                url=url,
                status_code=status_code,
                error_message=error_message,
                retry_count=0
            )
            sync_failed_urls_collection.insert_one(failed_url.dict())
    
    def scrape_batch(self, product_ids, iteration=1):
        """Scrape multiple product IDs with workers"""
        logger.info(f"Starting Blinkit iteration {iteration} with {len(product_ids)} URLs and {self.num_workers} workers")
        
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
        
        # Use fewer workers and longer delays for Blinkit
        with ThreadPoolExecutor(max_workers=min(self.num_workers, 2)) as executor:
            future_to_id = {executor.submit(self.scrape_product, product_id): product_id for product_id in product_ids}
            
            for future in as_completed(future_to_id):
                product_id = future_to_id[future]
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
                    
                    # Add delay between processing results
                    time.sleep(random.uniform(1, 2))
                    
                except Exception as e:
                    logger.error(f"Worker error for {product_id}: {e}")
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
        
        logger.info(f"Blinkit iteration {iteration} completed: {successful} successful, {failed} failed")
        return successful, failed
    
    def run_with_retries(self, product_ids, max_iterations=3):
        """Run scraping with retry logic"""
        current_ids = product_ids
        
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
                    "job_id": self.job_id,
                    "status": "success"
                })
                successful_ids_set = {doc["res_id"] for doc in successful_docs}
                
                current_ids = list(failed_ids_set - successful_ids_set)
                
                logger.info(f"Retrying {len(current_ids)} failed URLs")
                
                if not current_ids:
                    logger.info("All URLs succeeded, no need to retry")
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
        
        logger.info(f"Blinkit scraping job {self.job_id} completed: {successful_urls} successful, {failed_urls} failed")