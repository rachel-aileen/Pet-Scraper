#!/usr/bin/env python3

import requests
import json

def test_only_natural_pet():
    """Test what the scraper currently extracts from Only Natural Pet"""
    
    url = "https://www.onlynaturalpet.com/products/only-natural-pet-powerpate-turkey-chicken-dinner?variant=40711732002852"
    
    try:
        # Test the scraper endpoint
        response = requests.post(
            'http://localhost:8000/scrape',
            json={'url': url},
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            print("=== ONLY NATURAL PET CURRENT EXTRACTION ===")
            print(f"URL: {url}")
            print()
            
            # Check what's currently being extracted
            print("CURRENT RESULTS:")
            print(f"Name: {data.get('name', 'None')}")
            print(f"Brand: {data.get('brand', 'None')}")
            print(f"Size: {data.get('size', 'None')}")
            print(f"Price: {data.get('price', 'None')}")
            print(f"Life Stage: {data.get('lifeStage', 'None')}")
            print(f"Texture: {data.get('texture', 'None')}")
            print()
            
            # Check ingredients
            ingredients = data.get('ingredients', [])
            print(f"Ingredients ({len(ingredients)} items):")
            if isinstance(ingredients, list):
                for i, ingredient in enumerate(ingredients[:10]):  # Show first 10
                    print(f"  {i+1}. {ingredient}")
                if len(ingredients) > 10:
                    print(f"  ... and {len(ingredients) - 10} more")
            else:
                print(f"  {ingredients}")
            print()
            
            # Check guaranteed analysis
            ga = data.get('guaranteedAnalysis')
            print(f"Guaranteed Analysis: {ga}")
            print()
            
            # Check nutritional info
            ni = data.get('nutritionalInfo')
            print(f"Nutritional Info: {ni}")
            print()
            
            # Expected vs Actual comparison
            print("=== EXPECTED vs ACTUAL ===")
            print("Expected Ingredients: Turkey, Chicken, Turkey Broth, Chicken Broth, Turkey Liver, Peas, Natural Flavor, Agar-Agar, Tricalcium Phosphate, Carrots, Green Beans, Ground Whole Flaxseed, Eggs, Clams, Cranberries, Blueberries, Salmon Oil (Preserved With Mixed Tocopherols), Olive Oil, Salt, Sodium Tripolyphosphate, New Zealand Green Mussel, Calcium Sulfate, Potassium Chloride, Turmeric, Kelp, Calcium Carbonate, Choline Chloride, Betaine, Zinc Proteinate, Iron Proteinate, Niacin, Vitamin E Supplement, Thiamine Mononitrate, Copper Proteinate, Manganese Proteinate, Sodium Selenite, Calcium Pantothenate, Vitamin A Supplement, Riboflavin, Pyridoxine Hydrochloride, Biotin, Vitamin B12 Supplement, Calcium Iodate, Vitamin D3 Supplement, Folic Acid")
            print(f"Actual Ingredients: {ingredients}")
            print()
            
            print("Expected Guaranteed Analysis: Crude Protein (min) 8.0%, Crude Fat (min) 5.0%, Crude Fiber (max) 0.75%, Moisture (max) 78.0%")
            print(f"Actual Guaranteed Analysis: {ga}")
            print()
            
            print("Expected Calories: 1,214 kcal/kg, 34.4 kcal/oz")
            print(f"Actual Calories: {ni}")
            print()
            
            # Assessment
            ingredients_correct = isinstance(ingredients, list) and len(ingredients) > 20 and "Turkey" in str(ingredients)
            ga_correct = ga and "8.0%" in ga and "5.0%" in ga
            calories_correct = ni and isinstance(ni, dict) and "34.4" in str(ni.get('calories', ''))
            
            print("=== ASSESSMENT ===")
            print(f"Ingredients: {'✅ GOOD' if ingredients_correct else '❌ MISSING/INCOMPLETE'}")
            print(f"Guaranteed Analysis: {'✅ GOOD' if ga_correct else '❌ MISSING/INCORRECT'}")
            print(f"Calories: {'✅ GOOD' if calories_correct else '❌ MISSING/INCORRECT'}")
            
            if not (ingredients_correct and ga_correct and calories_correct):
                print("\n🚨 ISSUES FOUND - Need to debug extraction methods")
            else:
                print("\n🎉 ALL DATA CORRECT!")
                
        else:
            print(f"ERROR: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_only_natural_pet()
