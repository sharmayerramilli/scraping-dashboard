#!/usr/bin/env python3
"""Simple test to check Zomato scraping"""

import requests
from bs4 import BeautifulSoup
import time

def test_zomato_access():
    """Test different approaches to access Zomato"""
    
    # Test URLs
    test_urls = [
        "https://zoma.to/r/20752747",
        "https://www.zomato.com/ncr/meal2heal-vasant-kunj-new-delhi"
    ]
    
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
    
    for url in test_urls:
        print(f"\n🔍 Testing: {url}")
        try:
            response = session.get(url, timeout=15, allow_redirects=True)
            print(f"Status: {response.status_code}")
            print(f"Final URL: {response.url}")
            print(f"Content-Type: {response.headers.get('content-type', 'Unknown')}")
            print(f"Content-Length: {len(response.content)} bytes")
            
            if response.status_code == 200:
                # Try to parse with different encodings
                for encoding in ['utf-8', 'latin-1', 'iso-8859-1']:
                    try:
                        response.encoding = encoding
                        soup = BeautifulSoup(response.text, 'html.parser')
                        title = soup.find('title')
                        if title:
                            title_text = title.get_text(strip=True)
                            print(f"Title ({encoding}): {title_text}")
                            
                            # Look for restaurant name in title
                            if title_text and 'zomato' not in title_text.lower():
                                name_part = title_text.split(',')[0].split('-')[0].split('|')[0].strip()
                                if len(name_part) > 2:
                                    print(f"✅ Extracted name: {name_part}")
                            break
                    except Exception as e:
                        print(f"Encoding {encoding} failed: {e}")
                        continue
            else:
                print(f"❌ Failed with status {response.status_code}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
        
        time.sleep(2)

if __name__ == "__main__":
    test_zomato_access()