#!/usr/bin/env python3
"""Test scraper with manual verification"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time
import re

def test_manual_scraping():
    """Test scraping with manual verification"""
    
    # Test restaurant ID from your example
    res_id = "20752747"
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        # Try the URL that should work
        url = f"https://zoma.to/r/{res_id}"
        print(f"Testing URL: {url}")
        
        driver.get(url)
        time.sleep(5)
        
        print(f"Final URL: {driver.current_url}")
        print(f"Page Title: {driver.title}")
        
        # Check if we got redirected to a valid page
        if "zomato.com" in driver.current_url:
            # Try to extract name from title
            title_text = driver.title
            if title_text and 'zomato' in title_text.lower():
                name_part = title_text.split('|')[0].strip()
                if ',' in name_part:
                    name = name_part.split(',')[0].strip()
                    address = name_part.split(',', 1)[1].strip()
                    print(f"✅ Extracted Name: {name}")
                    print(f"✅ Extracted Address: {address}")
                else:
                    print(f"✅ Extracted Name: {name_part}")
            
            # Look for cost in page source
            page_source = driver.page_source
            cost_patterns = [
                r'₹\d+\s*for\s*one\s*order',
                r'₹\d+\s*for\s*two',
                r'Average\s*Cost[^₹]*₹\d+[^\n]*'
            ]
            
            for pattern in cost_patterns:
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                if matches:
                    print(f"✅ Found Cost: {matches[0]}")
                    break
            else:
                print("❌ No cost information found")
                
        else:
            print("❌ Failed to reach Zomato page")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    test_manual_scraping()