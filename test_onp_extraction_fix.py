#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import re
import html

def test_onp_extraction_methods():
    """Test different extraction methods for Only Natural Pet"""
    
    url = "https://www.onlynaturalpet.com/products/only-natural-pet-powerpate-turkey-chicken-dinner?variant=40711732002852"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        page_source = str(soup)
        
        print("=== TESTING ONLY NATURAL PET EXTRACTION METHODS ===")
        
        # 1. Test ingredient extraction
        print("\n=== INGREDIENTS EXTRACTION TEST ===")
        
        # Method 1: Look for the exact HTML-encoded pattern
        ingredient_pattern = r'INGREDIENTS[^:]*:\s*([^<]*(?:Turkey|Chicken)[^<]*?Folic Acid)'
        matches = re.findall(ingredient_pattern, page_source, re.IGNORECASE | re.DOTALL)
        
        print(f"HTML-encoded pattern matches: {len(matches)}")
        for i, match in enumerate(matches):
            # Decode HTML entities
            decoded = html.unescape(match)
            print(f"Match {i+1} (decoded): {decoded[:100]}...")
            
            # Count ingredients
            ingredient_count = decoded.count(',') + 1
            print(f"  Ingredient count: {ingredient_count}")
            
            if ingredient_count > 40:
                print(f"  ✅ This looks like the complete ingredient list!")
            else:
                print(f"  ❌ This looks incomplete")
        
        # Method 2: Look in JSON-LD structured data
        print(f"\n--- JSON-LD Method ---")
        json_scripts = soup.find_all('script', type='application/ld+json')
        for i, script in enumerate(json_scripts):
            if script.string and 'ingredients' in script.string.lower():
                print(f"JSON-LD script {i+1} contains ingredients")
                # Look for ingredients in the JSON
                import json
                try:
                    data = json.loads(script.string)
                    # Navigate the JSON structure to find ingredients
                    if isinstance(data, dict):
                        # Look for ingredients at various levels
                        ingredients_found = find_ingredients_in_json(data)
                        if ingredients_found:
                            print(f"  Found ingredients in JSON: {ingredients_found[:100]}...")
                except:
                    pass
        
        # 2. Test guaranteed analysis extraction
        print("\n=== GUARANTEED ANALYSIS EXTRACTION TEST ===")
        
        # Method 1: Look for the exact pattern with HTML encoding
        ga_pattern = r'GUARANTEED ANALYSIS[^:]*:[^<]*?Crude Protein[^<]*?8\.0%[^<]*?Crude Fat[^<]*?5\.0%[^<]*?Crude Fiber[^<]*?0\.75%[^<]*?Moisture[^<]*?78\.0%'
        ga_matches = re.findall(ga_pattern, page_source, re.IGNORECASE | re.DOTALL)
        
        print(f"GA HTML pattern matches: {len(ga_matches)}")
        for i, match in enumerate(ga_matches):
            decoded = html.unescape(match)
            print(f"GA Match {i+1}: {decoded}")
        
        # Method 2: Extract individual components
        print(f"\n--- Individual Component Method ---")
        components = {}
        
        # Look for each component separately
        protein_match = re.search(r'Crude Protein[^<]*?(\d+(?:\.\d+)?%)', page_source, re.IGNORECASE)
        if protein_match:
            components['protein'] = protein_match.group(1)
            print(f"Protein: {components['protein']}")
        
        fat_match = re.search(r'Crude Fat[^<]*?(\d+(?:\.\d+)?%)', page_source, re.IGNORECASE)
        if fat_match:
            components['fat'] = fat_match.group(1)
            print(f"Fat: {components['fat']}")
        
        fiber_match = re.search(r'Crude Fiber[^<]*?(\d+(?:\.\d+)?%)', page_source, re.IGNORECASE)
        if fiber_match:
            components['fiber'] = fiber_match.group(1)
            print(f"Fiber: {components['fiber']}")
        
        moisture_match = re.search(r'Moisture[^<]*?(\d+(?:\.\d+)?%)', page_source, re.IGNORECASE)
        if moisture_match:
            components['moisture'] = moisture_match.group(1)
            print(f"Moisture: {components['moisture']}")
        
        if len(components) >= 3:
            ga_result = f"Crude Protein (min): {components.get('protein', 'N/A')}, Crude Fat (min): {components.get('fat', 'N/A')}, Crude Fiber (max): {components.get('fiber', 'N/A')}, Moisture (max): {components.get('moisture', 'N/A')}"
            print(f"✅ Reconstructed GA: {ga_result}")
        
        # 3. Test calorie extraction
        print("\n=== CALORIE EXTRACTION TEST ===")
        
        # Look for both calorie values
        calorie_pattern_1 = r'(\d+,?\d*)\s*kcal/kg'
        calorie_pattern_2 = r'(\d+(?:\.\d+)?)\s*kcal/oz'
        
        kg_matches = re.findall(calorie_pattern_1, page_source, re.IGNORECASE)
        oz_matches = re.findall(calorie_pattern_2, page_source, re.IGNORECASE)
        
        print(f"kcal/kg matches: {kg_matches}")
        print(f"kcal/oz matches: {oz_matches}")
        
        # Look for the complete calorie content section
        calorie_section_pattern = r'CALORIE CONTENT[^<]*?(\d+,?\d*\s*kcal/kg[^<]*?\d+(?:\.\d+)?\s*kcal/oz)'
        calorie_section_matches = re.findall(calorie_section_pattern, page_source, re.IGNORECASE | re.DOTALL)
        
        print(f"Complete calorie section matches: {len(calorie_section_matches)}")
        for i, match in enumerate(calorie_section_matches):
            decoded = html.unescape(match)
            print(f"Calorie section {i+1}: {decoded}")
        
    except Exception as e:
        print(f"ERROR: {e}")

def find_ingredients_in_json(data, path=""):
    """Recursively search for ingredients in JSON data"""
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() == 'ingredients' and isinstance(value, str) and len(value) > 50:
                return value
            elif isinstance(value, (dict, list)):
                result = find_ingredients_in_json(value, f"{path}.{key}")
                if result:
                    return result
    elif isinstance(data, list):
        for i, item in enumerate(data):
            if isinstance(item, (dict, list)):
                result = find_ingredients_in_json(item, f"{path}[{i}]")
                if result:
                    return result
    return None

if __name__ == "__main__":
    test_onp_extraction_methods()
