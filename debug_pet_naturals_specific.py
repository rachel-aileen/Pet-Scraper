#!/usr/bin/env python3

from selenium_scraper import _get_browser
import re
import time

def debug_pet_naturals_page():
    """Debug the Pet Naturals page to find where ingredients are hidden"""
    url = "https://www.target.com/p/pet-naturals-daily-multivitamin-for-cats-everyday-health-support-chicken-liver-flavor-30-count/-/A-84077896#lnk=sametab"
    
    driver = _get_browser()
    driver.get(url)
    time.sleep(3)
    
    print("=== DEBUGGING PET NATURALS PAGE ===")
    
    # 1. Check for JavaScript data
    print("\n1. Checking JavaScript window objects...")
    js_data = driver.execute_script("""
        try {
            let results = [];
            
            // Check __NEXT_DATA__
            if (window.__NEXT_DATA__) {
                const nextData = JSON.stringify(window.__NEXT_DATA__);
                if (nextData.includes('nutrition_facts')) {
                    results.push('Found nutrition_facts in __NEXT_DATA__');
                    const match = nextData.match(/"nutrition_facts":\\s*\\{[^}]*"ingredients":\\s*"([^"]{50,})"/);
                    if (match) results.push('Ingredients found: ' + match[1].substring(0, 100) + '...');
                }
            }
            
            // Check all script tags
            const scripts = document.querySelectorAll('script');
            for (let script of scripts) {
                if (script.textContent && script.textContent.includes('nutrition_facts')) {
                    results.push('Found nutrition_facts in script tag');
                    const match = script.textContent.match(/"nutrition_facts":\\s*\\{[^}]*"ingredients":\\s*"([^"]{50,})"/);
                    if (match) results.push('Script ingredients: ' + match[1].substring(0, 100) + '...');
                }
            }
            
            return results.join('\\n');
        } catch (e) {
            return 'Error: ' + e.toString();
        }
    """)
    print(js_data)
    
    # 2. Search page source for any mention of vitamins/supplements
    print("\n2. Searching page source for vitamin/supplement content...")
    page_source = driver.page_source
    
    # Look for supplement-specific patterns
    vitamin_patterns = [
        r'vitamin[^,]*?for Cats[^,]*?Everyday Health Support[^,]*?Chicken Liver Flavor[^,]*?30 count[^.]*',
        r'chicken liver[^.]*vitamin[^.]*',
        r'daily multivitamin[^.]*ingredient[^.]*',
        r'supplement[^.]*ingredient[^.]*',
        r'Pet Naturals[^.]*ingredient[^.]*'
    ]
    
    for i, pattern in enumerate(vitamin_patterns):
        matches = re.finditer(pattern, page_source, re.IGNORECASE | re.DOTALL)
        for match in matches:
            content = match.group(0)[:200]
            print(f"Pattern {i+1} match: {content}...")
    
    # 3. Look for any text that contains "chicken liver" or vitamin information
    print("\n3. Looking for chicken liver or vitamin information...")
    chicken_liver_pattern = r'chicken liver[^.]{50,200}'
    matches = re.finditer(chicken_liver_pattern, page_source, re.IGNORECASE)
    for match in matches:
        print(f"Chicken liver context: {match.group(0)}...")
    
    # 4. Check for any expandable sections or hidden content
    print("\n4. Checking for expandable sections...")
    expandable_elements = driver.execute_script("""
        const elements = document.querySelectorAll('[data-test*="expand"], [aria-expanded], .accordion, .collapse, details');
        let results = [];
        for (let elem of elements) {
            results.push(elem.outerHTML.substring(0, 200));
        }
        return results.join('\\n---\\n');
    """)
    print(f"Expandable elements: {expandable_elements}")
    
    # 5. Try clicking on any possible tabs or sections
    print("\n5. Looking for tabs or sections that might contain ingredients...")
    try:
        tabs = driver.find_elements("xpath", "//*[contains(text(), 'Details') or contains(text(), 'Info') or contains(text(), 'Label') or contains(text(), 'Nutrition')]")
        for tab in tabs:
            print(f"Found potential tab: {tab.text} - {tab.tag_name}")
            try:
                tab.click()
                time.sleep(1)
                # Check if ingredients appeared
                new_source = driver.page_source
                if 'vitamin' in new_source.lower() and 'chicken liver' in new_source.lower():
                    print("Found vitamin content after clicking!")
                    vitamin_match = re.search(r'vitamin.*chicken liver.*', new_source, re.IGNORECASE)
                    if vitamin_match:
                        print(f"Vitamin info: {vitamin_match.group(0)[:300]}...")
            except:
                pass
    except Exception as e:
        print(f"Tab clicking failed: {e}")
    
    print("\n=== DEBUG COMPLETE ===")

if __name__ == "__main__":
    debug_pet_naturals_page() 