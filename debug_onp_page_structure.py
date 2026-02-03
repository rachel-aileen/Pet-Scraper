#!/usr/bin/env python3

import requests
from bs4 import BeautifulSoup
import re

def debug_onp_page_structure():
    """Debug the Only Natural Pet page structure to find missing data"""
    
    url = "https://www.onlynaturalpet.com/products/only-natural-pet-powerpate-turkey-chicken-dinner?variant=40711732002852"
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        page_source = str(soup)
        
        print("=== DEBUGGING ONLY NATURAL PET PAGE STRUCTURE ===")
        
        # 1. Search for ingredients
        print("\n=== INGREDIENTS SEARCH ===")
        
        # Look for the full ingredient list we know exists
        full_ingredients = "Turkey, Chicken, Turkey Broth, Chicken Broth, Turkey Liver, Peas, Natural Flavor, Agar-Agar, Tricalcium Phosphate, Carrots, Green Beans, Ground Whole Flaxseed, Eggs, Clams, Cranberries, Blueberries, Salmon Oil (Preserved With Mixed Tocopherols), Olive Oil, Salt, Sodium Tripolyphosphate, New Zealand Green Mussel, Calcium Sulfate, Potassium Chloride, Turmeric, Kelp, Calcium Carbonate, Choline Chloride, Betaine, Zinc Proteinate, Iron Proteinate, Niacin, Vitamin E Supplement, Thiamine Mononitrate, Copper Proteinate, Manganese Proteinate, Sodium Selenite, Calcium Pantothenate, Vitamin A Supplement, Riboflavin, Pyridoxine Hydrochloride, Biotin, Vitamin B12 Supplement, Calcium Iodate, Vitamin D3 Supplement, Folic Acid"
        
        if full_ingredients in page_source:
            print("✅ Full ingredients list found in page source!")
            # Find context around it
            pos = page_source.find(full_ingredients)
            context = page_source[max(0, pos-200):pos+len(full_ingredients)+200]
            print(f"Context: {context[:300]}...")
        else:
            print("❌ Full ingredients list not found as one block")
            
            # Look for individual ingredients that are missing
            missing_ingredients = ["Sodium Tripolyphosphate", "New Zealand Green Mussel", "Vitamin E Supplement", "Folic Acid"]
            for ingredient in missing_ingredients:
                if ingredient in page_source:
                    print(f"✅ Found '{ingredient}' in page")
                else:
                    print(f"❌ Missing '{ingredient}' in page")
        
        # Look for ingredient patterns
        ingredient_patterns = [
            r'INGREDIENTS[:\s]*([^<>]*(?:Turkey|Chicken)[^<>]*)',
            r'ingredients[:\s]*([^<>]*(?:Turkey|Chicken)[^<>]*)',
            r'"ingredients"[:\s]*"([^"]*)"',
        ]
        
        for i, pattern in enumerate(ingredient_patterns):
            matches = re.findall(pattern, page_source, re.IGNORECASE | re.DOTALL)
            print(f"Ingredient pattern {i+1}: {len(matches)} matches")
            for j, match in enumerate(matches[:2]):
                print(f"  Match {j+1}: {match[:100]}...")
        
        # 2. Search for guaranteed analysis
        print("\n=== GUARANTEED ANALYSIS SEARCH ===")
        
        ga_text = "Crude Protein (min) .............................................8.0%"
        if ga_text in page_source:
            print("✅ Guaranteed analysis found in page source!")
            pos = page_source.find(ga_text)
            context = page_source[max(0, pos-200):pos+500]
            print(f"Context: {context}")
        else:
            print("❌ Exact guaranteed analysis not found")
            
            # Look for individual components
            ga_components = ["8.0%", "5.0%", "0.75%", "78.0%"]
            for component in ga_components:
                if component in page_source:
                    print(f"✅ Found '{component}' in page")
                    # Find context
                    pos = page_source.find(component)
                    context = page_source[max(0, pos-50):pos+100]
                    print(f"  Context: {context}")
                else:
                    print(f"❌ Missing '{component}' in page")
        
        # Look for guaranteed analysis patterns
        ga_patterns = [
            r'GUARANTEED ANALYSIS[:\s]*([^<>]*(?:Protein|Fat|Fiber|Moisture)[^<>]*)',
            r'guaranteed analysis[:\s]*([^<>]*(?:Protein|Fat|Fiber|Moisture)[^<>]*)',
            r'Crude Protein[^<>]*?(\d+(?:\.\d+)?%)',
        ]
        
        for i, pattern in enumerate(ga_patterns):
            matches = re.findall(pattern, page_source, re.IGNORECASE | re.DOTALL)
            print(f"GA pattern {i+1}: {len(matches)} matches")
            for j, match in enumerate(matches[:2]):
                print(f"  Match {j+1}: {match[:100]}...")
        
        # 3. Search for calories
        print("\n=== CALORIE SEARCH ===")
        
        calorie_text_1 = "1,214 kcal/kg"
        calorie_text_2 = "34.4 kcal/oz"
        
        if calorie_text_1 in page_source:
            print(f"✅ Found '{calorie_text_1}' in page")
            pos = page_source.find(calorie_text_1)
            context = page_source[max(0, pos-100):pos+200]
            print(f"  Context: {context}")
        else:
            print(f"❌ Missing '{calorie_text_1}' in page")
        
        if calorie_text_2 in page_source:
            print(f"✅ Found '{calorie_text_2}' in page")
            pos = page_source.find(calorie_text_2)
            context = page_source[max(0, pos-100):pos+200]
            print(f"  Context: {context}")
        else:
            print(f"❌ Missing '{calorie_text_2}' in page")
        
        # Look for calorie patterns
        calorie_patterns = [
            r'(\d+,?\d*)\s*kcal/kg',
            r'(\d+(?:\.\d+)?)\s*kcal/oz',
            r'CALORIE CONTENT[^<>]*?(\d+,?\d*\s*kcal/kg[^<>]*?\d+(?:\.\d+)?\s*kcal/oz)',
        ]
        
        for i, pattern in enumerate(calorie_patterns):
            matches = re.findall(pattern, page_source, re.IGNORECASE)
            print(f"Calorie pattern {i+1}: {len(matches)} matches")
            for j, match in enumerate(matches[:3]):
                print(f"  Match {j+1}: {match}")
        
        # 4. Look for structured data (JSON-LD)
        print("\n=== STRUCTURED DATA SEARCH ===")
        
        json_scripts = soup.find_all('script', type='application/ld+json')
        print(f"Found {len(json_scripts)} JSON-LD scripts")
        
        for i, script in enumerate(json_scripts):
            if script.string:
                content = script.string[:200]
                print(f"Script {i+1}: {content}...")
                
                # Look for product data
                if 'Product' in script.string:
                    print(f"  Contains Product data")
                if 'ingredients' in script.string.lower():
                    print(f"  Contains ingredients data")
        
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    debug_onp_page_structure()
