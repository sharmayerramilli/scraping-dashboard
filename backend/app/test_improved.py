#!/usr/bin/env python3
"""Test improved scraper with title extraction"""

import requests
from bs4 import BeautifulSoup
import time

def test_improved_extraction():
    """Test the improved extraction logic"""
    
    url = "https://zoma.to/r/20752747"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    session = requests.Session()
    session.headers.update(headers)
    
    try:
        response = session.get(url, timeout=15, allow_redirects=True)
        print(f"Status: {response.status_code}")
        print(f"Final URL: {response.url}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Test title extraction
            title = soup.find('title')
            if title:
                title_text = title.get_text(strip=True)
                print(f"Title: {title_text}")
                
                # Extract name
                if 'zomato' in title_text.lower():
                    name_part = title_text.split('|')[0].strip()  # Remove "| Zomato"
                    name_part = name_part.split(',')[0].strip()   # Remove location
                    print(f"✅ Extracted Name: {name_part}")
                    
                    # Extract location
                    if ',' in title_text and '|' in title_text:
                        location_part = title_text.split('|')[0].strip()
                        if ',' in location_part:
                            location = location_part.split(',', 1)[1].strip()
                            print(f"✅ Extracted Location: {location}")
            
            # Look for other data in meta tags
            og_title = soup.find('meta', property='og:title')
            if og_title:
                print(f"OG Title: {og_title.get('content', '')}")
            
            description = soup.find('meta', {'name': 'description'})
            if description:
                desc_text = description.get('content', '')
                print(f"Description: {desc_text}")
                
        else:
            print(f"❌ Failed with status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_improved_extraction()