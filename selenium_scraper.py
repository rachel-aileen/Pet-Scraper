#!/usr/bin/env python3

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import re
import atexit

# Global browser instance for performance (reuse instead of creating new ones)
_browser = None

def _get_browser():
    """Get or create a reusable browser instance for SPEED with session validation"""
    global _browser
    
    # Check if existing browser is still valid
    if _browser is not None:
        try:
            # Test if browser is still connected
            _browser.current_url
        except Exception:
            # Browser is disconnected, clean it up and create new one
            try:
                _browser.quit()
            except:
                pass
            _browser = None
    
    # Create new browser if needed
    if _browser is None:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-images")  # Faster loading
        chrome_options.add_argument("--disable-extensions")  # Faster startup
        chrome_options.add_argument("--disable-plugins")  # Faster startup
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        _browser = webdriver.Chrome(options=chrome_options)
        # Register cleanup function
        atexit.register(_cleanup_browser)
    return _browser

def _cleanup_browser():
    """Clean up browser instance on exit"""
    global _browser
    if _browser:
        try:
            _browser.quit()
        except:
            pass
        _browser = None

def get_target_ingredients_with_selenium(url):
    """
    IMPROVED VERSION: Extract ingredients from Target.com using multiple strategies including JSON parsing
    """
    try:
        # Use reusable browser for SPEED
        driver = _get_browser()
        driver.get(url)
        
        # Wait for page to load
        wait = WebDriverWait(driver, 8)  # Increased slightly for better reliability
        time.sleep(2)  # Allow page to fully load
        
        # STRATEGY 1: Try to find ingredients in JSON data first (most reliable for Target.com)
        try:
            # Execute JavaScript to extract nutrition_facts from window data
            js_result = driver.execute_script("""
                try {
                    // Look for nutrition_facts in window object
                    if (window.__NEXT_DATA__ && window.__NEXT_DATA__.props) {
                        const data = JSON.stringify(window.__NEXT_DATA__.props);
                        const nutritionMatch = data.match(/"nutrition_facts":\\s*\\{[^}]*"ingredients":\\s*"([^"]{100,})"/);
                        if (nutritionMatch) return nutritionMatch[1];
                    }
                    
                    // Look for ingredients in Redux store
                    if (window.__PRELOADED_STATE__) {
                        const data = JSON.stringify(window.__PRELOADED_STATE__);
                        const nutritionMatch = data.match(/"nutrition_facts":\\s*\\{[^}]*"ingredients":\\s*"([^"]{100,})"/);
                        if (nutritionMatch) return nutritionMatch[1];
                    }
                    
                    // Look in page source for nutrition_facts
                    const pageText = document.documentElement.innerHTML;
                    const nutritionMatch = pageText.match(/"nutrition_facts":\\s*\\{[^}]*"ingredients":\\s*"([^"]{100,})"/);
                    if (nutritionMatch) return nutritionMatch[1];
                    
                    return null;
                } catch (e) {
                    return null;
                }
            """)
            
            if js_result and len(js_result) > 50:
                # Clean up any escaped characters
                cleaned_ingredients = js_result.replace('\\u003c', '<').replace('\\u003e', '>')
                cleaned_ingredients = re.sub(r'\\u[0-9a-fA-F]{4}', '', cleaned_ingredients)
                print(f"Found valid Target ingredients via JavaScript: {cleaned_ingredients[:100]}...")
                return cleaned_ingredients
        except Exception as e:
            print(f"JavaScript extraction failed: {e}")
        
        # STRATEGY 2: Try to find and click accordion/dropdown elements
        dropdown_selectors = [
            # Target.com specific accordion selectors (discovered from debug)
            "//button[contains(@href, 'ProductDetailsAndHighlights-accordion')]",
            "//button[contains(@href, 'Specifications-accordion')]", 
            "//button[@aria-expanded='false'][contains(., 'Details')]",
            "//button[@aria-expanded='false'][contains(., 'Specifications')]",
            
            # Traditional dropdown selectors
            "//button[contains(text(), 'Label info')]",
            "//a[contains(text(), 'Label info')]", 
            "//*[contains(text(), 'Label info')]",
            "//button[contains(text(), 'Product details')]",
            "//a[contains(text(), 'Product details')]", 
            "//*[contains(text(), 'Product details')]",
            "//button[contains(text(), 'Nutrition facts')]",
            "//a[contains(text(), 'Nutrition facts')]",
            "//*[contains(text(), 'Nutrition facts')]",
            "//button[contains(text(), 'Ingredients')]",
            "//a[contains(text(), 'Ingredients')]",
            "//*[contains(text(), 'Ingredients')]"
        ]
        
        dropdown_found = False
        for selector in dropdown_selectors:
            try:
                element = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                element.click()
                print(f"Found dropdown with selector: {selector}")
                dropdown_found = True
                time.sleep(3)  # Wait longer for accordion content to load
                break
            except TimeoutException:
                print(f"Timeout with selector: {selector}")
                continue
        
        # Continue even if dropdown not clicked - ingredients might be visible already
        if not dropdown_found:
            print("Could not find clickable dropdown - searching page content directly")
        
        # STRATEGY 2.5: Try to remove ads and then click accordion buttons  
        if not dropdown_found:
            try:
                # Remove ads that might block clicks
                driver.execute_script("""
                    // Remove iframes (ads)
                    const iframes = document.querySelectorAll('iframe');
                    iframes.forEach(iframe => iframe.remove());
                    
                    // Remove overlay elements that might block clicks
                    const overlays = document.querySelectorAll('[style*="z-index"]');
                    overlays.forEach(overlay => {
                        if (overlay.style.zIndex && parseInt(overlay.style.zIndex) > 100) {
                            overlay.remove();
                        }
                    });
                """)
                time.sleep(1)
                
                accordion_buttons = driver.find_elements(By.XPATH, "//button[@aria-expanded='false']")
                print(f"Found {len(accordion_buttons)} accordion buttons to try")
                
                for i, button in enumerate(accordion_buttons[:5]):  # Limit to first 5 buttons
                    try:
                        button_text = button.text.strip()
                        if any(keyword in button_text.lower() for keyword in ['detail', 'specification', 'info', 'nutrition']):
                            print(f"Clicking accordion button {i+1}: '{button_text}'")
                            
                            # Try multiple click strategies
                            try:
                                # Method 1: JavaScript click
                                driver.execute_script("arguments[0].click();", button)
                            except:
                                try:
                                    # Method 2: Scroll into view then click
                                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                                    time.sleep(1)
                                    button.click()
                                except:
                                    # Method 3: Force click with coordinates
                                    driver.execute_script("arguments[0].dispatchEvent(new MouseEvent('click', {bubbles: true}));", button)
                            
                            time.sleep(3)  # Wait for content to load
                            
                            # Check if ingredients appeared in the newly expanded content
                            current_source = driver.page_source
                            if any(keyword in current_source.lower() for keyword in ['ingredient', 'vitamin', 'supplement']):
                                print(f"Found ingredient-related content after clicking '{button_text}'")
                                break
                    except Exception as e:
                        print(f"Error clicking accordion button {i+1}: {e}")
                        continue
            except Exception as e:
                print(f"Accordion button strategy failed: {e}")
        
        # Get page source after clicking dropdown/accordion
        page_source = driver.page_source
        
        # STRATEGY 3: Enhanced search for visible ingredients on the page
        # First try to use the find_best_og_image strategy for finding the best product image
        try:
            images_found = driver.execute_script("""
                try {
                    // Count total images and those with data-src
                    const allImages = document.querySelectorAll('img');
                    const imagesWithDataSrc = document.querySelectorAll('img[data-src]');
                    return `Found ${allImages.length}/${imagesWithDataSrc.length} images on page (including data-src) – Using strategy: find_best_og_image`;
                } catch (e) {
                    return 'Image count failed';
                }
            """)
            print(f"Debug Info: {images_found}")
        except:
            pass
        
        # TARGET SPECIFIC: Enhanced ingredient patterns focusing on supplements
        ingredient_patterns = [
            # Pattern 1: Specific for Pet Naturals - vitamin content starting with common supplement ingredients
            r'(?i)(?:chicken liver|brewers dried yeast|dicalcium phosphate|microcrystalline cellulose)[^.]*?(?:vitamin\s+[a-z]\d*|folic\s+acid|biotin|niacin)[^.]*',
            
            # Pattern 2: "Ingredients:" followed by any legitimate ingredient list
            r'(?i)ingredients[:\s]*([a-z][^<>]*?(?:,\s*[^<>,]{2,30}){3,}[^<>]*?)(?:[\.<"]|$)',
            
            # Pattern 3: Supplement specific - Vitamins and minerals with better matching
            r'((?:chicken liver|brewers yeast|dicalcium phosphate|microcrystalline cellulose|vitamin|mineral|extract|oil|powder|acid)[^<>]*?(?:,\s*[^<>,]{3,30}){3,}[^<>]*?)(?:[\.<"\s\}]|$)',
            
            # Pattern 4: Pet food specific - Traditional pet food ingredients
            r'((?:whole ground corn|corn gluten meal|chicken meal|fish meal|deboned chicken|chicken by-product|poultry meal|beef tallow|soybean meal|water|chicken|fish)[^<>]*?(?:,\s*[^<>,]{3,30}){5,}[^<>]*?)(?:[\.<"\s\}]|$)',
            
            # Pattern 5: Universal pattern for any ingredient list with 5+ comma-separated items
            r'([a-z][a-z\s,\(\)-]*(?:,\s*[a-z][a-z\s\(\)-]{2,25}){5,}[^<>]*?)(?:[\.<"\s]|$)',
            
            # Pattern 6: Shorter lists for supplements (3+ items)
            r'([a-z][a-z\s,\(\)-]*(?:,\s*[a-z][a-z\s\(\)-]{2,25}){3,}[^<>]*?)(?:[\.<"\s]|$)'
        ]
        
        # Process patterns efficiently
        for pattern in ingredient_patterns:
            matches = re.finditer(pattern, page_source, re.IGNORECASE | re.DOTALL)
            for match in matches:
                content = match.group(1).strip()
                
                # Quick cleanup (optimized)
                content = re.sub(r'&[a-zA-Z0-9#]+;', '', content)
                content = re.sub(r'<[^>]+>', '', content)
                content = re.sub(r'^["\':\\\\]+', '', content)
                content = re.sub(r'["\'\\\\\.]+$', '', content)
                content = re.sub(r'\s+', ' ', content)
                content = content.strip()
                
                # STRICT validation to ensure we have actual ingredients, not page titles or marketing
                if (len(content) > 30 and 
                    content.count(',') >= 2 and
                    # Must contain legitimate ingredients (expanded for supplements)
                    any(word in content.lower() for word in [
                        'meal', 'rice', 'vitamin', 'supplement', 'chicken', 'fish', 'corn', 'barley', 'wheat',
                        'liver', 'calcium', 'mineral', 'extract', 'oil', 'powder', 'acid', 'yeast', 'protein'
                    ]) and
                    # Must NOT contain page metadata, titles, or marketing content
                    not any(bad in content.lower() for bad in [
                        'prohibited', 'otc products', 'warning', 'do not', 'consult', 
                        'doctor', 'physician', 'medical', 'drug', 'medication',
                        'strikethrough_enabled', 'privacy_link', 'product_detail_view',
                        'tracking_enabled', 'global_', 'true', 'false', 'enabled', 'event_tracking',
                        'javascript', 'function', 'var ', 'const ', 'let ', '":', '":"', '_enabled',
                        'please note that', 'this product', 'not intended', 'the statements',
                        # Reject page titles and marketing content
                        'target', ': target', 'everyday health', 'health support', 'flavor',
                        'count', 'daily multi', 'delicious', 'chewable', 'multivitamin',
                        'name="keywords"', 'property="og:', 'content="', 'data-',
                        # Reject marketing descriptions
                        'provides over', 'healthful nutrients', 'to support your', 'maintain peak',
                        'immune system', 'eye function', 'throughout his life', 'any age',
                        'peak condition', 'antioxidants and minerals', 'B complex'
                    ]) and
                    # Must be mostly lowercase (ingredients are typically lowercase)
                    sum(c.islower() for c in content if c.isalpha()) > sum(c.isupper() for c in content if c.isalpha())):
                    print(f"Found valid Target ingredients via Selenium: {content[:100]}...")
                    return content
        
        return None
        
    except Exception as e:
        print(f"Selenium error: {e}")
        return None 