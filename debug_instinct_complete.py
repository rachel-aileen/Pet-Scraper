#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import re

def debug_instinct_complete():
    url = "https://instinctpetfood.com/products/raw-boost-healthy-weight-chicken-dry-cat-food/"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        print("=== DEBUGGING INSTINCT COMPLETE INGREDIENT LIST ===")
        print(f"URL: {url}")
        print(f"Status: {response.status_code}")
        print()
        
        page_text = soup.get_text()
        
        # Find "Citric Acid" and see what comes after
        citric_acid_pos = page_text.find("Citric Acid")
        if citric_acid_pos != -1:
            print("=== TEXT AROUND 'CITRIC ACID' ===")
            start = max(0, citric_acid_pos - 200)
            end = min(len(page_text), citric_acid_pos + 500)
            context = page_text[start:end]
            print(f"Context: '{context}'")
            print()
            
            # Show what comes after Citric Acid
            after_citric = page_text[citric_acid_pos:citric_acid_pos + 1000]
            print(f"After Citric Acid: '{after_citric}'")
            print()
        
        # Look specifically for the complete ingredient pattern
        print("=== COMPLETE INGREDIENT PATTERN MATCHES ===")
        complete_pattern = r'(Chicken, Chicken Meal, Chickpeas.*?(?:Extract|Oil|Product|Bisulfite)\.?)'
        matches = re.findall(complete_pattern, page_text, re.IGNORECASE | re.DOTALL)
        
        for i, match in enumerate(matches):
            print(f"Match {i+1}:")
            print(f"Length: {len(match)}")
            print(f"Comma count: {match.count(',')}")
            print(f"First 100 chars: '{match[:100]}...'")
            print(f"Last 100 chars: '...{match[-100:]}'")
            print()
        
        # Try the exact pattern from the current code
        print("=== OUR INGREDIENTS PATTERN TEST ===")
        our_pattern = r'our\s+ingredients[:\s]*([A-Z][^.]*?(?:extract|supplement|acid|chloride|bisulfite|oil|product)\.?)'
        our_matches = re.findall(our_pattern, page_text, re.IGNORECASE | re.DOTALL)
        
        for i, match in enumerate(our_matches):
            print(f"Our Ingredients Match {i+1}:")
            print(f"Length: {len(match)}")
            print(f"Comma count: {match.count(',')}")
            print(f"Content: '{match}'")
            print()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_instinct_complete() 