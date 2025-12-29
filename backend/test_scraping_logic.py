#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import re

def test_scraping_without_db():
    """Test scraping logic without MongoDB"""
    
    def create_driver():
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    
    print("🔍 Testing Zomato Scraping...")
    driver = None
    try:
        driver = create_driver()
        url = "https://zoma.to/r/20752747"
        driver.get(url)
        time.sleep(5)
        
        title_text = driver.title
        name = "N/A"
        address = "N/A"
        cost = "N/A"
        
        if title_text and 'zomato' in title_text.lower():
            name_part = title_text.split('|')[0].strip()
            if ',' in name_part:
                name = name_part.split(',')[0].strip()
                address = name_part.split(',', 1)[1].strip()
            else:
                name = name_part
        
        # Extract cost
        try:
            page_text = driver.page_source
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
        
        print(f"✅ Zomato Scraping Result:")
        print(f"   Name: {name}")
        print(f"   Address: {address}")
        print(f"   Cost: {cost}")
        print(f"   URL: {driver.current_url}")
        
    except Exception as e:
        print(f"❌ Zomato scraping failed: {e}")
    finally:
        if driver:
            driver.quit()
    
    print("\n🔍 Testing Swiggy Scraping...")
    driver = None
    try:
        driver = create_driver()
        url = "https://www.swiggy.com/restaurants/-5916"
        driver.get(url)
        time.sleep(5)
        
        title_text = driver.title
        name = "N/A"
        address = "N/A"
        cost = "N/A"
        final_url = driver.current_url
        
        if title_text and 'swiggy' in title_text.lower():
            parts = title_text.split('|')
            if len(parts) >= 2:
                potential_name = parts[0].strip()
                if 'order food online' not in potential_name.lower() and len(potential_name) < 50:
                    name = potential_name
                if len(parts) >= 3:
                    address = parts[1].strip()
        
        # Extract address from URL
        if address == "N/A":
            url_parts = final_url.split('/')
            if len(url_parts) >= 4:
                city = url_parts[4] if len(url_parts) > 4 else ""
                restaurant_part = url_parts[-1] if url_parts else ""
                if '-rest' in restaurant_part:
                    slug_parts = restaurant_part.split('-rest')[0].split('-')
                    if len(slug_parts) > 1:
                        restaurant_name_words = name.lower().replace("'", "").split()
                        area_parts = []
                        for part in slug_parts:
                            if part.lower() not in restaurant_name_words:
                                area_parts.append(part)
                        
                        if area_parts:
                            area = ' '.join(area_parts[-2:] if len(area_parts) > 1 else area_parts).title()
                            if city:
                                address = f"{area}, {city.title()}"
                            else:
                                address = area
        
        # Extract cost
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
        
        print(f"✅ Swiggy Scraping Result:")
        print(f"   Name: {name}")
        print(f"   Address: {address}")
        print(f"   Cost: {cost}")
        print(f"   URL: {final_url}")
        
    except Exception as e:
        print(f"❌ Swiggy scraping failed: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    test_scraping_without_db()