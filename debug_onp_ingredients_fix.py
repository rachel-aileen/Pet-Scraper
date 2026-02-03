#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import re
import html

def debug_onp_ingredients_fix():
    """Debug the Only Natural Pet ingredient extraction to find the complete list"""
    
    url = "https://www.onlynaturalpet.com/products/only-natural-pet-powerpate-turkey-chicken-dinner?variant=40711732002852"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        page_source = str(soup)
        
        print("=== DEBUGGING ONLY NATURAL PET INGREDIENT EXTRACTION ===")
        
        # Test the patterns I'm using
        print("\n=== TESTING CURRENT PATTERNS ===")
        
        patterns = [
            r'"ingredients":\s*"[^"]*INGREDIENTS[^:]*:\s*([^"]*Turkey[^"]*Folic Acid[^"]*)"',
            r'INGREDIENTS[^:]*:\s*([A-Z][^<]*?(?:Turkey|Chicken)[^<]*?Folic Acid)',
        ]
        
        for i, pattern in enumerate(patterns):
            print(f"\nPattern {i+1}: {pattern}")
            matches = re.findall(pattern, page_source, re.IGNORECASE | re.DOTALL)
            print(f"Matches: {len(matches)}")
            
            for j, match in enumerate(matches[:2]):
                decoded = html.unescape(match)
                cleaned = re.sub(r'\\u[0-9a-fA-F]{4}', '', decoded)
                cleaned = re.sub(r'\\[rn]', ' ', cleaned)
                cleaned = re.sub(r'\s+', ' ', cleaned)
                cleaned = cleaned.strip()
                
                print(f"  Match {j+1} (first 200 chars): {cleaned[:200]}...")
                print(f"  Match {j+1} ingredient count: {cleaned.count(',') + 1}")
        
        # Look for the exact complete ingredient list we know exists
        print("\n=== LOOKING FOR COMPLETE INGREDIENT LIST ===")
        
        complete_ingredients = "Turkey, Chicken, Turkey Broth, Chicken Broth, Turkey Liver, Peas, Natural Flavor, Agar-Agar, Tricalcium Phosphate, Carrots, Green Beans, Ground Whole Flaxseed, Eggs, Clams, Cranberries, Blueberries, Salmon Oil (Preserved With Mixed Tocopherols), Olive Oil, Salt, Sodium Tripolyphosphate, New Zealand Green Mussel, Calcium Sulfate, Potassium Chloride, Turmeric, Kelp, Calcium Carbonate, Choline Chloride, Betaine, Zinc Proteinate, Iron Proteinate, Niacin, Vitamin E Supplement, Thiamine Mononitrate, Copper Proteinate, Manganese Proteinate, Sodium Selenite, Calcium Pantothenate, Vitamin A Supplement, Riboflavin, Pyridoxine Hydrochloride, Biotin, Vitamin B12 Supplement, Calcium Iodate, Vitamin D3 Supplement, Folic Acid"
        
        if complete_ingredients in page_source:
            print("✅ Complete ingredient list found in page source!")
            
            # Find the context around it
            pos = page_source.find(complete_ingredients)
            start_context = page_source[max(0, pos-300):pos]
            end_context = page_source[pos+len(complete_ingredients):pos+len(complete_ingredients)+100]
            
            print(f"Context before: ...{start_context[-100:]}")
            print(f"Context after: {end_context[:100]}...")
            
            # Create a pattern to match this exact structure
            # Look for what comes before the ingredient list
            before_patterns = [
                r'INGREDIENTS[^:]*:\s*' + re.escape(complete_ingredients[:50]),
                r'"ingredients"[^:]*:\s*[^"]*' + re.escape(complete_ingredients[:50]),
            ]
            
            for i, pattern in enumerate(before_patterns):
                matches = re.findall(pattern, page_source, re.IGNORECASE)
                print(f"Before pattern {i+1}: {len(matches)} matches")
        else:
            print("❌ Complete ingredient list not found as exact string")
            
            # Look for parts of it
            parts = ["Turkey, Chicken, Turkey Broth", "Folic Acid"]
            for part in parts:
                if part in page_source:
                    print(f"✅ Found part: '{part}'")
                    pos = page_source.find(part)
                    context = page_source[max(0, pos-100):pos+len(part)+100]
                    print(f"  Context: {context}")
                else:
                    print(f"❌ Missing part: '{part}'")
        
        # Try a different approach - look for metafields that contain the ingredients
        print("\n=== METAFIELDS APPROACH ===")
        
        # Look for the ingredients in JSON metafields
        metafield_pattern = r'"ingredients":\s*"([^"]*Turkey[^"]*Folic Acid[^"]*)"'
        metafield_matches = re.findall(metafield_pattern, page_source, re.IGNORECASE | re.DOTALL)
        
        print(f"Metafield matches: {len(metafield_matches)}")
        for i, match in enumerate(metafield_matches):
            decoded = html.unescape(match)
            # Clean up HTML encoding
            cleaned = re.sub(r'\\u[0-9a-fA-F]{4}', '', decoded)
            cleaned = re.sub(r'\\/', '/', cleaned)
            cleaned = re.sub(r'\\[rn]', ' ', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned)
            
            print(f"Metafield {i+1} (first 200 chars): {cleaned[:200]}...")
            print(f"Metafield {i+1} ingredient count: {cleaned.count(',') + 1}")
            
            # Look for the INGREDIENTS: part
            if 'INGREDIENTS:' in cleaned:
                ingredients_part = cleaned.split('INGREDIENTS:', 1)[1]
                # Find where it ends (before GUARANTEED ANALYSIS or similar)
                end_markers = ['GUARANTEED ANALYSIS', 'CALORIE CONTENT', 'AAFCO']
                for marker in end_markers:
                    if marker in ingredients_part:
                        ingredients_part = ingredients_part.split(marker)[0]
                        break
                
                ingredients_part = ingredients_part.strip()
                print(f"  Extracted ingredients part: {ingredients_part[:200]}...")
                print(f"  Extracted ingredient count: {ingredients_part.count(',') + 1}")
                
                if ingredients_part.count(',') > 40:
                    print(f"  ✅ This looks like the complete list!")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    debug_onp_ingredients_fix()
