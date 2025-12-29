#!/usr/bin/env python3
"""Debug script to examine Zomato page content"""

import requests
from bs4 import BeautifulSoup
import json

def debug_page_content():
    url = "https://zoma.to/r/20752747"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
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
    
    try:
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        print(f"Status Code: {response.status_code}")
        print(f"Final URL: {response.url}")
        print(f"Content Length: {len(response.content)} bytes")
        print("=" * 50)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Check title
            title = soup.find('title')
            if title:
                print(f"Title: {title.get_text(strip=True)}")
            
            # Look for JSON-LD scripts
            scripts = soup.find_all('script', type='application/ld+json')
            print(f"Found {len(scripts)} JSON-LD scripts")
            
            for i, script in enumerate(scripts):
                try:
                    data = json.loads(script.string)
                    print(f"JSON-LD {i+1}: {json.dumps(data, indent=2)[:500]}...")
                except:
                    print(f"JSON-LD {i+1}: Failed to parse")
            
            # Look for common selectors
            selectors_to_check = [
                'h1',
                '[data-testid="restaurant-name"]',
                '.restaurant-name',
                'h1[class*="sc-7kepeu"]',
                'meta[property="og:title"]'
            ]
            
            print("\nChecking common selectors:")
            for selector in selectors_to_check:
                elements = soup.select(selector)
                if elements:
                    for elem in elements[:3]:  # Show first 3 matches
                        text = elem.get_text(strip=True) if hasattr(elem, 'get_text') else elem.get('content', '')
                        print(f"  {selector}: {text}")
            
            # Save a sample of the HTML for inspection
            with open('debug_page.html', 'w', encoding='utf-8') as f:
                f.write(str(soup.prettify())[:10000])  # First 10KB
            print("\nSaved first 10KB of HTML to debug_page.html")
            
        else:
            print(f"Request failed with status {response.status_code}")
            print(f"Response content: {response.text[:500]}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_page_content()