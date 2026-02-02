from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import re
import time
import random
import string
from urllib.parse import urlparse, urljoin

app = Flask(__name__)

# File to store scraped data
DATA_FILE = 'scraped_data.json'

def generate_random_id():
    """Generate a random ID for barcode placeholder (mix of letters and numbers)"""
    # Generate a random 8-character ID that looks like a barcode/product ID
    characters = string.ascii_lowercase + string.digits
    random_part = ''.join(random.choices(characters, k=6))
    prefix = random.choice(['applaws', 'pet', 'food', 'prod'])
    return f"{prefix}-{random_part}"

def add_proper_brand_spacing(brand):
    """Add proper spacing to compound brand names"""
    if not brand or len(brand) < 3:
        return brand
    
    # Dictionary of known brand names that should have spaces
    brand_spacing_rules = {
        # Pet food brands
        'petnaturals': 'Pet Naturals',
        'petco': 'Petco',  # Keep as one word - this is correct
        'petsmart': 'PetSmart',
        'bluebluffalo': 'Blue Buffalo',
        'bluebuffalo': 'Blue Buffalo', 
        'hillspet': 'Hill\'s Pet',
        'hillsscience': 'Hill\'s Science',
        'royalcanin': 'Royal Canin',
        'nutronatural': 'Nutro Natural',
        'naturalbalance': 'Natural Balance',
        'earthborn': 'Earthborn',  # Keep as one word - this is correct
        'solidgold': 'Solid Gold',
        'tastewild': 'Taste of the Wild',
        'tasteofthewild': 'Taste of the Wild',
        'stellachewy': 'Stella & Chewy\'s',
        'stellaandchewys': 'Stella & Chewy\'s',
        'ziwipeak': 'ZiwiPeak',
        'rachealray': 'Rachael Ray',
        'rachaelray': 'Rachael Ray',
        'bluewilderness': 'Blue Wilderness',
        'merrickpet': 'Merrick Pet',
        'wellnesscomplete': 'Wellness Complete',
        'wellnesscore': 'Wellness CORE',
    }
    
    # Check for exact matches first (case insensitive)
    brand_lower = brand.lower()
    if brand_lower in brand_spacing_rules:
        return brand_spacing_rules[brand_lower]
    
    # Pattern-based spacing for common compound patterns
    import re
    
    # Pattern 1: Pet + word (e.g., "PetNaturals" -> "Pet Naturals")
    brand = re.sub(r'^([Pp])et([A-Z][a-z]+)', r'\1et \2', brand)
    
    # Pattern 2: Blue + word (e.g., "BlueBuffalo" -> "Blue Buffalo") 
    brand = re.sub(r'^([Bb])lue([A-Z][a-z]+)', r'\1lue \2', brand)
    
    # Pattern 3: Hill's + word (e.g., "HillsScience" -> "Hill's Science")
    brand = re.sub(r'^([Hh])ills([A-Z][a-z]+)', r'\1ill\'s \2', brand)
    
    # Pattern 4: Royal + word (e.g., "RoyalCanin" -> "Royal Canin")
    brand = re.sub(r'^([Rr])oyal([A-Z][a-z]+)', r'\1oyal \2', brand)
    
    # Pattern 5: Natural + word (e.g., "NaturalBalance" -> "Natural Balance")
    brand = re.sub(r'^([Nn])atural([A-Z][a-z]+)', r'\1atural \2', brand)
    
    # Pattern 6: Stella + word (e.g., "StellaChewy" -> "Stella Chewy")  
    brand = re.sub(r'^([Ss])tella([A-Z][a-z]+)', r'\1tella \2', brand)
    
    # Pattern 7: Generic pattern for camelCase brand names (Word1Word2 -> Word1 Word2)
    # Only apply if it results in reasonable looking words
    if len(brand) > 6 and brand.lower() not in ['petco', 'earthborn', 'orijen', 'acana']:
        # Look for pattern where lowercase is followed by uppercase
        camel_pattern = r'([a-z])([A-Z][a-z]+)'
        if re.search(camel_pattern, brand):
            spaced_brand = re.sub(camel_pattern, r'\1 \2', brand)
            # Only use the spaced version if both parts are reasonable length
            parts = spaced_brand.split()
            if len(parts) == 2 and len(parts[0]) >= 3 and len(parts[1]) >= 3:
                brand = spaced_brand
    
    return brand

def load_data():
    """Load existing scraped data"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    return []

def save_data(data):
    """Save data to JSON file"""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def extract_target_brand_from_shop_all(soup, url):
    """Extract brand from Target.com by looking for 'Show all [Brand]' or 'Shop all [Brand]' patterns"""
    if 'target.com' not in url.lower():
        return None
    
    # PRIMARY: Look for "Show all [Brand]" or "Shop all [Brand]" text patterns (most reliable for Target.com)
    # This covers links like "Show all Pet Honesty", "Show all Meow Mix", etc.
    show_all_patterns = [
        r'show\s+all\s+([\w\s&\'-]{2,25})(?=\s|$|\.)',  # "Show all Pet Honesty"
        r'shop\s+all\s+([\w\s&\'-]{2,25})(?=\s|$|\.)',  # "Shop all Pet Honesty" 
    ]
    
    # Search in all text elements for these patterns
    all_elements = soup.find_all(['a', 'span', 'div', 'button', 'li'])
    
    for elem in all_elements:
        text = elem.get_text().strip()
        
        # Skip very long text blocks that are likely combined content
        if len(text) > 200:
            continue
            
        for pattern in show_all_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                brand = match.group(1).strip()
                
                # Clean up duplicated brand names (e.g., "Pet HonestyPet Honesty" -> "Pet Honesty")
                brand = re.sub(r'\s+', ' ', brand)  # Normalize whitespace
                
                # Handle duplicated brand names
                words = brand.split()
                if len(words) >= 2 and len(words) % 2 == 0:
                    half = len(words) // 2
                    first_half = ' '.join(words[:half])
                    second_half = ' '.join(words[half:])
                    if first_half.lower() == second_half.lower():
                        brand = first_half
                
                if (brand and len(brand) > 1 and 
                    brand.lower() not in ['target', 'shop', 'all', 'items', 'products', 'brands', 'salmon', 'chicken', 'beef', 'recipe', 'flavor', 'food', 'more', 'less'] and
                    not re.match(r'^\d+$', brand) and  # Not just numbers
                    re.match(r'^[A-Za-z][A-Za-z0-9\s&\'-]*$', brand)):  # Valid brand format
                    
                    # Capitalize properly (Title Case)
                    brand_words = brand.split()
                    formatted_brand = ' '.join(word.capitalize() if word.lower() not in ['and', 'of', 'the', 'in', 'with'] else word.lower() for word in brand_words)
                    return formatted_brand
    
    # FALLBACK 1: Try to extract brand from JSON data in script tags
    script_tags = soup.find_all('script')
    
    for script in script_tags:
        if script.string and len(script.string) > 1000 and 'primary_brand' in script.string:
            # Get the primary_brand section and look for name (handle escaped quotes in JSON)
            pos = script.string.find('primary_brand')
            context = script.string[pos:pos+500]
            name_pattern = r'\\"name\\":\\s*\\"([^"\\]+)\\"'
            match = re.search(name_pattern, context)
            if match:
                brand = match.group(1).strip()
                if brand and len(brand) > 1 and brand.lower() not in ['target', 'shop', 'all']:
                    return brand
    
    return None

def extract_brand(soup, url):
    """Extract brand information from the webpage"""
    brand = None
    
    # Common brand extraction strategies
    strategies = [
        # Target.com specific: Look for "Shop all [Brand]" pattern
        lambda: extract_target_brand_from_shop_all(soup, url),
        
        # Look for brand in meta tags
        lambda: soup.find('meta', {'property': 'product:brand'}),
        lambda: soup.find('meta', {'name': 'brand'}),
        lambda: soup.find('meta', {'itemprop': 'brand'}),
        
        # Look for structured data (JSON-LD)
        lambda: extract_from_json_ld(soup, 'brand'),
        
        # Look for common class names and patterns
        lambda: soup.find(class_=re.compile(r'brand', re.I)),
        lambda: soup.find('span', class_=re.compile(r'brand', re.I)),
        lambda: soup.find('div', class_=re.compile(r'brand', re.I)),
        
        # Look for text patterns
        lambda: soup.find(string=re.compile(r'brand:', re.I)),
        
        # Look in title or headings
        lambda: extract_from_title(soup),
        
        # Extract from URL as fallback
        lambda: extract_brand_from_url(url),
    ]
    
    for i, strategy in enumerate(strategies):
        try:
            result = strategy()
            if result:
                if hasattr(result, 'get'):
                    brand = result.get('content') or result.get_text()
                elif hasattr(result, 'get_text'):
                    brand = result.get_text()
                else:
                    brand = str(result)
                

                
                if brand and brand.strip() and brand.strip().lower() not in ['brand not found', 'not found']:
                    brand = brand.strip()
                    # Handle Purina Friskies brand exception
                    brand_lower = brand.lower()
                    url_lower = url.lower()
                    
                    # Case 1: Brand is just "Friskies" → make it "Purina Friskies"
                    if "friskies" in brand_lower and "purina" not in brand_lower:
                        # Find Friskies with original case
                        friskies_match = re.search(r'friskies', brand, re.IGNORECASE)
                        if friskies_match:
                            friskies_text = friskies_match.group()
                            # Replace with Purina prefix
                            brand = re.sub(r'\bfriskies\b', f'Purina {friskies_text}', brand, flags=re.IGNORECASE)
                    
                    # Case 2: Brand is "Purina" but URL contains "friskies" → make it "Purina Friskies"
                    elif brand_lower == "purina" and "friskies" in url_lower:
                        brand = "Purina Friskies"
                    
                    # Apply proper spacing to compound brand names
                    brand = add_proper_brand_spacing(brand)
                    
                    return brand
        except Exception:
            continue
    
    return "Brand not found"

def extract_brand_from_url(url):
    """Extract brand name from the URL itself"""
    try:
        # Common pet food brands to look for in URLs
        pet_brands = [
            'purina', 'hills', 'hill', 'royal-canin', 'royal canin', 'blue-buffalo', 'blue buffalo',
            'wellness', 'orijen', 'acana', 'merrick', 'taste-of-the-wild', 'taste of the wild',
            'instinct', 'nutro', 'iams', 'pedigree', 'science-diet', 'science diet',
            'pro-plan', 'pro plan', 'beneful', 'fancy-feast', 'fancy feast',
            'whiskas', 'temptations', 'greenies', 'dentastix', 'cesar', 'sheba',
            'viva-raw', 'viva raw', 'stella-chewy', 'stella chewy', 'ziwi-peak', 'ziwi peak',
            'fromm', 'canidae', 'diamond', 'kirkland', 'costco', 'rachael-ray', 'rachael ray',
            'blue-wilderness', 'blue wilderness', 'nulo', 'earthborn', 'solid-gold', 'solid gold',
            'meow-mix', 'meow mix'
        ]
        
        # Clean URL for analysis
        url_lower = url.lower()
        url_parts = url_lower.replace('https://', '').replace('http://', '').replace('www.', '')
        
        # Special check for Friskies first (since it's always Purina Friskies)
        if 'friskies' in url_parts:
            return "Purina Friskies"
        
        # Look for brand in domain name
        for brand in pet_brands:
            brand_clean = brand.replace('-', '').replace(' ', '')
            if brand_clean in url_parts.replace('-', '').replace('/', '').replace('.', ''):
                # Format brand name properly
                brand_formatted = brand.replace('-', ' ').title()
                # Handle Purina Friskies brand exception
                if "friskies" in brand_formatted.lower() and "purina" not in brand_formatted.lower():
                    brand_formatted = f"Purina {brand_formatted}"
                return brand_formatted
        
        # Extract potential brand from URL path segments
        path_segments = url_parts.split('/')
        for segment in path_segments:
            # Clean segment
            segment = segment.replace('-', ' ').replace('_', ' ')
            # Look for brand patterns in segments
            for brand in pet_brands:
                if brand.replace('-', ' ').lower() in segment.lower():
                    brand_formatted = brand.replace('-', ' ').title()
                    # Handle Purina Friskies brand exception
                    if "friskies" in brand_formatted.lower() and "purina" not in brand_formatted.lower():
                        brand_formatted = f"Purina {brand_formatted}"
                    return brand_formatted
            
            # Look for common brand patterns in segment names
            if any(keyword in segment for keyword in ['brand', 'manufacturer', 'company']):
                # Try to extract brand name from the segment
                words = segment.split('-')
                if len(words) >= 2:
                    potential_brand = ' '.join(words[:-1]) if words[-1] in ['brand', 'pet', 'food'] else segment
                    return potential_brand.replace('-', ' ').title()
        
        # For image URLs, also try to extract from filename
        if any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.pdf']):
            # Try to get brand from filename
            filename = url_parts.split('/')[-1].replace('%20', ' ')
            for brand in pet_brands:
                if brand.replace('-', ' ').lower() in filename.lower():
                    brand_formatted = brand.replace('-', ' ').title()
                    # Handle Purina Friskies brand exception
                    if "friskies" in brand_formatted.lower() and "purina" not in brand_formatted.lower():
                        brand_formatted = f"Purina {brand_formatted}"
                    return brand_formatted
        
        # Extract from domain name
        domain = url_parts.split('/')[0].split('.')[0]
        if domain and len(domain) > 3 and domain not in ['www', 'shop', 'store', 'pet', 'dog', 'cat', 'images', 'img', 'cdn', 'assets']:
            return domain.replace('-', ' ').title()
            
    except Exception:
        pass
    
    return None

def extract_pet_type(soup, url):
    """Extract pet type (cat or dog) from URL and page content"""
    try:
        # Convert to lowercase for easier matching
        url_lower = url.lower()
        
        # Define keywords for each pet type (expanded list)
        cat_keywords = ['cat', 'cats', 'feline', 'felines', 'kitten', 'kittens', 'kitty', 'kitties']
        dog_keywords = ['dog', 'dogs', 'canine', 'canines', 'puppy', 'puppies', 'pup', 'pups']
        
        # Check URL path first (most reliable)
        for keyword in cat_keywords:
            if keyword in url_lower:
                return 'cat'
        
        for keyword in dog_keywords:
            if keyword in url_lower:
                return 'dog'
        
        # Check page title
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text('').lower()
            for keyword in cat_keywords:
                if keyword in title_text:
                    return 'cat'
            for keyword in dog_keywords:
                if keyword in title_text:
                    return 'dog'
        
        # Check meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            desc_content = meta_desc.get('content', '').lower()
            for keyword in cat_keywords:
                if keyword in desc_content:
                    return 'cat'
            for keyword in dog_keywords:
                if keyword in desc_content:
                    return 'dog'
        
        # Check Open Graph title and description
        og_title = soup.find('meta', {'property': 'og:title'})
        if og_title:
            og_title_content = og_title.get('content', '').lower()
            for keyword in cat_keywords:
                if keyword in og_title_content:
                    return 'cat'
            for keyword in dog_keywords:
                if keyword in og_title_content:
                    return 'dog'
        
        og_desc = soup.find('meta', {'property': 'og:description'})
        if og_desc:
            og_desc_content = og_desc.get('content', '').lower()
            for keyword in cat_keywords:
                if keyword in og_desc_content:
                    return 'cat'
            for keyword in dog_keywords:
                if keyword in og_desc_content:
                    return 'dog'
        
        # Check all headings (more comprehensive)
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            heading_text = heading.get_text('').lower()
            for keyword in cat_keywords:
                if keyword in heading_text:
                    return 'cat'
            for keyword in dog_keywords:
                if keyword in heading_text:
                    return 'dog'
        
        # Check product breadcrumbs and navigation
        breadcrumbs = soup.find_all(['nav', 'ol', 'ul'], class_=lambda x: x and ('breadcrumb' in x.lower() or 'nav' in x.lower()))
        for breadcrumb in breadcrumbs:
            breadcrumb_text = breadcrumb.get_text('').lower()
            for keyword in cat_keywords:
                if keyword in breadcrumb_text:
                    return 'cat'
            for keyword in dog_keywords:
                if keyword in breadcrumb_text:
                    return 'dog'
        
        # Check main content areas
        main_content = soup.find_all(['main', 'article', 'section'], limit=3)
        for content in main_content:
            content_text = content.get_text('').lower()
            for keyword in cat_keywords:
                if keyword in content_text:
                    return 'cat'
            for keyword in dog_keywords:
                if keyword in content_text:
                    return 'dog'
        
        # Last resort: Search entire page body text (limited to avoid noise)
        body = soup.find('body')
        if body:
            # Get first 2000 characters of body text to avoid too much noise
            body_text = body.get_text('')[:2000].lower()
            for keyword in cat_keywords:
                if keyword in body_text:
                    return 'cat'
            for keyword in dog_keywords:
                if keyword in body_text:
                    return 'dog'
        
        # Default fallback - could not determine
        return 'unknown'
        
    except Exception:
        return 'unknown'

def extract_food_type(soup, url):
    """Extract food type from URL and page content - supports multiple types"""
    try:
        # ONLY check URL and title for food type (per user request)
        url_lower = url.lower()
        
        # Get title only
        title = soup.find('title')
        title_text = title.get_text().lower() if title else ''
        
        # Only combine URL and title for food type detection
        all_text = f"{url_lower} {title_text}"
        
        # Define food type indicators with separate freeze-dried category
        food_type_indicators = {
            'dry': [
                'kibble', 'dry food', 'dry cat food', 'dry dog food', 'biscuit', 'pellet',
                'crunchy', 'crunch', 'nugget', 'bits', 'dry-cat-food', 'dry-dog-food'
            ],
            'wet': [
                'wet', 'canned', 'can', 'gravy', 'sauce', 'stew', 'broth',
                'chunks in', 'flaked', 'shredded', 'minced', 'loaf', 'in-gravy',
                'chicken broth', 'beef broth', 'fish broth', 'mousse'
            ],
            'raw': [
                'raw', 'raw boost', 'raw pieces', 'raw nutrition', 'frozen raw',
                'fresh raw', 'raw diet', 'raw food'
            ],
            'freeze-dried': [
                'freeze dried', 'freeze-dried', 'freezedried', 'freeze dry',
                'lyophilized', 'freeze-drying', 'fd', 'freeze dried raw'
            ],
            'air-dried': [
                'air dried', 'air-dried', 'air dry', 'naturally dried'
            ],
            'pate': [
                'pate', 'paté', 'pâté', 'smooth pate', 'chunky pate', 'classic pate'
            ],
            'treats': [
                'treat', 'treats', 'snack', 'training reward', 'dental chew',
                'biscuit treat', 'jerky', 'cookie', 'chew', 'bone'
            ],
            'toppers': [
                'topper', 'toppers', 'meal topper', 'food topper', 'flavor enhancer',
                'meal enhancer', 'food enhancer', 'sprinkle', 'mix-in', 'mixins',
                'food booster', 'meal booster', 'supplement powder', 'nutritional topper'
            ]
        }
        
        # Count indicators for each food type with weights
        # Give higher weight to URL indicators since they're most reliable
        food_type_scores = {}
        for food_type, indicators in food_type_indicators.items():
            score = 0
            for indicator in indicators:
                if indicator in all_text:
                    # Higher weight for URL/title mentions
                    if indicator in url_lower or indicator in title_text:
                        score += 3
                    else:
                        score += 1
            food_type_scores[food_type] = score
        
        # Find all food types that have a significant presence (threshold approach)
        detected_types = []
        
        # Primary type detection - at least 2 points or strong indicator
        for food_type, score in food_type_scores.items():
            if score >= 2:  # Threshold for detection
                detected_types.append(food_type)
        
        # Special logic for combinations and conflicts
        if detected_types:
            # Remove conflicts and apply business rules
            
            # Rule 1: If pate is detected, include wet automatically
            if 'pate' in detected_types and 'wet' not in detected_types:
                detected_types.append('wet')
            
            # Rule 2: If both dry (kibble) and raw are detected, it's likely dry with freeze-dried raw pieces
            if 'dry' in detected_types and 'raw' in detected_types:
                # Check if freeze-dried is also mentioned
                if 'freeze-dried' not in detected_types and any(indicator in all_text for indicator in ['freeze dried', 'freeze-dried']):
                    detected_types.append('freeze-dried')
                # Keep both dry and raw in this case
            
            # Rule 3: If freeze-dried and raw are both detected, keep both
            # (e.g., "freeze-dried raw" products)
            
            # Sort by priority for consistent ordering
            priority_order = ['treats', 'toppers', 'pate', 'wet', 'dry', 'freeze-dried', 'air-dried', 'raw']
            detected_types = [t for t in priority_order if t in detected_types]
            
            # Return as comma-separated string
            return ', '.join(detected_types)
        
        # Fallback: no clear indicators found
        return "dry"  # Default fallback
        
    except Exception as e:
        return "dry"  # Safe fallback

def extract_food_type_from_url(url):
    """Extract food type from URL only (for direct image URLs) - supports multiple types"""
    try:
        url_lower = url.lower()
        
        # Define food type indicators for URL checking
        url_indicators = {
            'pate': ['pate', 'paté', 'pâté'],
            'toppers': ['topper', 'toppers', 'meal-topper', 'food-topper', 'enhancer', 'mix-in'],
            'treats': ['treat', 'treats', 'snack', 'training', 'dental', 'jerky', 'chew', 'bone'],
            'wet': ['wet', 'canned', 'can', 'gravy', 'sauce', 'broth', 'stew', 'mousse'],
            'dry': ['dry', 'kibble', 'pellet', 'biscuit', 'crunchy'],
            'freeze-dried': ['freeze-dried', 'freeze dried', 'freezedried', 'freeze-dry', 'fd'],
            'air-dried': ['air-dried', 'air dried', 'air-dry'],
            'raw': ['raw', 'frozen-raw', 'fresh-raw']
        }
        
        detected_types = []
        
        # Check each food type
        for food_type, keywords in url_indicators.items():
            if any(keyword in url_lower for keyword in keywords):
                detected_types.append(food_type)
        
        if detected_types:
            # Apply same business rules as main function
            
            # Rule 1: If pate is detected, include wet automatically
            if 'pate' in detected_types and 'wet' not in detected_types:
                detected_types.append('wet')
            
            # Sort by priority for consistent ordering
            priority_order = ['treats', 'toppers', 'pate', 'wet', 'dry', 'freeze-dried', 'air-dried', 'raw']
            detected_types = [t for t in priority_order if t in detected_types]
            
            return ', '.join(detected_types)
        else:
            return 'dry'  # Default fallback
            
    except Exception:
        return 'dry'

def extract_product_name_from_url(url):
    """Extract product name from URL only (for direct image URLs)"""
    try:
        # Extract filename from URL
        from urllib.parse import unquote, urlparse
        parsed = urlparse(url)
        path = parsed.path
        
        # Get the filename without extension
        filename = path.split('/')[-1]
        if '.' in filename:
            filename = filename.rsplit('.', 1)[0]
        
        # URL decode the filename
        filename = unquote(filename)
        
        # Replace common separators with spaces
        name = filename.replace('-', ' ').replace('_', ' ').replace('+', ' ')
        
        # Clean up multiple spaces
        import re
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Capitalize words appropriately
        if name:
            name = name.title()
            return name
        
        return None
        
    except Exception:
        return None

def extract_pet_type_from_url(url):
    """Extract pet type from URL only (for direct image URLs)"""
    try:
        url_lower = url.lower()
        
        # Define keywords for each pet type (expanded list - same as main function)
        cat_keywords = ['cat', 'cats', 'feline', 'felines', 'kitten', 'kittens', 'kitty', 'kitties']
        dog_keywords = ['dog', 'dogs', 'canine', 'canines', 'puppy', 'puppies', 'pup', 'pups']
        
        # Check URL for keywords
        for keyword in cat_keywords:
            if keyword in url_lower:
                return 'cat'
        
        for keyword in dog_keywords:
            if keyword in url_lower:
                return 'dog'
        
        return 'unknown'
        
    except Exception:
        return 'unknown'

def find_best_og_image(soup):
    """Find the best Open Graph image from potentially multiple og:image tags"""
    # Look for all og:image meta tags
    og_images = soup.find_all('meta', {'property': 'og:image'})
    
    if not og_images:
        # Try alternative formats
        og_images = soup.find_all('meta', attrs={'property': lambda x: x and x.lower() == 'og:image'})
    
    if og_images:
        # If multiple og:image tags, prefer ones that look like product images
        for og_img in og_images:
            content = og_img.get('content', '')
            if content:
                # Prefer images with 'product', 'main', or larger dimensions in the URL
                if any(keyword in content.lower() for keyword in ['product', 'main', '1200', '800', '600']):
                    return og_img
        
        # If no preferred image found, return the first one
        return og_images[0]
    
    return None

def convert_to_full_size_image(image_url):
    """Convert thumbnail/social share image URLs to full-size versions"""
    if not image_url:
        return image_url
    
    # For Purina URLs, try multiple conversion patterns
    if 'purina.com' in image_url.lower():
        # Try different patterns that might work for Purina
        original_url = image_url
        
        # Pattern 1: Remove social_share path but keep the rest
        if '/styles/social_share/' in image_url:
            # Try: /sites/default/files/styles/social_share/public/products/image.jpg
            # To: /sites/default/files/public/products/image.jpg
            test_url = image_url.replace('/styles/social_share/', '/')
            # We could test this URL here, but for now let's be conservative
            # and return original since we know it works
            
        # Pattern 2: Try without query parameters
        if '?' in image_url:
            base_url = image_url.split('?')[0]
            # Again, could test this but being conservative for now
            
        # For now, keep the working social share images for Purina
        # TODO: Could implement URL testing here to verify alternatives work
        return original_url
    
    # Handle other Drupal-style paths for non-Purina sites
    if '/styles/social_share/' in image_url and 'purina.com' not in image_url.lower():
        return image_url.replace('/styles/social_share/', '/')
    
    if '/styles/thumbnail/' in image_url:
        return image_url.replace('/styles/thumbnail/', '/')
    
    if '/styles/medium/' in image_url:
        return image_url.replace('/styles/medium/', '/')
    
    if '/styles/small/' in image_url:
        return image_url.replace('/styles/small/', '/')
    
    # Remove query parameters that might indicate resizing (but be careful)
    if '?' in image_url and any(param in image_url.lower() for param in ['w=', 'h=', 'width=', 'height=', 'resize']) and 'purina.com' not in image_url.lower():
        return image_url.split('?')[0]
    
    return image_url


def extract_image_url(soup, url):
    """Extract image URL from the webpage - prioritizes first reasonable image"""
    image_url = None
    
    # Simple and effective image extraction strategies
    strategies = [
        # Prioritize full-size product images first
        ('find_first_reasonable_image', lambda: find_first_reasonable_image(soup)),
        
        # Look for structured data (JSON-LD)
        ('extract_from_json_ld', lambda: extract_from_json_ld(soup, 'image')),
        
        # Look for Open Graph image (often cropped for social sharing)
        ('find_best_og_image', lambda: find_best_og_image(soup)),
        ('product:image meta', lambda: soup.find('meta', {'property': 'product:image'})),
        ('twitter:image meta', lambda: soup.find('meta', {'name': 'twitter:image'})),
        
        # Fallback to any image that's not tiny
        ('find_any_decent_image', lambda: find_any_decent_image(soup)),
        
        # Look for images in CSS background-image properties
        ('find_background_images', lambda: find_background_images(soup)),
        
        # Look for images in JavaScript or data attributes
        ('find_script_images', lambda: find_script_images(soup)),
        
        # AGGRESSIVE: Search entire HTML for any image-like URLs
        ('find_any_image_url_in_html', lambda: find_any_image_url_in_html(soup)),
        
        # SUPER AGGRESSIVE: Direct regex search for og:image in HTML text
        ('find_og_image_in_raw_html', lambda: find_og_image_in_raw_html(soup)),
    ]
    
    for strategy_name, strategy in strategies:
        try:
            result = strategy()
            if result:
                # Store successful strategy for debug info
                extract_image_url._last_strategy = strategy_name
                
                if hasattr(result, 'get'):
                    # Meta tag
                    image_url = result.get('content')
                elif isinstance(result, list) and result:
                    # List of images, take the first one
                    image_url = result[0].get('src') if result[0] else None
                elif hasattr(result, 'get') and 'src' in result.attrs:
                    # Single img tag
                    image_url = result.get('src')
                
                if image_url and image_url.strip():
                    # Convert relative URLs to absolute
                    image_url = image_url.strip()
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        image_url = urljoin(url, image_url)
                    elif not image_url.startswith(('http://', 'https://')):
                        image_url = urljoin(url, image_url)
                    
                    # Convert social share/thumbnail URLs to full-size versions
                    full_size_url = convert_to_full_size_image(image_url)
                    if full_size_url != image_url:
                        image_url = full_size_url
                    
                    return image_url
        except Exception as e:
            continue
    
    extract_image_url._last_strategy = 'none_successful'
    return "Image not found"



def find_first_reasonable_image(soup):
    """Find the first image that's not obviously a logo/icon, prioritizing full-size images"""
    images = soup.find_all('img', src=True)
    
    # First pass: Look for full-size images (avoid thumbnail/social share versions)
    for img in images:
        try:
            src = img.get('src', '')
            alt = img.get('alt', '').lower()
            class_name = ' '.join(img.get('class', [])).lower()
            
            # Skip data URLs, empty sources, and very short URLs (like SVG placeholders)
            if not src or src.startswith('data:') or len(src) < 15:
                continue
            
            # Skip obvious logos, icons, and navigation elements
            skip_keywords = ['logo', 'icon', 'nav', 'menu', 'header', 'footer', 'sprite', 'svg']
            
            if any(keyword in src.lower() for keyword in skip_keywords):
                continue
            if any(keyword in alt for keyword in skip_keywords):
                continue
            if any(keyword in class_name for keyword in skip_keywords):
                continue
            
            # Skip thumbnail/social share images (prioritize full-size)
            thumbnail_indicators = [
                '/styles/social_share/',  # Only filter out social share specifically for now
            ]
            
            if any(indicator in src.lower() for indicator in thumbnail_indicators):
                continue
            
            # Skip very small images (likely icons)
            width = img.get('width')
            height = img.get('height')
            if width and height:
                try:
                    w, h = int(width), int(height)
                    if w < 50 or h < 50:  # Reduced from 100 to 50 for better success rate
                        continue
                except ValueError:
                    pass
            
            # Prioritize images that look like product images
            product_indicators = ['product', 'item', 'package', 'bag', 'can', 'food']
            
            # This looks like a product image - prioritize it
            if any(indicator in src.lower() for indicator in product_indicators):
                return img
            
            # This looks like a full-size image, return it
            return img
                    
        except Exception as e:
            continue
    
    # Second pass: Accept any reasonable image including thumbnails (fallback)
    for img in images:
        try:
            src = img.get('src', '')
            alt = img.get('alt', '').lower()
            class_name = ' '.join(img.get('class', [])).lower()
            
            # Skip data URLs, empty sources, and very short URLs
            if not src or src.startswith('data:') or len(src) < 15:
                continue
            
            # Skip only obvious logos, icons, and navigation elements
            skip_keywords = ['logo', 'icon', 'nav', 'menu', 'header', 'footer', 'sprite', 'svg']
            
            if any(keyword in src.lower() for keyword in skip_keywords):
                continue
            if any(keyword in alt for keyword in skip_keywords):
                continue
            if any(keyword in class_name for keyword in skip_keywords):
                continue
            
            # Skip very small images (likely icons)
            width = img.get('width')
            height = img.get('height')
            if width and height:
                try:
                    w, h = int(width), int(height)
                    if w < 50 or h < 50:  # Skip tiny images
                        continue
                except ValueError:
                    pass
            
            # This looks like a reasonable image, return it
            return img
                    
        except Exception:
            continue
    
    return None

def find_any_decent_image(soup):
    """Find any image that has a reasonable src (fallback)"""
    images = soup.find_all('img', src=True)
    
    for img in images:
        try:
            src = img.get('src', '')
            
            # Skip data URLs and empty sources
            if not src or src.startswith('data:') or len(src) < 10:
                continue
            
            # Skip common small/icon patterns
            if any(pattern in src.lower() for pattern in ['1x1', 'pixel', 'spacer', 'blank']):
                continue
                
            # Return the first image that looks like it has a real URL
            return img
                    
        except Exception:
            continue
    
    # If no good img tags, try to find ANY img tag even without src
    all_images = soup.find_all('img')
    for img in all_images:
        # Check all possible src attributes
        for attr in ['src', 'data-src', 'data-original', 'data-lazy', 'data-srcset']:
            if img.get(attr):
                fake_img = soup.new_tag('img')
                fake_img['src'] = img.get(attr)
                return fake_img
    
    return None

def find_background_images(soup):
    """Look for images in CSS background-image properties"""
    try:
        # Look for inline styles with background-image
        elements_with_bg = soup.find_all(style=True)
        for element in elements_with_bg:
            style = element.get('style', '')
            if 'background-image' in style.lower():
                # Extract URL from background-image: url(...)
                import re
                matches = re.search(r'background-image:\s*url\(["\']?([^"\')]+)["\']?\)', style, re.I)
                if matches:
                    img_url = matches.group(1)
                    # Create a fake img element to return
                    fake_img = soup.new_tag('img')
                    fake_img['src'] = img_url
                    return fake_img
        
        # Look for CSS with background images
        style_tags = soup.find_all('style')
        for style_tag in style_tags:
            if style_tag.string:
                matches = re.findall(r'background-image:\s*url\(["\']?([^"\')]+)["\']?\)', style_tag.string, re.I)
                if matches:
                    img_url = matches[0]
                    fake_img = soup.new_tag('img')
                    fake_img['src'] = img_url
                    return fake_img
                    
    except Exception:
        pass
    return None

def find_script_images(soup):
    """Look for image URLs in JavaScript or data attributes"""
    try:
        # Look for data-src attributes (lazy loading)
        img_with_data_src = soup.find('img', {'data-src': True})
        if img_with_data_src:
            # Create a proper img tag with the data-src as src
            fake_img = soup.new_tag('img')
            fake_img['src'] = img_with_data_src['data-src']
            return fake_img
            
        # Look for data-image attributes
        elements_with_data_image = soup.find_all(attrs={'data-image': True})
        if elements_with_data_image:
            fake_img = soup.new_tag('img')
            fake_img['src'] = elements_with_data_image[0]['data-image']
            return fake_img
            
        # Look for common image URLs in script tags
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string:
                # Look for image URLs in JavaScript
                import re
                image_patterns = [
                    r'["\']([^"\']*\.(?:jpg|jpeg|png|gif|webp|bmp)[^"\']*)["\']',
                    r'image["\']?\s*:\s*["\']([^"\']+)["\']',
                    r'src["\']?\s*:\s*["\']([^"\']+\.(?:jpg|jpeg|png|gif|webp|bmp)[^"\']*)["\']'
                ]
                
                for pattern in image_patterns:
                    matches = re.findall(pattern, script.string, re.I)
                    if matches:
                        img_url = matches[0]
                        if img_url and not any(skip in img_url.lower() for skip in ['icon', 'logo', 'sprite']):
                            fake_img = soup.new_tag('img')
                            fake_img['src'] = img_url
                            return fake_img
                            
    except Exception:
        pass
    return None

def find_any_image_url_in_html(soup):
    """AGGRESSIVE: Search entire HTML content for any image-like URLs"""
    try:
        import re
        # Get the entire HTML content as text
        html_text = str(soup)
        
        # Super aggressive patterns to find image URLs
        image_patterns = [
            # Standard image URLs
            r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|gif|webp|bmp)(?:\?[^\s"\'<>]*)?',
            r'//[^\s"\'<>]+\.(?:jpg|jpeg|png|gif|webp|bmp)(?:\?[^\s"\'<>]*)?',
            r'/[^\s"\'<>]+\.(?:jpg|jpeg|png|gif|webp|bmp)(?:\?[^\s"\'<>]*)?',
            
            # CDN and Shopify patterns
            r'https?://cdn\.shopify\.com/[^\s"\'<>]+',
            r'https?://[^\s"\'<>]*\.shopifycdn\.com/[^\s"\'<>]+',
            r'https?://[^\s"\'<>]*amazonaws\.com/[^\s"\'<>]+\.(?:jpg|jpeg|png|gif|webp)',
            
            # Common CMS patterns
            r'https?://[^\s"\'<>]*\.(?:cloudinary|imgix|cloudfront)\.com/[^\s"\'<>]+',
            
            # Look for any URL with 'image' in the path
            r'https?://[^\s"\'<>]*image[^\s"\'<>]*\.(?:jpg|jpeg|png|gif|webp|bmp)',
            r'https?://[^\s"\'<>]*/images?/[^\s"\'<>]+\.(?:jpg|jpeg|png|gif|webp|bmp)',
            
            # Look for data-src and other lazy loading attributes
            r'data-src=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|gif|webp|bmp)[^"\']*)["\']',
            r'data-original=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|gif|webp|bmp)[^"\']*)["\']',
        ]
        
        for pattern in image_patterns:
            matches = re.findall(pattern, html_text, re.I)
            if matches:
                # Return the first reasonable match
                for match in matches:
                    # Clean up the match (remove quotes if captured)
                    clean_match = match.strip('\'"')
                    
                    # Skip tiny/icon images and common excludes
                    if not any(skip in clean_match.lower() for skip in [
                        'icon', 'favicon', 'logo', '16x16', '32x32', '64x64', 'sprite', 
                        'placeholder', 'loading', 'blank', '1x1', 'pixel',
                        'badge', 'button', 'arrow', 'star'
                    ]):
                        # Prefer larger or product-related images
                        if any(good in clean_match.lower() for good in [
                            'product', 'main', 'large', 'hero', 'feature', 'detail',
                            'shopify', 'cdn', '_1024', '_800', '_600', 'x600', 'x800'
                        ]):
                            fake_img = soup.new_tag('img')
                            fake_img['src'] = clean_match
                            return fake_img
                            
                        # If no preferred patterns, take any reasonable image
                        if len(clean_match) > 50:  # Longer URLs are usually more legitimate
                            fake_img = soup.new_tag('img')
                            fake_img['src'] = clean_match
                            return fake_img
                        
    except Exception:
        pass
    return None

def find_og_image_in_raw_html(soup):
    """SUPER AGGRESSIVE: Direct regex search for og:image in raw HTML"""
    try:
        import re
        html_text = str(soup)
        
        # Look for og:image meta tags directly in the HTML text
        patterns = [
            r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\'][^>]*>',
            r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\'][^>]*>',
            r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
            r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html_text, re.I)
            if matches:
                image_url = matches[0]
                if image_url and len(image_url) > 10:
                    # Create a fake img tag to return
                    fake_img = soup.new_tag('img')
                    fake_img['src'] = image_url
                    return fake_img
                    
    except Exception:
        pass
    return None

def extract_from_json_ld(soup, field_type='brand'):
    """Extract brand or image from JSON-LD structured data"""
    scripts = soup.find_all('script', type='application/ld+json')
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0]
            
            if field_type == 'brand' and 'brand' in data:
                brand = data['brand']
                if isinstance(brand, dict):
                    return brand.get('name', '')
                return str(brand)
            elif field_type == 'image' and 'image' in data:
                image = data['image']
                if isinstance(image, list) and image:
                    return image[0] if isinstance(image[0], str) else image[0].get('url', '')
                elif isinstance(image, dict):
                    return image.get('url', '')
                elif isinstance(image, str):
                    return image
        except (json.JSONDecodeError, KeyError):
            continue
    return None

def extract_from_title(soup):
    """Try to extract brand from title or main headings"""
    title = soup.find('title')
    if title:
        title_text = title.get_text()
        # Look for common pet food brands in title
        pet_brands = ['purina', 'hill', 'royal canin', 'blue buffalo', 'wellness', 'orijen', 'acana', 'merrick']
        for brand in pet_brands:
            if brand.lower() in title_text.lower():
                return brand.title()
    return None

def extract_product_name(soup, url):
    """Extract the product name from the webpage"""
    try:
        # Strategy 1: Look for product title in structured data (JSON-LD)
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    # Look for Product schema
                    if data.get('@type') == 'Product' and data.get('name'):
                        return clean_product_name(data['name'])
                    # Look for nested product data
                    if 'product' in data and isinstance(data['product'], dict) and data['product'].get('name'):
                        return clean_product_name(data['product']['name'])
            except:
                continue
        
        # Strategy 2: Look for Open Graph title
        og_title = soup.find('meta', {'property': 'og:title'})
        if og_title and og_title.get('content'):
            title = og_title.get('content').strip()
            if title and not any(x in title.lower() for x in ['home', 'shop', 'category', '|']):
                return clean_product_name(title)
        
        # Strategy 3: Look for main product heading (h1)
        h1_tags = soup.find_all('h1')
        for h1 in h1_tags:
            text = h1.get_text().strip()
            if text and len(text) > 5 and len(text) < 200:  # Reasonable product name length
                return clean_product_name(text)
        
        # Strategy 4: Look for product-specific meta tags
        product_name_meta = soup.find('meta', {'name': 'product_name'}) or soup.find('meta', {'property': 'product:name'})
        if product_name_meta and product_name_meta.get('content'):
            return clean_product_name(product_name_meta.get('content'))
        
        # Strategy 5: Look for page title (cleaned up)
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
            # Clean up common title suffixes
            for suffix in [' | ', ' - ', ' – ', ' | Buy Online', ' | Chewy', ' | Target', ' | Petco', ' | PetSmart']:
                if suffix in title:
                    title = title.split(suffix)[0].strip()
            if title and len(title) > 5:
                return clean_product_name(title)
        
        return None
        
    except Exception:
        return None

def clean_product_name(name):
    """Clean up product name by removing common suffixes and formatting"""
    if not name:
        return None
    
    # Remove common website suffixes
    suffixes_to_remove = [
        ' | Chewy', ' | Target', ' | Petco', ' | PetSmart', ' | Amazon',
        ' - Chewy', ' - Target', ' - Petco', ' - PetSmart', ' - Amazon',
        ' | Buy Online', ' - Buy Online', ' | Shop Online', ' - Shop Online'
    ]
    
    cleaned = name.strip()
    for suffix in suffixes_to_remove:
        if cleaned.endswith(suffix):
            cleaned = cleaned[:-len(suffix)].strip()
    
    return cleaned if cleaned else None

def extract_product_size(soup, url):
    """Extract product size/weight from the webpage"""
    try:
        # Strategy 1: Look for size in structured data (JSON-LD)
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    # Look for weight/size in product data
                    if data.get('@type') == 'Product':
                        weight = data.get('weight') or data.get('size')
                        if weight:
                            return clean_product_size(str(weight))
                        # Look for offers with size information
                        offers = data.get('offers', [])
                        if isinstance(offers, list):
                            for offer in offers:
                                if isinstance(offer, dict):
                                    weight = offer.get('weight') or offer.get('size')
                                    if weight:
                                        return clean_product_size(str(weight))
            except:
                continue
        
        # Strategy 2: Look for size patterns in the page text
        # Get text from key areas where size info is typically found
        search_areas = []
        
        # Product title area
        h1_tags = soup.find_all('h1')
        for h1 in h1_tags:
            search_areas.append(h1.get_text())
        
        # Product details/specifications areas
        detail_selectors = [
            {'class': re.compile(r'(product|details|spec|info|size|weight)', re.I)},
            {'id': re.compile(r'(product|details|spec|info|size|weight)', re.I)}
        ]
        
        for selector in detail_selectors:
            elements = soup.find_all(['div', 'span', 'p', 'li'], selector)
            for element in elements[:5]:  # Limit to avoid too much text
                search_areas.append(element.get_text())
        
        # Also check the page title and meta description for size info
        title_tag = soup.find('title')
        if title_tag:
            search_areas.append(title_tag.get_text())
        
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            search_areas.append(meta_desc.get('content', ''))
        
        # Check Open Graph title and description
        og_title = soup.find('meta', {'property': 'og:title'})
        if og_title:
            search_areas.append(og_title.get('content', ''))
        
        og_desc = soup.find('meta', {'property': 'og:description'})
        if og_desc:
            search_areas.append(og_desc.get('content', ''))
        
        # Look for size in product code or SKU areas
        sku_elements = soup.find_all(string=re.compile(r'(product code|sku|item|model)', re.I))
        for sku_elem in sku_elements[:3]:
            parent = sku_elem.parent
            if parent:
                search_areas.append(parent.get_text())
        
        # Look for size patterns in the text
        size_patterns = [
            # Most specific patterns first (exact matches)
            r'(\d+(?:\.\d+)?\s*oz)\b',  # "2.47 oz"
            r'(\d+(?:\.\d+)?\s*lbs?)\b',  # "5.5 lb" or "5.5 lbs"
            r'(\d+(?:\.\d+)?\s*g)\b',    # "100 g"
            r'(\d+(?:\.\d+)?\s*kg)\b',   # "1.5 kg"
            r'(\d+(?:\.\d+)?\s*ml)\b',   # "250 ml"
            r'(\d+(?:\.\d+)?\s*fl\s*oz)\b',  # "8 fl oz"
            
            # More general patterns
            r'(\d+(?:\.\d+)?\s*(?:ounce|ounces))\b',
            r'(\d+(?:\.\d+)?\s*(?:pound|pounds))\b',
            r'(\d+(?:\.\d+)?\s*(?:gram|grams))\b',
            r'(\d+(?:\.\d+)?\s*(?:kilogram|kilograms))\b',
            r'(\d+(?:\.\d+)?\s*(?:milliliter|milliliters))\b',
            r'(\d+(?:\.\d+)?\s*(?:liter|liters))\b',
            r'(\d+(?:\.\d+)?\s*(?:fluid\s*ounce|fluid\s*ounces))\b',
            
            # Catch patterns in titles like "Product Name | 2.47 oz Pouch"
            r'[|\-–]\s*(\d+(?:\.\d+)?\s*oz)\s*(?:pouch|can|bag|package)?',
            r'[|\-–]\s*(\d+(?:\.\d+)?\s*lbs?)\s*(?:pouch|can|bag|package)?',
            
            # Parenthetical sizes like "(2.47oz)"
            r'\((\d+(?:\.\d+)?\s*oz)\)',
            r'\((\d+(?:\.\d+)?\s*lbs?)\)',
        ]
        
        import re
        for area_text in search_areas:
            if not area_text:
                continue
            for pattern in size_patterns:
                matches = re.findall(pattern, area_text, re.IGNORECASE)
                for match in matches:
                    cleaned_size = clean_product_size(match)
                    if cleaned_size:
                        return cleaned_size
        
        return None
        
    except Exception:
        return None

def clean_product_size(size_text):
    """Clean and standardize product size text"""
    if not size_text:
        return None
    
    import re
    
    # Remove extra whitespace and normalize
    cleaned = re.sub(r'\s+', ' ', size_text.strip())
    
    # Standardize common abbreviations
    standardizations = {
        r'\bounces?\b': 'oz',
        r'\bpounds?\b': 'lbs',
        r'\bpound\b': 'lb',
        r'\bgrams?\b': 'g',
        r'\bkilograms?\b': 'kg',
        r'\bmilliliters?\b': 'ml',
        r'\bliters?\b': 'l',
        r'\bfluid\s+ounces?\b': 'fl oz',
        r'\bfl\s+oz\b': 'fl oz'
    }
    
    for pattern, replacement in standardizations.items():
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    
    # Ensure there's no space between number and unit for common cases
    cleaned = re.sub(r'(\d+(?:\.\d+)?)\s+(oz|lb|lbs|g|kg|ml|l)\b', r'\1\2', cleaned)
    
    return cleaned if cleaned else None

def extract_life_stage(soup, url):
    """Extract life stage information (kitten/puppy, adult, senior, all)"""
    try:
        # Get text content from specific areas (avoid navigation/menus)
        product_areas = []
        
        # Look for main product content areas
        main_content = soup.find('main')
        if main_content:
            product_areas.append(main_content.get_text())
        
        # Look for product description areas
        product_desc = soup.find_all(['div', 'section'], class_=lambda x: x and any(term in str(x).lower() for term in ['product', 'description', 'details', 'info']))
        for desc in product_desc[:3]:  # Limit to first 3
            product_areas.append(desc.get_text())
        
        # Get page title and meta description (often contains life stage info)
        title = soup.find('title')
        if title:
            product_areas.append(title.get_text())
        
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc:
            product_areas.append(meta_desc.get('content', ''))
        
        # Combine all product text
        all_text = ' '.join(product_areas).lower()
        
        # First check for "all life stages" which takes priority
        all_stages_keywords = [
            'all life stages', 'all ages', 'all lifestages',
            'aafco cat food nutrient profiles for all life stages',
            'aafco dog food nutrient profiles for all life stages',
            'formulated for all life stages',
            'complete and balanced for all life stages',
            'suitable for all life stages',
            'meets aafco for all life stages',
            'aafco all life stages'
        ]
        
        # Check for all life stages patterns first (most specific)
        for keyword in all_stages_keywords:
            if keyword in all_text:
                return "all"
        
        # Look for specific age categories with very specific patterns
        import re
        
        # More restrictive patterns to avoid false positives
        kitten_patterns = [
            r'\bfor\s+kittens?\b',           # "for kitten" or "for kittens"
            r'\bkitten\s+food\b',            # "kitten food"
            r'\bkitten\s+formula\b',         # "kitten formula"
            r'\bkitten\s+recipe\b'           # "kitten recipe"
        ]
        
        puppy_patterns = [
            r'\bfor\s+puppies?\b',           # "for puppy" or "for puppies"
            r'\bpuppy\s+food\b',             # "puppy food"
            r'\bpuppy\s+formula\b',          # "puppy formula"
            r'\bpuppy\s+recipe\b'            # "puppy recipe"
        ]
        
        senior_patterns = [
            r'\bfor\s+senior\b',             # "for senior"
            r'\bsenior\s+(?:cat|dog|food|formula)\b',  # "senior cat/dog/food/formula"
            r'\b(?:7|8|9|10|11|12)\+\s*(?:years?|cat|dog)\b',  # "7+ years" etc
            r'\bmature\s+(?:cat|dog)\b',     # "mature cat/dog"
            r'\baged\s+(?:cat|dog)\b'        # "aged cat/dog"
        ]
        
        # Check for specific patterns (most restrictive first)
        for pattern in senior_patterns:
            if re.search(pattern, all_text):
                return "senior"
        
        for pattern in kitten_patterns:
            if re.search(pattern, all_text):
                return "kitten"
        
        for pattern in puppy_patterns:
            if re.search(pattern, all_text):
                return "puppy"
        
        # Default to adult if no specific life stage found
        return "adult"
        
    except Exception as e:
        return "adult"


def extract_life_stage_from_url(url):
    """Extract life stage from direct image URLs based on filename"""
    try:
        url_lower = url.lower()
        
        # Life stage keywords
        kitten_keywords = ['kitten', 'kittens']
        puppy_keywords = ['puppy', 'puppies'] 
        senior_keywords = ['senior', 'seniors', 'mature', 'aged']
        all_stages_keywords = ['all-life-stages', 'all-ages', 'all-stages', 'life-stages']
        
        # Check URL for life stage indicators
        if any(keyword in url_lower for keyword in all_stages_keywords):
            return "all"
        
        if any(keyword in url_lower for keyword in kitten_keywords):
            return "kitten"
        
        if any(keyword in url_lower for keyword in puppy_keywords):
            return "puppy"
            
        if any(keyword in url_lower for keyword in senior_keywords):
            return "senior"
        
        return "adult"
        
    except Exception:
        return "adult"

def clean_extra_content(ingredient_text):
    """Remove unwanted trailing content from ingredient lists"""
    import re
    
    # Remove common unwanted trailing content
    unwanted_patterns = [
        r'view all ingredients.*',
        r'download.*ingredient.*list.*',
        r'open in new window.*',
        r'contact us.*',
        r'reviews.*',
        r'discover similar.*',
        r'sitemap.*',
        r'navigate to.*',
        r'all rights reserved.*',
        r'trademark.*',
        r'©.*',
        r'facebook.*',
        r'twitter.*',
        r'youtube.*',
        r'instagram.*',
        r'feed.*instructions.*',
        r'guaranteed.*analysis.*',
        r'nutritional.*info.*',
        # Marketing phrases
        r'tantalize.*',
        r'gourmet.*',
        r'delicious flavor.*',
        r'hand-crafted.*',
        r'toppers offer.*',
        r'invite your cat.*',
        r'experience gourmet.*',
        r'looks good enough for you.*',
        r'crafted especially for.*',
        r'attention to detail.*',
        r'unique taste cats love.*',
        r'tender bites.*',
        r'savory broth.*',
        r'most refined.*',
        r'between-meal snack.*',
        r'complement tray.*',
        r'single-serve.*',
        r'adult cat food complement.*',
        r'made to meet your.*',
        r'ingredient criteria.*',
        r'serve fancy feast.*',
        r'favorite fancy feast.*',
        r'add delicious flavor.*',
        r'real high quality ingredients.*',
        r'perfect way.*',
        r'grain free.*appetizers.*',
        r'cats alone or over.*',
        r'the right size for.*'
    ]
    
    cleaned_text = ingredient_text
    for pattern in unwanted_patterns:
        cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE | re.DOTALL)
    
    # Clean up any double spaces or trailing commas
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    cleaned_text = re.sub(r',\s*$', '', cleaned_text)
    cleaned_text = cleaned_text.strip()
    
    # Remove unwanted characters from individual ingredients and at the end
    if ',' in cleaned_text:
        # Split by commas, remove unwanted characters from each ingredient, then rejoin
        ingredients = []
        for ing in cleaned_text.split(','):
            cleaned = ing.strip()
            while cleaned and cleaned[-1] in '.\\"\',;':
                cleaned = cleaned[:-1].strip()
            
            # Check for patterns where valid ingredient is contaminated with invalid codes
            # Pattern 1: "Blue 2. N600123" (period + space + invalid code)
            if '. ' in cleaned and len(cleaned.split('. ')) == 2:
                first_part, second_part = cleaned.split('. ', 1)
                if is_valid_ingredient(first_part) and not is_valid_ingredient(second_part):
                    ingredients.append(first_part)
                elif is_valid_ingredient(cleaned):
                    ingredients.append(cleaned)
            # Pattern 2: "Blue 2 D600724" (space + invalid code starting with letter+numbers)
            elif ' ' in cleaned and len(cleaned.split()) >= 2:
                parts = cleaned.split()
                # Check if last part looks like an invalid code (letter followed by many digits)
                last_part = parts[-1]
                if (len(parts) >= 2 and 
                    re.match(r'^[A-Za-z]\d{5,}$', last_part) and  # Pattern like D600724, N600123
                    not is_valid_ingredient(last_part)):
                    # Rejoin everything except the last invalid part
                    clean_part = ' '.join(parts[:-1])
                    if is_valid_ingredient(clean_part):
                        ingredients.append(clean_part)
                elif cleaned and is_valid_ingredient(cleaned):
                    ingredients.append(cleaned)
            elif cleaned and is_valid_ingredient(cleaned):
                ingredients.append(cleaned)
        cleaned_text = ', '.join(ingredients)
    
    # Remove any trailing unwanted characters
    while cleaned_text and cleaned_text[-1] in '.\\"\',;':
        cleaned_text = cleaned_text[:-1].strip()
    
    return cleaned_text

def is_valid_ingredient(ingredient):
    """Check if an ingredient is valid and not a website error/typo"""
    if not ingredient or len(ingredient.strip()) < 2:
        return False
    
    ingredient = ingredient.strip().lower()
    
    # Allow known valid patterns first (vitamins, E-numbers, etc.)
    # But only for specific known prefixes
    if re.match(r'^[be]\d{1,3}$', ingredient):  # B1, E300, etc. (common vitamin/additive prefixes)
        return True
    if re.match(r'^[a-z]{1,2}-\d+$', ingredient):  # B-12, etc.
        return True
    if 'vitamin' in ingredient or 'supplement' in ingredient:
        return True
    
    # Exclude random alphanumeric codes (like k600323, abc123, etc.)
    # Pattern: letters followed by many numbers (3+)
    if re.match(r'^[a-z]{1,3}\d{3,}$', ingredient):  # e.g., k600323, ab12345
        return False
    # Pattern: many numbers followed by few letters
    if re.match(r'^\d{3,}[a-z]{1,3}$', ingredient):  # e.g., 12345k, 600ab
        return False
    # Pattern: alternating letters and numbers (multiple digit groups)
    if re.search(r'\d.*[a-z].*\d', ingredient) and len(ingredient) > 3:  # z2z3z4, abc123def456
        return False
    
    # Exclude single characters or very short nonsensical combinations
    if len(ingredient) <= 2 and not ingredient.isalpha():
        return False
    
    # Exclude items that are mostly numbers with minimal letters (but allow vitamins/E-numbers)
    letter_count = sum(1 for c in ingredient if c.isalpha())
    number_count = sum(1 for c in ingredient if c.isdigit())
    if (number_count > 0 and letter_count > 0 and 
        number_count >= letter_count * 3 and  # More strict ratio
        len(ingredient) > 4):  # Don't apply to short ingredients
        return False
    
    return True

def format_ingredient_list(ingredient_text):
    """Universal function to format ingredient lists with proper comma separation"""
    import re
    
    # Convert British spelling "fibre" to American spelling "fiber"
    ingredient_text = re.sub(r'\bfibre\b', 'fiber', ingredient_text, flags=re.IGNORECASE)
    
    # Remove "Vitamins" wrapper and keep only the individual vitamins
    # Pattern: "Vitamins (Vitamin E Supplement, Vitamin B3 (Niacin Supplement), ...)"
    # Should become: "Vitamin E Supplement, Vitamin B3 (Niacin Supplement), ..."
    
    # Use a more robust approach to handle nested parentheses
    def extract_vitamins_content(text):
        # Find "Vitamins (" and then match balanced parentheses
        start_pattern = r'\bVitamins\s*\('
        match = re.search(start_pattern, text, re.IGNORECASE)
        if match:
            start_pos = match.end() - 1  # Position of opening parenthesis
            paren_count = 0
            end_pos = start_pos
            
            for i, char in enumerate(text[start_pos:], start_pos):
                if char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                    if paren_count == 0:
                        end_pos = i
                        break
            
            if paren_count == 0:  # Found matching closing parenthesis
                vitamins_content = text[start_pos + 1:end_pos]  # Content inside parentheses
                # Replace the entire "Vitamins (...)" with just the content
                return text[:match.start()] + vitamins_content + text[end_pos + 1:]
        
        return text
    
    # Remove "Minerals" wrapper and keep only the individual minerals
    # Pattern: "Minerals (Zinc Proteinate, Iron Proteinate, Potassium Chloride, ...)"
    # Should become: "Zinc Proteinate, Iron Proteinate, Potassium Chloride, ..."
    
    def extract_minerals_content(text):
        # Find "Minerals (" and then match balanced parentheses
        start_pattern = r'\bMinerals\s*\('
        match = re.search(start_pattern, text, re.IGNORECASE)
        if match:
            start_pos = match.end() - 1  # Position of opening parenthesis
            paren_count = 0
            end_pos = start_pos
            
            for i, char in enumerate(text[start_pos:], start_pos):
                if char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                    if paren_count == 0:
                        end_pos = i
                        break
            
            if paren_count == 0:  # Found matching closing parenthesis
                minerals_content = text[start_pos + 1:end_pos]  # Content inside parentheses
                # Replace the entire "Minerals (...)" with just the content
                return text[:match.start()] + minerals_content + text[end_pos + 1:]
        
        return text
    
    ingredient_text = extract_vitamins_content(ingredient_text)
    ingredient_text = extract_minerals_content(ingredient_text)
    
    # Remove any unwanted characters at the end of the entire text first
    ingredient_text = ingredient_text.strip()
    while ingredient_text and ingredient_text[-1] in '.\\"\',;':
        ingredient_text = ingredient_text[:-1].strip()
    
    # If already has good comma separation, clean and return
    if ', ' in ingredient_text and ingredient_text.count(',') > 3:
        # Split into individual ingredients, remove unwanted characters from each, then rejoin
        ingredients = []
        for ing in ingredient_text.split(','):
            cleaned = ing.strip()
            
            # Remove trailing unwanted characters
            while cleaned and cleaned[-1] in '.\\"\',;':
                cleaned = cleaned[:-1].strip()
            
            # Check for patterns where valid ingredient is contaminated with invalid codes
            # Pattern 1: "Blue 2. N600123" (period + space + invalid code)
            if '. ' in cleaned and len(cleaned.split('. ')) == 2:
                first_part, second_part = cleaned.split('. ', 1)
                if is_valid_ingredient(first_part) and not is_valid_ingredient(second_part):
                    ingredients.append(first_part)
                elif is_valid_ingredient(cleaned):
                    ingredients.append(cleaned)
            # Pattern 2: "Blue 2 D600724" (space + invalid code starting with letter+numbers)
            elif ' ' in cleaned and len(cleaned.split()) >= 2:
                parts = cleaned.split()
                # Check if last part looks like an invalid code (letter followed by many digits)
                last_part = parts[-1]
                if (len(parts) >= 2 and 
                    re.match(r'^[A-Za-z]\d{5,}$', last_part) and  # Pattern like D600724, N600123
                    not is_valid_ingredient(last_part)):
                    # Rejoin everything except the last invalid part
                    clean_part = ' '.join(parts[:-1])
                    if is_valid_ingredient(clean_part):
                        ingredients.append(clean_part)
                elif cleaned and is_valid_ingredient(cleaned):
                    ingredients.append(cleaned)
            elif cleaned and is_valid_ingredient(cleaned):
                ingredients.append(cleaned)
        
        result = ', '.join(ingredients)
        
        # Apply generic ending cleanup to early return path too
        generic_endings_patterns = [
            r',?\s*and\s+other\s+minerals?\s*$',
            r',?\s*and\s+other\s+vitamins?\s*$', 
            r',?\s*and\s+other\s+supplements?\s*$',
            r',?\s*and\s+other\s+additives?\s*$',
            r',?\s*and\s+other\s+ingredients?\s*$',
            r',?\s*etc\.?\s*$',
            r',?\s*and\s+more\s*$'
        ]
        
        for pattern in generic_endings_patterns:
            original_text = result
            result = re.sub(pattern, '', result, flags=re.IGNORECASE).strip()
            if result != original_text:  # If a substitution was made, break
                break
        
        return result
    
    # Apply universal comma formatting for ingredients that run together
    formatted_text = ingredient_text
    
    # Special handling for dry food patterns that start with meat
    # Handle patterns like "ChickenRice" -> "Chicken, Rice"
    formatted_text = re.sub(r'(Chicken|Beef|Salmon|Turkey|Duck|Lamb)(Rice|Meal|Protein)', r'\1, \2', formatted_text)
    
    # Handle patterns like "RicePoultry" -> "Rice, Poultry"  
    formatted_text = re.sub(r'(Rice|Corn|Wheat|Oat)(Poultry|Chicken|Beef|Protein|Meal)', r'\1, \2', formatted_text)
    
    # Handle "Poultry By-Product Meal" pattern
    formatted_text = re.sub(r'(Rice|Corn|Wheat|Oat)(Poultry By-Product)', r'\1, \2', formatted_text)
    
    # Insert commas before capital letters that start new ingredients
    # Pattern: lowercase/number/parenthesis followed by capital letter (common pattern across brands)
    formatted_text = re.sub(r'([a-z0-9\)])([A-Z][a-z])', r'\1, \2', formatted_text)
    
    # Fix common issues across brands
    formatted_text = re.sub(r', (Vitamin [A-Z]-?\d+)', r', \1', formatted_text)  # Keep vitamin names together
    formatted_text = re.sub(r'Starch-, Modified', 'Starch-Modified', formatted_text)  # Fix modified starch
    formatted_text = re.sub(r'B-, (\d)', r'B-\1', formatted_text)  # Fix B-vitamins
    formatted_text = re.sub(r'Oil-, ', 'Oil, ', formatted_text)  # Fix oil names
    formatted_text = re.sub(r'Acid-, ', 'Acid, ', formatted_text)  # Fix acid names
    formatted_text = re.sub(r'Meal-, ', 'Meal, ', formatted_text)  # Fix meal names
    formatted_text = re.sub(r'By-, Product', 'By-Product', formatted_text)  # Fix by-product
    
    # Handle common ingredient run-together patterns
    # Fish/meat + other ingredients
    formatted_text = re.sub(r'(Salmon|Chicken|Beef|Turkey|Duck|Tuna|Lamb)(Meal|Broth|Oil|Fat)', r'\1, \2', formatted_text)
    
    # Fix double commas
    formatted_text = re.sub(r',\s*,', ',', formatted_text)
    
    # Clean up any leading/trailing commas
    formatted_text = re.sub(r'^,\s*', '', formatted_text)
    formatted_text = re.sub(r',\s*$', '', formatted_text)
    
    # Final cleanup: split ingredients, remove periods and unwanted characters from each, then rejoin
    if ',' in formatted_text:
        ingredients = []
        for ing in formatted_text.split(','):
            cleaned = ing.strip()
            # Remove trailing unwanted characters (periods, slashes, quotes, etc.)
            while cleaned and cleaned[-1] in '.\\"\',;':
                cleaned = cleaned[:-1].strip()
            
            # Check for patterns where valid ingredient is contaminated with invalid codes
            # Pattern 1: "Blue 2. N600123" (period + space + invalid code)
            if '. ' in cleaned and len(cleaned.split('. ')) == 2:
                first_part, second_part = cleaned.split('. ', 1)
                if is_valid_ingredient(first_part) and not is_valid_ingredient(second_part):
                    ingredients.append(first_part)
                elif is_valid_ingredient(cleaned):
                    ingredients.append(cleaned)
            # Pattern 2: "Blue 2 D600724" (space + invalid code starting with letter+numbers)
            elif ' ' in cleaned and len(cleaned.split()) >= 2:
                parts = cleaned.split()
                # Check if last part looks like an invalid code (letter followed by many digits)
                last_part = parts[-1]
                if (len(parts) >= 2 and 
                    re.match(r'^[A-Za-z]\d{5,}$', last_part) and  # Pattern like D600724, N600123
                    not is_valid_ingredient(last_part)):
                    # Rejoin everything except the last invalid part
                    clean_part = ' '.join(parts[:-1])
                    if is_valid_ingredient(clean_part):
                        ingredients.append(clean_part)
                elif cleaned and is_valid_ingredient(cleaned):
                    ingredients.append(cleaned)
            elif cleaned and is_valid_ingredient(cleaned):
                ingredients.append(cleaned)
        formatted_text = ', '.join(ingredients)
    
    # Remove any remaining unwanted characters at the end
    while formatted_text and formatted_text[-1] in '.\\"\',;':
        formatted_text = formatted_text[:-1].strip()
    
    # Remove generic endings that don't provide specific ingredient information
    generic_endings_patterns = [
        r',?\s*and\s+other\s+minerals?\s*$',
        r',?\s*and\s+other\s+vitamins?\s*$', 
        r',?\s*and\s+other\s+supplements?\s*$',
        r',?\s*and\s+other\s+additives?\s*$',
        r',?\s*and\s+other\s+ingredients?\s*$',
        r',?\s*etc\.?\s*$',
        r',?\s*and\s+more\s*$'
    ]
    
    for pattern in generic_endings_patterns:
        original_text = formatted_text
        formatted_text = re.sub(pattern, '', formatted_text, flags=re.IGNORECASE).strip()
        if formatted_text != original_text:  # If a substitution was made, break
            break
    
    return formatted_text

def extract_applaws_dropdown_data(url):
    """Extract all Applaws dropdown data (ingredients, guaranteed analysis, nutritional info) in one browser session"""
    import re
    from bs4 import BeautifulSoup
    
    try:
        from selenium_scraper import _get_browser
        import time
        from selenium.webdriver.common.by import By
        
        results = {}
        
        driver = _get_browser()
        driver.get(url)
        time.sleep(5)  # Allow page to load completely
        
        # Find all dropdown buttons
        dropdown_buttons = [
            ('ingredients', "//*[contains(text(), 'Ingredients')]"),
            ('nutritional', "//*[contains(text(), 'Nutritional Information') or contains(text(), 'Guaranteed Analysis') or contains(text(), 'Nutrition')]")
        ]
        
        for dropdown_type, xpath in dropdown_buttons:
            try:
                elements = driver.find_elements(By.XPATH, xpath)
                
                for element in elements:
                    element_text = element.text.strip()
                    
                    # Click the appropriate dropdown
                    should_click = False
                    if dropdown_type == 'ingredients' and element_text == 'Ingredients':
                        should_click = True
                    elif dropdown_type == 'nutritional' and element_text in ['Nutritional Information', 'Guaranteed Analysis', 'Nutrition']:
                        should_click = True
                    
                    if should_click:
                        # Click to reveal content
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", element)
                        time.sleep(5)  # Wait for content to load
                        
                        # Get the revealed content
                        new_source = driver.page_source
                        soup_selenium = BeautifulSoup(new_source, 'html.parser')
                        page_text = soup_selenium.get_text()
                        
                        if dropdown_type == 'ingredients':
                            # Extract ingredients - find the clean list after "Ingredients" keyword
                            
                            # Look for the complete ingredients list after "Ingredients" keyword
                            # Pattern: "Ingredients Chicken Breast, Chicken Broth, Rice, Rice Flour."
                            # Look for exact match of the ingredients pattern
                            # From debug: "Ingredients Chicken Breast, Chicken Broth, Rice, Rice Flour."
                            # From debug: "Ingredients Tuna Fillet, Fish Broth, Rice"
                            
                            # Simple approach: find "Ingredients" followed by food items and stop before next section
                            ingredients_pattern = r'ingredients\s+([a-z][a-z\s,]*(?:chicken|tuna|fish|beef|turkey|lamb|rice|flour|broth|water|oil)[a-z\s,]*?)(?=\s*\.\s*nutritional|\s*nutritional|\s*guaranteed|\s*peek|\s*$)'
                            ingredient_match = re.search(ingredients_pattern, page_text, re.IGNORECASE)
                            
                            if ingredient_match:
                                clean_ingredients = ingredient_match.group(1).strip()
                                # Remove the "ingredients" keyword if it got captured
                                clean_ingredients = re.sub(r'^ingredients\s*', '', clean_ingredients, flags=re.IGNORECASE)
                                # Remove extra whitespace and newlines
                                clean_ingredients = re.sub(r'\s+', ' ', clean_ingredients)
                                # Remove trailing punctuation
                                clean_ingredients = re.sub(r'[^\w\s,().-]+$', '', clean_ingredients)
                                if clean_ingredients.endswith('.'):
                                    clean_ingredients = clean_ingredients[:-1]
                                clean_ingredients = clean_ingredients.strip()
                                
                                # Validate it's a proper ingredient list (has commas and food-related terms)
                                if (len(clean_ingredients) > 5 and 
                                    ',' in clean_ingredients and
                                    clean_ingredients.count(',') >= 1 and  # Should have at least 2 ingredients
                                    any(word in clean_ingredients.lower() for word in ['tuna', 'chicken', 'fish', 'beef', 'turkey', 'lamb', 'broth', 'water', 'rice', 'oil'])):
                                    # Convert to array format
                                    ingredients_array = [ingredient.strip() for ingredient in clean_ingredients.split(',')]
                                    results['ingredients'] = ingredients_array
                            
                            # If no ingredients found with main patterns, try fallback
                            if 'ingredients' not in results:
                                # Fallback patterns if the first approach doesn't work
                                ingredient_patterns = [
                                    # Pattern for "Ingredients X, Y, Z" format
                                    r'ingredients[:\s]+([a-z][^.]*?(?:,\s*[a-z][^,]*){1,})',
                                    # Pattern for clean ingredient lists (protein + at least 2 other items)
                                    r'((?:chicken|fish|tuna|beef|turkey|lamb)[^,]*(?:,\s*[a-z][^,]*){1,})',
                                    # Pattern for broth-based ingredients
                                    r'((?:chicken|fish|tuna|beef|turkey|lamb)\s+(?:broth|fillet)[^,]*(?:,\s*[a-z][^,]*){1,})'
                                ]
                                
                                for pattern in ingredient_patterns:
                                    matches = re.findall(pattern, page_text, re.IGNORECASE)
                                    for match in matches:
                                        match = match.strip()
                                        match = re.sub(r'\s+', ' ', match)
                                        match = re.sub(r'^[^\w]+', '', match)
                                        match = re.sub(r'[^\w\s,().-]+$', '', match)
                                        
                                        # Must be short enough to be just ingredients (not marketing text)
                                        if (len(match) > 10 and len(match) < 200 and 
                                            match.count(',') >= 1 and
                                            not any(bad in match.lower() for bad in ['carrageenan', 'additive free', 'only', 'ingredients', 'feed with', 'complete', 'balanced diet', 'applaws']) and
                                            any(word in match.lower() for word in ['chicken', 'fish', 'tuna', 'beef', 'turkey', 'lamb', 'broth', 'water', 'rice', 'oil'])):
                                            # Convert to array format
                                            ingredients_array = [ingredient.strip() for ingredient in match.split(',')]
                                            results['ingredients'] = ingredients_array
                                            break
                                    
                                    if 'ingredients' in results:
                                        break
                        
                        elif dropdown_type == 'nutritional':
                            # Extract guaranteed analysis
                            ga_patterns = [
                                # Pattern for protein-first format
                                r'(crude\s+protein[^%]+%[^,]*,\s*crude\s+fat[^%]+%[^,]*,\s*crude\s+fiber[^%]+%[^,]*,\s*moisture[^%]+%[^.]*)',
                                r'(crude\s+protein[^.]+fat[^.]+fiber[^.]+moisture[^.]*%)',
                                r'(protein[^.]*%[^.]*fat[^.]*%[^.]*fiber[^.]*%[^.]*moisture[^.]*%)',
                                # Pattern for fat-first format (like kitten tuna)
                                r'(crude\s+fat[^%]+%[^,]*,\s*crude\s+fib[a-z]*[^%]+%[^,]*,\s*moisture[^%]+%[^,]*,\s*crude\s+protein[^%]+%)',
                                # More flexible patterns that can capture in any order
                                r'((?:crude\s+)?(?:fat|protein|fiber|fibre|moisture)[^%]*%[^,]*,\s*(?:crude\s+)?(?:fat|protein|fiber|fibre|moisture)[^%]*%[^,]*,\s*(?:crude\s+)?(?:fat|protein|fiber|fibre|moisture)[^%]*%[^,]*,\s*(?:crude\s+)?(?:fat|protein|fiber|fibre|moisture)[^%]*%)',
                                # Simplified pattern that captures any sequence with multiple nutritional components
                                r'((?:crude\s+)?(?:fat|protein|fib[a-z]*|moisture)[^%]*%[^.]*(?:,\s*[^.]*%[^.]*){2,})'
                            ]
                            
                            for pattern in ga_patterns:
                                matches = re.findall(pattern, page_text, re.IGNORECASE)
                                for match in matches:
                                    match = match.strip()
                                    match = re.sub(r'\s+', ' ', match)
                                    match = re.sub(r'^[^\w]+', '', match)
                                    match = re.sub(r'[^\w\.%\)]+$', '', match)
                                    if match.endswith('.'):
                                        match = match[:-1]
                                    
                                    # DIRECT SEARCH: Extract ONLY the specific percentages we need
                                    # Search for the specific guaranteed analysis components in the page text
                                    protein_match = re.search(r'Crude\s+Protein\s+\(min\)\s+(\d+(?:\.\d+)?%)', page_text, re.IGNORECASE)
                                    fat_match = re.search(r'Crude\s+Fat\s+\(min\)\s+(\d+(?:\.\d+)?%)', page_text, re.IGNORECASE)
                                    moisture_match = re.search(r'Moisture\s+\(max\)\s+(\d+(?:\.\d+)?%)', page_text, re.IGNORECASE)
                                    
                                    # If we found at least protein and one other component, construct clean result
                                    if protein_match and (fat_match or moisture_match):
                                        components = []
                                        components.append(f"Crude Protein (min) {protein_match.group(1)}")
                                        if fat_match:
                                            components.append(f"Crude Fat (min) {fat_match.group(1)}")
                                        if moisture_match:
                                            components.append(f"Moisture (max) {moisture_match.group(1)}")
                                        
                                        clean_analysis = ", ".join(components)
                                        results['guaranteed_analysis'] = clean_analysis
                                        break
                                
                                if 'guaranteed_analysis' in results:
                                    break
                            
                            # Extract nutritional info (calories)
                            calorie_patterns = [
                                r'(\d+(?:\.\d+)?\s*kcal/kg)',
                                r'(\d+(?:\.\d+)?\s*kcal\s*/\s*kg)',
                                r'(\d+(?:\.\d+)?\s*kilocalories?\s*/\s*kg)',
                                r'(\d+(?:\.\d+)?\s*cal/kg)',
                            ]
                            
                            for pattern in calorie_patterns:
                                matches = re.findall(pattern, page_text, re.IGNORECASE)
                                for match in matches:
                                    match = match.strip()
                                    match = re.sub(r'\s+', ' ', match)
                                    match = re.sub(r'\s*/\s*', '/', match)
                                    
                                    calorie_num = re.findall(r'(\d+(?:\.\d+)?)', match)
                                    if calorie_num and 50 <= float(calorie_num[0]) <= 10000:
                                        results['nutritional_info'] = {'calories': match}
                                        break
                                
                                if 'nutritional_info' in results:
                                    break
                        
                        break  # Found and clicked this dropdown type
                
            except Exception as e:
                continue
        
        return results
        
    except Exception as e:
        return {}

def extract_nutritional_info(soup, url):
    """Extract nutritional information including calories from the webpage"""
    import re
    
    try:
        nutritional_info = {}
        
        # APPLAWS DROPDOWN DETECTION: Use Selenium to click nutritional information dropdowns
        # Applaws hides nutritional info in clickable sections that need to be revealed
        if 'applaws.com' in url.lower():
            try:
                from selenium_scraper import _get_browser
                import time
                from selenium.webdriver.common.by import By
                
                driver = _get_browser()
                driver.get(url)
                time.sleep(5)  # Allow page to load completely
                
                # Look for clickable "Nutritional Information" sections
                nutrition_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), 'Nutritional Information') or contains(text(), 'Nutrition') or contains(text(), 'Guaranteed Analysis')]")
                
                for i, button in enumerate(nutrition_buttons):
                    try:
                        element_text = button.text.strip()
                        
                        # Look for nutritional information dropdown text
                        if element_text in ['Nutritional Information', 'Nutrition', 'Guaranteed Analysis']:
                            # Click to reveal hidden nutritional content
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                            time.sleep(1)
                            driver.execute_script("arguments[0].click();", button)
                            time.sleep(5)  # Wait for content to load
                            
                            # Get the new page content and extract nutritional info
                            new_source = driver.page_source
                            soup_selenium = BeautifulSoup(new_source, 'html.parser')
                            page_text = soup_selenium.get_text()
                            
                            # Look for calorie patterns directly in the page text
                            
                            # Look for kcal/kg patterns
                            calorie_patterns = [
                                r'(\d+(?:\.\d+)?\s*kcal/kg)',
                                r'(\d+(?:\.\d+)?\s*kcal\s*/\s*kg)',
                                r'(\d+(?:\.\d+)?\s*kilocalories?\s*/\s*kg)',
                                r'(\d+(?:\.\d+)?\s*cal/kg)',
                            ]
                            
                            for pattern in calorie_patterns:
                                matches = re.findall(pattern, page_text, re.IGNORECASE)
                                for match in matches:
                                    # Clean up the match
                                    match = match.strip()
                                    # Standardize the format
                                    match = re.sub(r'\s+', ' ', match)
                                    match = re.sub(r'\s*/\s*', '/', match)
                                    
                                    # Validate it looks like a reasonable calorie value
                                    calorie_num = re.findall(r'(\d+(?:\.\d+)?)', match)
                                    if calorie_num and 50 <= float(calorie_num[0]) <= 10000:  # Reasonable calorie range
                                        nutritional_info['calories'] = match
                                        break
                                
                                if 'calories' in nutritional_info:
                                    break
                            
                            break  # Found and clicked the nutrition button
                            
                    except Exception as e:
                        continue
                
            except Exception as e:
                # Fall through to regular extraction if Selenium fails
                pass
        
        # Fallback: Try to extract from static HTML if Selenium didn't work
        if not nutritional_info:
            page_text = soup.get_text()
            
            # Look for calorie patterns in the static content
            calorie_patterns = [
                r'(\d+(?:\.\d+)?\s*kcal/kg)',
                r'(\d+(?:\.\d+)?\s*kcal\s*/\s*kg)',
                r'(\d+(?:\.\d+)?\s*kilocalories?\s*/\s*kg)',
                r'(\d+(?:\.\d+)?\s*cal/kg)',
            ]
            
            import re
            for pattern in calorie_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    match = match.strip()
                    match = re.sub(r'\s+', ' ', match)
                    match = re.sub(r'\s*/\s*', '/', match)
                    
                    # Validate calorie value
                    calorie_num = re.findall(r'(\d+(?:\.\d+)?)', match)
                    if calorie_num and 50 <= float(calorie_num[0]) <= 10000:
                        nutritional_info['calories'] = match
                        break
                
                if 'calories' in nutritional_info:
                    break
        
        # Return the nutritional info object or None if no calories found
        return nutritional_info if nutritional_info else None
        
    except Exception:
        return None

def extract_guaranteed_analysis(soup, url):
    """Extract guaranteed analysis information from the webpage using the same dropdown as nutritional info"""
    import re
    
    try:
        # For Applaws, we should reuse the same dropdown content that's already been clicked for nutritional info
        # This is more efficient and avoids multiple browser instances
        if 'applaws.com' in url.lower():
            try:
                from selenium_scraper import _get_browser
                import time
                from selenium.webdriver.common.by import By
                
                driver = _get_browser()
                driver.get(url)
                time.sleep(5)  # Allow page to load completely
                
                # Look for clickable "Nutritional Information" or "Guaranteed Analysis" sections
                analysis_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), 'Nutritional Information') or contains(text(), 'Guaranteed Analysis') or contains(text(), 'Nutrition')]")
                
                for i, button in enumerate(analysis_buttons):
                    try:
                        element_text = button.text.strip()
                        
                        # Look for nutritional information dropdown text
                        if element_text in ['Nutritional Information', 'Guaranteed Analysis', 'Nutrition']:
                            # Click to reveal hidden content
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                            time.sleep(1)
                            driver.execute_script("arguments[0].click();", button)
                            time.sleep(5)  # Wait for content to load
                            
                            # Get the new page content and extract guaranteed analysis
                            new_source = driver.page_source
                            soup_selenium = BeautifulSoup(new_source, 'html.parser')
                            page_text = soup_selenium.get_text()
                            
                            # Look for guaranteed analysis patterns directly in the page text
                            
                            # Try multiple patterns to find guaranteed analysis after clicking
                            # ULTRA-PRECISE: Extract ONLY the exact percentages, nothing else
                            patterns = [
                                # Pattern 1: Extract the exact sequence from your screenshot
                                r'Guaranteed\s+Analysis\s+(Crude\s+Protein\s+\([^)]+\)\s+\d+(?:\.\d+)?%(?:\s*,\s*Crude\s+Fat\s+\([^)]+\)\s+\d+(?:\.\d+)?%)?(?:\s*,\s*(?:Crude\s+)?Fiber\s+\([^)]+\)\s+\d+(?:\.\d+)?%)?(?:\s*,\s*Moisture\s+\([^)]+\)\s+\d+(?:\.\d+)?%)?)',
                                
                                # Pattern 2: Just the percentages part without "Guaranteed Analysis" prefix
                                r'(Crude\s+Protein\s+\([^)]+\)\s+\d+(?:\.\d+)?%(?:\s*,\s*Crude\s+Fat\s+\([^)]+\)\s+\d+(?:\.\d+)?%)?(?:\s*,\s*(?:Crude\s+)?Fiber\s+\([^)]+\)\s+\d+(?:\.\d+)?%)?(?:\s*,\s*Moisture\s+\([^)]+\)\s+\d+(?:\.\d+)?%)?)(?=\s+(?:Peek|Ideal|Added|With|Made|FAQs|Popular|$))',
                                
                                # Pattern 3: Very specific - match the exact format from screenshot
                                r'(Crude\s+Protein\s+\(min\)\s+\d+%,\s+Crude\s+Fat\s+\(min\)\s+\d+%,\s+Moisture\s+\(max\)\s+\d+%)',
                                
                                # Pattern 4: Flexible but bounded by next sentence
                                r'(Crude\s+Protein\s+\([^)]+\)\s+\d+(?:\.\d+)?%[^.]*?(?:,\s*[^.]*?){0,3})\s+(?=Peek\s+at|Ideal\s+balance|Added\s+calcium|With\s+vitamins|Made\s+without|FAQs|Popular|$)'
                            ]
                            
                            # DIRECT SEARCH: Look for the exact percentages in the entire page text
                            # This bypasses all complex patterns and just finds what we need
                            
                            # Search for the specific guaranteed analysis components
                            protein_match = re.search(r'Crude\s+Protein\s+\(min\)\s+(\d+(?:\.\d+)?%)', page_text, re.IGNORECASE)
                            fat_match = re.search(r'Crude\s+Fat\s+\(min\)\s+(\d+(?:\.\d+)?%)', page_text, re.IGNORECASE)
                            moisture_match = re.search(r'Moisture\s+\(max\)\s+(\d+(?:\.\d+)?%)', page_text, re.IGNORECASE)
                            
                            # If we found at least protein and one other component, construct clean result
                            if protein_match and (fat_match or moisture_match):
                                components = []
                                components.append(f"Crude Protein (min) {protein_match.group(1)}")
                                if fat_match:
                                    components.append(f"Crude Fat (min) {fat_match.group(1)}")
                                if moisture_match:
                                    components.append(f"Moisture (max) {moisture_match.group(1)}")
                                
                                clean_analysis = ", ".join(components)
                                return clean_analysis
                            
                            break  # Found and clicked the analysis button
                            
                    except Exception as e:
                        continue
                
            except Exception as e:
                # Fall through to regular extraction if Selenium fails
                pass
        
        # Fallback: Try to extract from static HTML if Selenium didn't work
        page_text = soup.get_text()
        
        # DIRECT SEARCH in static content: Look for the exact percentages
        # Search for the specific guaranteed analysis components in the entire page text
        protein_match = re.search(r'Crude\s+Protein\s+\(min\)\s+(\d+(?:\.\d+)?%)', page_text, re.IGNORECASE)
        fat_match = re.search(r'Crude\s+Fat\s+\(min\)\s+(\d+(?:\.\d+)?%)', page_text, re.IGNORECASE)
        moisture_match = re.search(r'Moisture\s+\(max\)\s+(\d+(?:\.\d+)?%)', page_text, re.IGNORECASE)
        
        # If we found at least protein and one other component, construct clean result
        if protein_match and (fat_match or moisture_match):
            components = []
            components.append(f"Crude Protein (min) {protein_match.group(1)}")
            if fat_match:
                components.append(f"Crude Fat (min) {fat_match.group(1)}")
            if moisture_match:
                components.append(f"Moisture (max) {moisture_match.group(1)}")
            
            clean_analysis = ", ".join(components)
            # Convert British spelling "fibre" to American spelling "fiber"
            clean_analysis = re.sub(r'\bfibre\b', 'fiber', clean_analysis, flags=re.IGNORECASE)
            return clean_analysis
        
        return None
        
    except Exception:
        return None

def convert_ingredients_to_array(ingredients_string):
    """Helper function to convert ingredient string to array format"""
    if not ingredients_string or not isinstance(ingredients_string, str):
        return ingredients_string
    
    # If it's an error message or special case, return as is
    if any(phrase in ingredients_string.lower() for phrase in ['unable to extract', 'error', 'not available', 'please check']):
        return ingredients_string
    
    # Split by commas and clean each ingredient
    ingredients_array = [ingredient.strip() for ingredient in ingredients_string.split(',')]
    # Remove empty items
    ingredients_array = [ingredient for ingredient in ingredients_array if ingredient]
    
    return ingredients_array

def extract_ingredients(soup, url):
    """Extract ingredients from the page with multiple strategies, prioritized"""
    import re
    
    # APPLAWS DROPDOWN DETECTION: Use Selenium to click ingredient dropdowns
    # Applaws hides ingredients in clickable sections that need to be revealed
    if 'applaws.com' in url.lower():
        try:
            from selenium_scraper import _get_browser
            import time
            from selenium.webdriver.common.by import By
            
            driver = _get_browser()
            driver.get(url)
            time.sleep(5)  # Allow page to load completely
            
            # Look for clickable "Ingredients" sections on Applaws
            ingredient_buttons = driver.find_elements(By.XPATH, "//*[contains(text(), 'Ingredients') or contains(text(), 'INGREDIENTS')]")
            
            for i, button in enumerate(ingredient_buttons):
                try:
                    element_text = button.text.strip()
                    
                    # Look for exact "Ingredients" dropdown (not marketing text like "100% Natural Ingredients")
                    if element_text == 'Ingredients':
                        # Click to reveal hidden ingredient content
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                        time.sleep(1)
                        driver.execute_script("arguments[0].click();", button)
                        time.sleep(5)  # Wait longer for content to load
                        
                        # Get the new page content and extract ingredients
                        new_source = driver.page_source
                        soup_selenium = BeautifulSoup(new_source, 'html.parser')
                        page_text = soup_selenium.get_text()
                        
                        # Extract ingredients from the revealed content
                        result = extract_ingredients_from_text(page_text)
                        if result and len(result) > 10:
                            return convert_ingredients_to_array(result)
                        
                        # More aggressive search in the revealed content
                        # Look for ingredient patterns directly in the page text
                        import re
                        
                        # Try multiple patterns to find ingredients after clicking (based on debug findings)
                        patterns = [
                            # Pattern that works well based on debug (captures until period)
                            r'(chicken\s+broth[^.]+\.)',
                            r'((?:chicken|fish|tuna|beef|turkey|lamb)\s+broth[^.]+\.)',
                            # More general patterns
                            r'ingredients[:\s]*([^.]+\.)',
                            r'ingredients[:\s]*\n\s*(.+?)(?:\n\n|\n[A-Z]|$)',
                            # Fallback pattern for other formats
                            r'([a-z][a-z\s,()]+(?:chicken|fish|tuna|beef|turkey|lamb)[a-z\s,()]*(?:,\s*[a-z][a-z\s()]*){2,}\.?)'
                        ]
                        
                        for pattern in patterns:
                            matches = re.findall(pattern, page_text, re.IGNORECASE)
                            for match in matches:
                                # Clean up the match
                                match = match.strip()
                                # Remove extra whitespace and newlines
                                match = re.sub(r'\s+', ' ', match)
                                # Remove any leading/trailing punctuation except period
                                match = re.sub(r'^[^\w]+', '', match)
                                match = re.sub(r'[^\w\.]+$', '', match)
                                # Remove trailing period if present
                                if match.endswith('.'):
                                    match = match[:-1]
                                
                                # Validate it looks like ingredients (has food words and commas)
                                if (len(match) > 20 and 
                                    match.count(',') >= 2 and
                                    any(word in match.lower() for word in ['chicken', 'fish', 'tuna', 'beef', 'turkey', 'lamb', 'broth', 'water', 'oil'])):
                                    return convert_ingredients_to_array(match)
                        
                        # Also try a direct search around the word "ingredients" as backup
                        if 'ingredients' in page_text.lower():
                            ingredients_pos = page_text.lower().find('ingredients')
                            context = page_text[ingredients_pos:ingredients_pos+500]
                            
                            # Look for simple patterns like "Tuna Fillet, Fish Broth, Rice"
                            import re
                            simple_pattern = r'ingredients[^\n]*?\n\s*([a-z][^.]*?(?:,\s*[a-z][^.,]*?){1,10})[.\n]'
                            match = re.search(simple_pattern, context, re.IGNORECASE)
                            if match:
                                simple_result = match.group(1).strip()
                                return convert_ingredients_to_array(simple_result)
                        
                        break  # Found and clicked the ingredients button
                        
                except Exception as e:
                    continue
            
        except Exception as e:
            # Fall through to regular extraction if Selenium fails
            pass
    
    page_text = soup.get_text()
    fallback_json_ingredients = None  # Store suspicious JSON ingredients as fallback
    

    
    # TARGET.COM UNIVERSAL FIX: Use Selenium to extract from "Label info" dropdown 
    # This completely bypasses all other extraction methods for Target.com
    if 'target.com' in url.lower():
        try:
            from selenium_scraper import get_target_ingredients_with_selenium
            selenium_ingredients = get_target_ingredients_with_selenium(url)
            if selenium_ingredients and len(selenium_ingredients) > 50:
                # Clean and return the Selenium results
                formatted_content = format_ingredient_list(selenium_ingredients)
                formatted_content = clean_extra_content(formatted_content)
                if len(formatted_content) > 50:
                    return convert_ingredients_to_array(formatted_content)

            # If Selenium didn't find anything valid, check if this is a supplement without detailed ingredients
            # For supplements/vitamins, Target often only shows marketing descriptions, not ingredient lists
            if any(word in url.lower() for word in ['vitamin', 'supplement', 'multivitamin', 'probiotic']):
                return "Ingredient information not available - this appears to be a supplement product where Target.com only provides marketing descriptions rather than detailed ingredient lists."
            else:
                return "Unable to extract ingredients from Label info dropdown. Please check that the product has ingredient information available."
        except Exception as e:
            print(f"Warning: Selenium extraction failed: {e}")
            return f"Error accessing Label info dropdown: {str(e)}"

    
    # ABSOLUTE HOLISTIC SPECIFIC: Use Selenium to extract from ingredients dropdown
    # Use browser automation to properly handle dropdown interactions
    if 'absolute-holistic.com' in url.lower():
        try:
            from selenium_scraper import _get_browser
            import time
            
            driver = _get_browser()
            driver.get(url)
            time.sleep(3)  # Allow page to load
            
            # Look for the ingredients text in the page
            page_source = driver.page_source
            soup_selenium = BeautifulSoup(page_source, 'html.parser')
            page_text_selenium = soup_selenium.get_text()
            
            # Use our proven extraction logic with Selenium-loaded content
            # Look for any Absolute Holistic ingredient pattern
            ingredient_patterns = ['IngredientsChicken', 'IngredientsLamb', 'IngredientsSalmon', 'IngredientsBeef']
            
            for pattern in ingredient_patterns:
                ingredients_start = page_text_selenium.find(pattern)
                if ingredients_start != -1:
                    remaining_text = page_text_selenium[ingredients_start + 11:]  # Skip "Ingredients"
                    
                    # Look for multiple possible end patterns for Absolute Holistic
                    end_patterns = [
                        ('Folic Acid)', 11),  # Some products end with this
                        ('Vitamin D3', 10),   # Some products end with this
                        ('Vitamin K', 9),     # Some might end with this
                        ('Biotin', 6),        # Fallback
                    ]
                    
                    potential_ingredients = None
                    for end_pattern, offset in end_patterns:
                        end_pos = remaining_text.find(end_pattern)
                        if end_pos != -1:
                            potential_ingredients = remaining_text[:end_pos + offset].strip()
                            break
                    
                    # If no specific ending found, use generic terminators
                    if not potential_ingredients:
                        end_patterns_generic = [
                            'OUR NEW ZEALAND SOURCED',
                            '____________________________',
                            'Guaranteed Analysis',
                            'Storage Recommendations',
                            'Feeding Instructions'
                        ]
                        
                        end_pos = len(remaining_text)
                        for pattern_generic in end_patterns_generic:
                            pos = remaining_text.find(pattern_generic)
                            if pos != -1 and pos < end_pos:
                                end_pos = pos
                        
                        potential_ingredients = remaining_text[:end_pos].strip()
                    
                    if potential_ingredients:
                        # Clean up any HTML entities and extra whitespace
                        potential_ingredients = potential_ingredients.replace('&amp;', '&')
                        potential_ingredients = re.sub(r'\s+', ' ', potential_ingredients)
                        
                        # Validate this looks like ingredients
                        first_word = potential_ingredients.split(',')[0].strip().lower()
                        valid_starters = ['chicken', 'lamb', 'salmon', 'beef', 'duck', 'turkey']
                        
                        if len(potential_ingredients) > 50 and any(starter in first_word for starter in valid_starters):
                            formatted_content = format_ingredient_list(potential_ingredients)
                            if len(formatted_content) > 50:
                                return formatted_content
                    break
                            
        except Exception as e:
            print(f"Warning: Absolute Holistic Selenium setup failed: {e}")
            # If Selenium fails, fall back to direct BeautifulSoup extraction
            print("Falling back to direct page extraction for Absolute Holistic...")
            
            try:
                # Direct extraction as fallback when Selenium fails
                ingredient_patterns = ['IngredientsChicken', 'IngredientsLamb', 'IngredientsSalmon', 'IngredientsBeef']
                
                for pattern in ingredient_patterns:
                    ingredients_start = page_text.find(pattern)
                    if ingredients_start != -1:
                        remaining_text = page_text[ingredients_start + 11:]  # Skip "Ingredients"
                        
                        # Look for multiple possible end patterns
                        end_patterns = [
                            ('Folic Acid)', 11),
                            ('Vitamin D3', 10),
                            ('Vitamin K', 9),
                            ('Biotin', 6),
                        ]
                        
                        potential_ingredients = None
                        for end_pattern, offset in end_patterns:
                            end_pos = remaining_text.find(end_pattern)
                            if end_pos != -1:
                                potential_ingredients = remaining_text[:end_pos + offset].strip()
                                break
                        
                        # Generic fallback if no specific ending found
                        if not potential_ingredients:
                            end_patterns_generic = [
                                'OUR NEW ZEALAND SOURCED',
                                '____________________________',
                                'Guaranteed Analysis'
                            ]
                            
                            end_pos = len(remaining_text)
                            for pattern_generic in end_patterns_generic:
                                pos = remaining_text.find(pattern_generic)
                                if pos != -1 and pos < end_pos:
                                    end_pos = pos
                            
                            potential_ingredients = remaining_text[:end_pos].strip()
                        
                        if potential_ingredients:
                            # Clean up and validate
                            potential_ingredients = potential_ingredients.replace('&amp;', '&')
                            potential_ingredients = re.sub(r'\s+', ' ', potential_ingredients)
                            
                            first_word = potential_ingredients.split(',')[0].strip().lower()
                            valid_starters = ['chicken', 'lamb', 'salmon', 'beef', 'duck', 'turkey']
                            
                            if len(potential_ingredients) > 50 and any(starter in first_word for starter in valid_starters):
                                formatted_content = format_ingredient_list(potential_ingredients)
                                if len(formatted_content) > 50:
                                    print(f"Fallback extraction successful: {len(formatted_content)} characters")
                                    return formatted_content
                        break
                        
            except Exception as fallback_e:
                print(f"Warning: Fallback extraction also failed: {fallback_e}")
            
            # Only return error message if both Selenium AND fallback fail
            return "Unable to extract ingredients from Absolute Holistic dropdown. Please ensure the page has ingredient information available."
    
    # PRIORITY 0: Highest-priority search using regex with scoring - FIXED: More precise boundary detection
    ingredient_start_patterns = [
        # Most precise: Stop at specific section markers
        r'ingredients?[:\s]+(.*?)(?=\n\s*(?:guaranteed\s+analysis|feeding|directions|nutritional\s+info|calories|shipping|returns|nutrition\s+facts|allergen|warning|storage|best\s+before|expir|net\s+weight|related\s+products|you\s+may\s+also\s+like|similar\s+products|product\s+details|$))',
        # Medium precision: Stop at paragraph breaks or section headers, but limit length
        r'ingredients?[:\s]+(.{20,800}?)(?=\n\n|\n\s*[A-Z][A-Z\s]+:|\n\s*\d+\s*%|$)',
        # Fallback with strict length limit to prevent cross-contamination
        r'ingredient\s+list[:\s]+(.{20,600}?)(?=\n\n|\n[A-Z]|$)',
        r'contains[:\s]+(.{20,500}?)(?=\n\n|\n[A-Z]|$)'
    ]
    
    # Enhanced scoring system for ingredient validation
    primary_starters = [
        'ground yellow corn', 'chicken', 'water sufficient for processing', 
        'tuna fillet', 'meat and bone meal', 'salmon', 'beef', 'turkey',
        'duck', 'lamb', 'venison', 'rabbit', 'fish meal', 'chicken meal',
        'beef meal', 'salmon meal', 'sweet potato', 'peas', 'rice'
    ]
    
    technical_terms = [
        'sodium selenite', 'thiamine mononitrate', 'riboflavin', 
        'menadione nicotinamide bisulfite', 'marine microalgae oil',
        'amino acid chelate', 'pantothenic acid', 'pyridoxine hydrochloride',
        'folic acid', 'biotin', 'cyanocobalamin', 'choline chloride',
        'zinc oxide', 'ferrous sulfate', 'copper sulfate', 'manganese sulfate',
        'calcium iodate', 'ethylenediamine dihydriodide', 'rosemary extract',
        'mixed tocopherols', 'vitamin e supplement', 'vitamin a supplement',
        'vitamin d3 supplement', 'vitamin b12 supplement', 'niacin supplement'
    ]
    
    common_ingredients = [
        'broth', 'gum', 'egg whites', 'taurine', 'calcium chloride',
        'potassium chloride', 'salt', 'natural flavor', 'artificial flavor',
        'carrageenan', 'locust bean gum', 'guar gum', 'xanthan gum'
    ]
    
    marketing_terms = [
        'gourmet', 'delicious', 'packed with animal protein', 'strong lean muscles',
        'freeze-dried raw', 'minimally processed bites', 'burn fat', 'healthy metabolism',
        'feel fuller', 'made without', 'made in the usa', 'finest ingredients',
        'from around the world', 'available in', 'lb bags', 'more about',
        'high protein kibble', 'same bag', 'raw pieces', 'raw nutrition',
        'boosted nutrition', 'support healthy', 'immune health', 'perfect for any pet',
        'tailored nutrition', 'life stages', 'optimal nutrition', 'premium quality',
        'wholesome ingredients', 'natural nutrition', 'complete and balanced'
    ]
    
    promotional_terms = [
        'buy now', 'shop', 'add to cart', 'free shipping', 'save money',
        'discount', 'coupon', 'special offer', 'limited time'
    ]
    
    best_match = None
    best_score = 0
    
    for pattern in ingredient_start_patterns:
        matches = re.finditer(pattern, page_text, re.IGNORECASE | re.DOTALL)
        for match in matches:
            potential_text = match.group(1).strip()
            
            # Calculate score
            score = 0
            potential_lower = potential_text.lower()
            
            # Positive scoring
            for starter in primary_starters:
                if starter in potential_lower[:100]:  # Check first 100 chars
                    score += 50
            
            for term in technical_terms:
                if term in potential_lower:
                    score += 30
            
            for ingredient in common_ingredients:
                if ingredient in potential_lower:
                    score += 10
            
            # Negative scoring
            for term in marketing_terms:
                if term in potential_lower:
                    score -= 25
            
            for term in promotional_terms:
                if term in potential_lower:
                    score -= 50
            
            # Length and comma bonus - FIXED: Better scoring for complete ingredient lists
            if len(potential_text) > 100:
                score += 10
            if len(potential_text) > 300:  # Bonus for longer lists
                score += 20
            if len(potential_text) > 500:  # Even bigger bonus for very complete lists
                score += 30
            if potential_text.count(',') > 5:
                score += 20
            if potential_text.count(',') > 10:  # Bonus for lists with many ingredients
                score += 40
            if potential_text.count(',') > 20:  # Bonus for supplement lists with many vitamins/minerals
                score += 60
            
            # Additional validation to prevent cross-contamination from other products
            potential_lower = potential_text.lower()
            
            # Reject if it contains multiple product indicators (suggests cross-contamination)
            product_indicators = ['product details', 'related products', 'you may also like', 'similar products', 
                                'other flavors', 'other varieties', 'also available', 'view all', 'shop all']
            contamination_count = sum(1 for indicator in product_indicators if indicator in potential_lower)
            
            # Reject if it contains multiple "ingredients:" sections (suggests multiple products)
            ingredients_count = potential_lower.count('ingredients:')
            
            # Check if this is the best match so far - FIXED: Prioritize longer, more complete matches but avoid contamination
            if (score > best_score and len(potential_text) > 10 and 
                contamination_count == 0 and ingredients_count <= 1):
                best_match = potential_text
                best_score = score
    
    if best_match and is_likely_ingredient_list(best_match):
        formatted_content = format_ingredient_list(best_match)
        formatted_content = clean_extra_content(formatted_content)
        if len(formatted_content) > 50:
            return formatted_content

    # PRIORITY 0.3: Enhanced "Label Info" dropdown search for Target.com
    # Look for "Label Info" sections that contain "Ingredients:" prefix
    label_info_patterns = [
        # Target-specific pattern: Label info section with "Ingredients:" prefix
        r'label\s+info[^:]*?ingredients:\s*([^.]*?(?:vitamin\s+d-?3\s+supplement|folic\s+acid|[a-z]\d{6,}\.?))',
        # More general patterns
        r'label\s+info[:\s]*([^<]*?)(?=\s*(?:guaranteed\s+analysis|feeding|directions|nutritional|calories|shipping|returns|$))',
        r'label\s+information[:\s]*([^<]*?)(?=\s*(?:guaranteed\s+analysis|feeding|directions|nutritional|calories|shipping|returns|$))',
        r'product\s+label[:\s]*([^<]*?)(?=\s*(?:guaranteed\s+analysis|feeding|directions|nutritional|calories|shipping|returns|$))'
    ]
    
    for i, pattern in enumerate(label_info_patterns):
        matches = re.finditer(pattern, page_text, re.IGNORECASE | re.DOTALL)
        for match in matches:
            potential_content = match.group(1).strip()
            
            if len(potential_content) > 50:
                # For Target-specific pattern (pattern 0), use content directly
                if i == 0:
                    if (potential_content.count(',') >= 8 and 
                        is_likely_ingredient_list(potential_content)):
                        formatted_content = format_ingredient_list(potential_content)
                        formatted_content = clean_extra_content(formatted_content)
                        if len(formatted_content) > 50:
                            return formatted_content
                else:
                    # For other patterns, look for ingredients within the content
                    # Search for "Ingredients:" followed by ingredient list
                    ingredient_match = re.search(
                        r'ingredients:\s*([^.]*?(?:vitamin\s+d-?3\s+supplement|folic\s+acid|[a-z]\d{6,}\.?))',
                        potential_content, 
                        re.IGNORECASE | re.DOTALL
                    )
                    if ingredient_match:
                        ingredient_text = ingredient_match.group(1).strip()
                        if (len(ingredient_text) > 100 and 
                            ingredient_text.count(',') >= 8 and
                            is_likely_ingredient_list(ingredient_text)):
                            formatted_content = format_ingredient_list(ingredient_text)
                            formatted_content = clean_extra_content(formatted_content)
                            if len(formatted_content) > 50:
                                return formatted_content
                    
                    # Fallback: try to find ingredients starting with common proteins
                    ingredient_match = re.search(
                        r'((?:water|chicken|beef|salmon|tuna|turkey|duck|lamb)[^.]*?(?:rosemary\s+extract|vitamin\s+e|mixed\s+tocopherols|vitamin\s+d-?3\s+supplement))',
                        potential_content, 
                        re.IGNORECASE | re.DOTALL
                    )
                    if ingredient_match:
                        ingredient_text = ingredient_match.group(1).strip()
                        if (len(ingredient_text) > 100 and 
                            is_likely_ingredient_list(ingredient_text)):
                            formatted_content = format_ingredient_list(ingredient_text)
                            formatted_content = clean_extra_content(formatted_content)
                            if len(formatted_content) > 50:
                                return formatted_content

    # PRIORITY 0.35: NEW - More aggressive search for any "Chicken" to "Rosemary Extract" content
    # This is specifically for the Instinct Target.com case mentioned by user
    if 'chicken' in page_text.lower() and 'rosemary extract' in page_text.lower():
        chicken_to_rosemary_pattern = r'(chicken[^.]*?rosemary\s+extract)'
        matches = re.finditer(chicken_to_rosemary_pattern, page_text, re.IGNORECASE | re.DOTALL)
        for match in matches:
            potential_ingredients = match.group(1).strip()
            if (len(potential_ingredients) > 100 and 
                potential_ingredients.count(',') >= 5 and
                is_likely_ingredient_list(potential_ingredients)):
                formatted_content = format_ingredient_list(potential_ingredients)
                formatted_content = clean_extra_content(formatted_content)
                if len(formatted_content) > 50:
                    return formatted_content

    # PRIORITY 0.36: NEW - Search for any long comma-separated list that starts with "Chicken" 
    # and contains common ingredient endings, regardless of surrounding text
    chicken_list_pattern = r'chicken[,\s][^.]*?(?:rosemary\s+extract|vitamin\s+e\s+supplement|mixed\s+tocopherols|sodium\s+selenite|ethylenediamine\s+dihydriodide)'
    matches = re.finditer(chicken_list_pattern, page_text, re.IGNORECASE | re.DOTALL)
    for match in matches:
        potential_ingredients = match.group(0).strip()
        if (len(potential_ingredients) > 150 and 
            potential_ingredients.count(',') >= 8 and
            # Make sure it's not just navigation or repeated text
            not any(skip_term in potential_ingredients.lower() for skip_term in [
                'navigate to', 'click here', 'view all', 'shop now', 'add to cart',
                'product details', 'nutritional info', 'feeding guide'
            ]) and
            is_likely_ingredient_list(potential_ingredients)):
            formatted_content = format_ingredient_list(potential_ingredients)
            formatted_content = clean_extra_content(formatted_content)
            if len(formatted_content) > 100:
                return formatted_content

    # PRIORITY 0.4: NEW - Enhanced search for hidden/dropdown content specifically for Instinct-style pages
    # Look for elements that might contain hidden ingredient information
    dropdown_selectors = [
        'div[data-label-info]', 'div[data-ingredients]', 
        '.label-info', '.ingredients-dropdown', '.product-label',
        '[data-toggle*="ingredient"]', '[data-toggle*="label"]',
        'details summary:contains("Label")', 'details summary:contains("Ingredient")',
        '.accordion-content', '.collapse-content', '.toggle-content',
        '[data-accordion]', '[data-collapse]', '[data-toggle]'
    ]
    
    for selector in dropdown_selectors:
        try:
            elements = soup.select(selector)
            for element in elements:
                content = element.get_text()
                if (len(content) > 100 and 
                    any(starter in content.lower() for starter in ['chicken', 'beef', 'salmon']) and
                    any(ender in content.lower() for ender in ['rosemary extract', 'vitamin e', 'mixed tocopherols']) and
                    is_likely_ingredient_list(content)):
                    formatted_content = format_ingredient_list(content)
                    formatted_content = clean_extra_content(formatted_content)
                    if len(formatted_content) > 50:
                        return formatted_content
        except:
            continue

    # PRIORITY 0.45: NEW - Search for any div/span/p that contains both "chicken" and "rosemary extract"
    # This covers cases where ingredients might be in various container elements
    potential_containers = soup.find_all(['div', 'span', 'p', 'section', 'article', 'aside'])
    for container in potential_containers:
        container_text = container.get_text()
        if (len(container_text) > 200 and 
            'chicken' in container_text.lower() and 
            'rosemary extract' in container_text.lower() and
            container_text.count(',') >= 10):
            
            # Try to extract just the ingredient portion
            chicken_match = re.search(
                r'(chicken[^.]*?rosemary\s+extract)', 
                container_text, 
                re.IGNORECASE | re.DOTALL
            )
            if chicken_match:
                potential_ingredients = chicken_match.group(1).strip()
                if (len(potential_ingredients) > 150 and 
                    potential_ingredients.count(',') >= 8 and
                    is_likely_ingredient_list(potential_ingredients)):
                    formatted_content = format_ingredient_list(potential_ingredients)
                    formatted_content = clean_extra_content(formatted_content)
                    if len(formatted_content) > 100:
                        return formatted_content

    # PRIORITY 0.47: NEW - Target.com specific "Label info" section extraction
    # Target.com has a specific structure with "Label info" heading followed by content
    if 'target.com' in url.lower():
        # Look for the "Label info" heading and its following content
        label_info_headings = soup.find_all(['h3', 'h2', 'h4'], string=re.compile(r'label\s*info', re.I))
        for heading in label_info_headings:
            # Look for the next sibling div that contains the actual content
            next_sibling = heading.find_next_sibling()
            if next_sibling:
                sibling_text = next_sibling.get_text()
                if (len(sibling_text) > 100 and 
                    any(starter in sibling_text.lower() for starter in ['chicken', 'ground', 'corn', 'meal']) and
                    sibling_text.count(',') >= 5):
                    # Extract potential ingredient content
                    if is_likely_ingredient_list(sibling_text):
                        formatted_content = format_ingredient_list(sibling_text)
                        formatted_content = clean_extra_content(formatted_content)
                        if len(formatted_content) > 50:
                            return formatted_content
        
        # Also check for Target's product detail tab container structure
        tab_containers = soup.find_all(attrs={'data-test': re.compile(r'product.*detail.*tab', re.I)})
        for container in tab_containers:
            container_text = container.get_text()
            # Look for content after "Label info" within the container
            if 'label info' in container_text.lower():
                # Try to extract the section after "Label info"
                label_info_match = re.search(
                    r'label\s+info(.*?)(?:shipping\s*&\s*returns|q&a|specifications|details|$)',
                    container_text,
                    re.IGNORECASE | re.DOTALL
                )
                if label_info_match:
                    potential_content = label_info_match.group(1).strip()
                    if (len(potential_content) > 100 and 
                        potential_content.count(',') >= 5 and
                        any(starter in potential_content.lower() for starter in ['chicken', 'ground', 'corn', 'meal']) and
                        is_likely_ingredient_list(potential_content)):
                        formatted_content = format_ingredient_list(potential_content)
                        formatted_content = clean_extra_content(formatted_content)
                        if len(formatted_content) > 50:
                            return formatted_content

        # PRIORITY 0.48: NEW - Target.com JavaScript/JSON ingredient extraction
        # Target.com embeds ingredient data in JavaScript objects with various structures
        script_tags = soup.find_all('script')
        for script in script_tags:
            if script.string and len(script.string) > 1000:
                # Multiple patterns to handle different Target.com product page structures
                ingredient_patterns = [
                    # SPECIFIC pattern for nutrition_facts Blue Buffalo: "nutrition_facts":{"ingredients":"Deboned Chicken..."
                    r'"nutrition_facts":\s*\{\s*"ingredients":\s*"([^"]{100,})"',
                    # Pattern for escaped JSON (alternative): \\"nutrition_facts\\":{\\"ingredients\\":\\"...
                    r'\\\\"nutrition_facts\\\\":\s*\{\s*\\\\"ingredients\\\\":\s*\\\\"([^\\]{100,})\\\\"',
                    # Primary pattern: nutrition_facts structure
                    r'nutrition_facts[^}]*\\?["\']ingredients\\?["\']\s*:\s*\\?["\']([^"\'\\]{100,})["\']',
                    # Enhanced pattern for Blue Buffalo with better JSON parsing
                    r'\\?["\']nutrition_facts\\?["\']\s*:\s*\{[^}]*\\?["\']ingredients\\?["\']\s*:\s*\\?["\']([^"\'\\]{100,})["\']',
                    # Fallback patterns for different JSON structures
                    r'product_info[^}]*\\?["\']ingredients\\?["\']\s*:\s*\\?["\']([^"\'\\]*)["\']',
                    r'nutrition[^}]*\\?["\']ingredients\\?["\']\s*:\s*\\?["\']([^"\'\\]*)["\']',
                    r'label_info[^}]*\\?["\']ingredients\\?["\']\s*:\s*\\?["\']([^"\'\\]*)["\']',
                    # More flexible patterns that just look for ingredients key with substantial content
                    r'\\?["\']ingredients\\?["\']\s*:\s*\\?["\']([^"\'\\]*(?:chicken|beef|salmon|ground|corn|meal)[^"\'\\]*)["\']',
                    # Very broad pattern for any ingredients field with long content
                    r'\\?["\']ingredients\\?["\']\s*:\s*\\?["\']([^"\'\\]{100,})["\']'
                ]
                
                for pattern in ingredient_patterns:
                    matches = re.finditer(pattern, script.string, re.IGNORECASE | re.DOTALL)
                    for match in matches:
                        potential_ingredients = match.group(1)
                        if (len(potential_ingredients) > 50 and 
                            potential_ingredients.count(',') >= 5 and
                            any(starter in potential_ingredients.lower() for starter in ['chicken', 'ground', 'corn', 'meal', 'beef', 'salmon', 'turkey', 'fish']) and
                            is_likely_ingredient_list(potential_ingredients)):
                            # Clean up any escaped characters
                            cleaned_ingredients = potential_ingredients.replace('\\u003c', '<').replace('\\u003e', '>')
                            cleaned_ingredients = re.sub(r'\\u[0-9a-fA-F]{4}', '', cleaned_ingredients)  # Remove unicode escapes
                            
                            formatted_content = format_ingredient_list(cleaned_ingredients)
                            formatted_content = clean_extra_content(formatted_content)
                            
                            # VALIDATION: Check if JSON ingredients seem suspicious/generic
                            # If product mentions specific protein but JSON has generic terms, be suspicious
                            if len(formatted_content) > 50:
                                page_title = soup.find('title')
                                title_text = page_title.get_text().lower() if page_title else ''
                                url_lower = url.lower()
                                
                                # Check for mismatches between title/URL and ingredients
                                suspicious = False
                                if ('chicken' in title_text or 'chicken' in url_lower):
                                    if ('beef' in formatted_content.lower() and 'chicken' not in formatted_content.lower()):
                                        suspicious = True
                                if ('turkey' in title_text or 'turkey' in url_lower):
                                    if ('poultry' in formatted_content.lower() and 'turkey' not in formatted_content.lower()):
                                        suspicious = True
                                
                                # If ingredients seem suspicious, continue searching for better ones
                                if not suspicious:
                                    return formatted_content
                                else:
                                    # Store as fallback but keep searching
                                    if fallback_json_ingredients is None:  # Only store first fallback
                                        fallback_json_ingredients = formatted_content
                
                # For Blue Buffalo specifically, if we found JSON ingredients, return them immediately
                if fallback_json_ingredients is not None and 'blue-buffalo' in url.lower():
                    return fallback_json_ingredients
                
                # Stop searching script tags if we found valid JSON ingredients 
                # (even if suspicious - we'll return them as fallback later)
                if fallback_json_ingredients is not None:
                    break
                
                # FALLBACK: If no structured patterns work, search for any ingredient-like content in scripts
                # This is for cases where the JSON structure might be different or malformed
                for script in script_tags:
                    if script.string and len(script.string) > 1000 and 'ingredient' in script.string.lower():
                        # Look for any substantial text that contains common ingredient indicators
                        # and is surrounded by quotes (likely to be ingredient data)
                        fallback_patterns = [
                            r'["\']([^"\']{200,}(?:chicken|beef|salmon)[^"\']{200,}(?:rosemary extract|vitamin|mineral|oxide|extract)[^"\']*)["\']',
                            r'["\']([^"\']*(?:ground whole grain corn|chicken by-product meal)[^"\']{300,})["\']',
                            r'["\']([^"\']*(?:chicken, chicken by-product meal)[^"\']{200,})["\']'
                        ]
                        
                        for pattern in fallback_patterns:
                            matches = re.finditer(pattern, script.string, re.IGNORECASE | re.DOTALL)
                            for match in matches:
                                potential_ingredients = match.group(1)
                                if (len(potential_ingredients) > 100 and 
                                    potential_ingredients.count(',') >= 10 and
                                    # Check for multiple food-related terms
                                    sum(1 for term in ['chicken', 'ground', 'corn', 'meal', 'beef', 'salmon', 'protein', 'fat', 'vitamin'] 
                                        if term in potential_ingredients.lower()) >= 3 and
                                    is_likely_ingredient_list(potential_ingredients)):
                                    
                                    # Clean up any escaped characters
                                    cleaned_ingredients = potential_ingredients.replace('\\u003c', '<').replace('\\u003e', '>')
                                    cleaned_ingredients = re.sub(r'\\u[0-9a-fA-F]{4}', '', cleaned_ingredients)
                                    
                                    formatted_content = format_ingredient_list(cleaned_ingredients)
                                    formatted_content = clean_extra_content(formatted_content)
                                    if len(formatted_content) > 100:  # Higher threshold for fallback
                                        return formatted_content

    # PRIORITY 0.49: Enhanced search when JSON ingredients are suspicious 
    # Look more aggressively for correct ingredients that match the product title
    if fallback_json_ingredients is not None:
        page_title = soup.find('title')
        title_text = page_title.get_text().lower() if page_title else ''
        url_lower = url.lower()
        
        # Extract expected proteins from title/URL
        expected_proteins = []
        if 'chicken' in title_text or 'chicken' in url_lower:
            expected_proteins.append('chicken')
        if 'turkey' in title_text or 'turkey' in url_lower:
            expected_proteins.append('turkey')
        if 'salmon' in title_text or 'salmon' in url_lower:
            expected_proteins.append('salmon')
        if 'beef' in title_text or 'beef' in url_lower:
            expected_proteins.append('beef')
            
        if expected_proteins:
            # Look for ANY text that contains the expected proteins and looks like ingredients
            for protein in expected_proteins:
                # Search for ingredients starting with water and the expected protein
                protein_pattern = rf'(water[,\s]+{protein}[^.]*?(?:vitamin\s+[a-z]-?\d*\s+supplement|folic\s+acid|[a-z]\d{{6,}}\.?))'
                matches = re.finditer(protein_pattern, page_text, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    potential_ingredients = match.group(1).strip()
                    if (len(potential_ingredients) > 100 and 
                        potential_ingredients.count(',') >= 8 and
                        is_likely_ingredient_list(potential_ingredients)):
                        formatted_content = format_ingredient_list(potential_ingredients)
                        formatted_content = clean_extra_content(formatted_content)
                        if len(formatted_content) > 50:
                            # Verify this is better than our fallback
                            if protein.lower() in formatted_content.lower():
                                return formatted_content

    # PRIORITY 0.5: Special handling for "Our Ingredients" pattern (like Instinct)
    our_ingredients_pattern = r'our\s+ingredients[:\s]*([A-Z][^.]*?(?:rosemary\s+extract|vitamin\s+[a-z]\d*\s+supplement|sodium\s+selenite|ethylenediamine\s+dihydriodide)\.?)'
    matches = re.finditer(our_ingredients_pattern, page_text, re.IGNORECASE | re.DOTALL)
    for match in matches:
        potential_ingredients = match.group(1).strip()
        if (len(potential_ingredients) > 50 and len(potential_ingredients) < 3000 and
            is_likely_ingredient_list(potential_ingredients)):
            formatted_content = format_ingredient_list(potential_ingredients)
            formatted_content = clean_extra_content(formatted_content)
            if len(formatted_content) > 50:
                return formatted_content

    # FINAL FALLBACK: Try Selenium for Target.com if no other method worked or we have suspicious ingredients
    if ('target.com' in url.lower()):
        # Don't use Selenium for Blue Buffalo if we already have JSON ingredients
        if 'blue-buffalo' in url.lower() and fallback_json_ingredients is not None:
            should_use_selenium = False
        else:
            # Use Selenium if: we have suspicious JSON OR no ingredients found at all
            # (If we reach this point and it's Target.com, that means no other method succeeded)
            should_use_selenium = True  # Always try Selenium for Target.com as final fallback
        
        if should_use_selenium:
            try:
                from selenium_scraper import get_target_ingredients_with_selenium
                selenium_ingredients = get_target_ingredients_with_selenium(url)
                if (selenium_ingredients and 
                    len(selenium_ingredients) > 50 and
                    selenium_ingredients.count(',') >= 8):
                    # Selenium found ingredients
                    formatted_content = format_ingredient_list(selenium_ingredients)
                    formatted_content = clean_extra_content(formatted_content)
                    if len(formatted_content) > 50:
                        return convert_ingredients_to_array(formatted_content)
            except Exception as e:
                print(f"Selenium fallback failed: {e}")

    # Return suspicious JSON ingredients if Selenium also failed
    if fallback_json_ingredients is not None:
        return convert_ingredients_to_array(fallback_json_ingredients)
    
    # If all strategies fail, return None
    return None

def extract_ingredients_after_element(element):
    """Extract ingredients from content following a heading element"""
    try:
        # Look for the next sibling elements
        current = element.next_sibling
        content_parts = []
        
        while current and len(content_parts) < 5:  # Limit search
            if hasattr(current, 'get_text'):
                text = current.get_text().strip()
                if text and len(text) > 10:
                    content_parts.append(text)
                    # If this looks like ingredients, return it
                    if is_likely_ingredient_list(text):
                        return convert_ingredients_to_array(clean_ingredients_text(text))
            current = current.next_sibling
        
        # If we found content, combine it
        if content_parts:
            combined = ' '.join(content_parts)
            if is_likely_ingredient_list(combined):
                return convert_ingredients_to_array(clean_ingredients_text(combined))
                
        return None
    except:
        return None

def extract_ingredients_from_element(element):
    """Extract ingredients from a specific element"""
    try:
        text = element.get_text().strip()
        if len(text) > 10 and is_likely_ingredient_list(text):
            cleaned = clean_ingredients_text(text)
            if cleaned:  # Only return if clean_ingredients_text didn't return None
                return cleaned
        return None
    except:
        return None

def extract_ingredients_from_json_ld(data):
    """Extract ingredients from JSON-LD structured data"""
    try:
        if isinstance(data, list):
            for item in data:
                result = extract_ingredients_from_json_ld(item)
                if result:
                    return result
        elif isinstance(data, dict):
            # Look for common ingredient fields
            ingredient_fields = ['ingredients', 'recipeIngredient', 'nutrition', 'composition']
            for field in ingredient_fields:
                if field in data:
                    ingredients = data[field]
                    if isinstance(ingredients, list):
                        return ', '.join(str(ing) for ing in ingredients)
                    elif isinstance(ingredients, str) and len(ingredients) > 10:
                        return convert_ingredients_to_array(clean_ingredients_text(ingredients))
            
            # Recursively search nested objects
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    result = extract_ingredients_from_json_ld(value)
                    if result:
                        return result
        return None
    except:
        return None

def extract_ingredients_from_text(text):
    """Extract ingredients from a large text block using patterns"""
    import re
    
    try:
        text_lower = text.lower()
        
        # Look for ingredient section patterns - FIXED: More precise boundary detection to prevent cross-contamination
        patterns = [
            # Most precise: Stop at specific section markers and product boundaries
            r'ingredients?[:\s]+(.*?)(?=\n\s*(?:guaranteed\s+analysis|feeding|directions|nutritional\s+info|calories|shipping|returns|nutrition\s+facts|allergen|warning|storage|best\s+before|expir|net\s+weight|related\s+products|you\s+may\s+also\s+like|similar\s+products|product\s+details|other\s+flavors|$))',
            r'ingredient (?:list|panel)[:\s]+(.*?)(?=\n\s*(?:guaranteed\s+analysis|feeding|directions|nutritional\s+info|calories|shipping|returns|nutrition\s+facts|allergen|warning|storage|best\s+before|expir|net\s+weight|related\s+products|you\s+may\s+also\s+like|similar\s+products|product\s+details|$))',
            r'contains[:\s]+(.*?)(?=\n\s*(?:guaranteed\s+analysis|feeding|directions|nutritional\s+info|calories|shipping|returns|nutrition\s+facts|allergen|warning|storage|best\s+before|expir|net\s+weight|related\s+products|you\s+may\s+also\s+like|similar\s+products|product\s+details|$))',
            r'made with[:\s]+(.*?)(?=\n\s*(?:guaranteed\s+analysis|feeding|directions|nutritional\s+info|calories|shipping|returns|nutrition\s+facts|allergen|warning|storage|best\s+before|expir|net\s+weight|related\s+products|you\s+may\s+also\s+like|similar\s+products|product\s+details|$))',
            # Controlled length patterns to prevent cross-contamination
            r'ingredients?[:\s]+(.{20,800}?)(?=\n\n|\n\s*[A-Z][A-Z\s]+:|\n\s*\d+\s*%|\n\s*guaranteed|$)',
            r'ingredient (?:list|panel)[:\s]+(.{20,600}?)(?=\n\s*[A-Z][A-Z\s]+:|\n\s*\d+\s*%|\n\s*guaranteed|$)'
        ]
        
        # Collect all matches with their quality scores to pick the best one
        all_matches = []
        
        for pattern_idx, pattern in enumerate(patterns):
            import re
            matches = re.findall(pattern, text_lower, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if len(match.strip()) > 20 and is_likely_ingredient_list(match):
                    # Check for cross-contamination indicators
                    match_lower = match.lower()
                    contamination_indicators = ['product details', 'related products', 'you may also like', 
                                              'similar products', 'other flavors', 'other varieties', 
                                              'also available', 'view all', 'shop all']
                    contamination_count = sum(1 for indicator in contamination_indicators if indicator in match_lower)
                    ingredients_count = match_lower.count('ingredients:')
                    
                    # Only consider matches without contamination
                    if contamination_count == 0 and ingredients_count <= 1:
                        # Score based on length, comma count, and pattern priority
                        score = len(match) + match.count(',') * 10 - pattern_idx * 5  # Prefer earlier patterns
                        all_matches.append((score, match, pattern_idx))
        
        # Return the highest-scoring match
        if all_matches:
            all_matches.sort(reverse=True)  # Sort by score descending
            best_match = all_matches[0][1]  # Get the match with highest score
            return convert_ingredients_to_array(clean_ingredients_text(best_match))
        
        return None
    except:
        return None

def is_likely_ingredient_list(text):
    """Check if text is likely to be an ingredient list rather than marketing content"""
    if not text or len(text.strip()) < 10:
        return False

    text_lower = text.lower()

    # Immediately reject navigation content
    navigation_indicators = [
        'navigate to', 'contact us', 'facebook', 'twitter', 'instagram', 'youtube',
        'sitemap', 'terms of service', 'privacy policy', 'where to buy', 'shop',
        'find a store', 'customer service', 'subscribe', 'newsletter', 'follow us'
    ]

    for nav_indicator in navigation_indicators:
        if nav_indicator in text_lower:
            return False

    # Immediately reject product descriptions and marketing copy
    description_indicators = [
        'designed to help', 'nutritional needs', 'high protein', 'specialized cat food',
        'energy levels', 'maintain a healthy weight', 'you can rest assured',
        'essential nutrients they deserve', 'promotes digestive health',
        'complete and balanced meal', 'optimal vision', 'immune support',
        'nutritious and delicious dining experience', 'beloved indoor', 'exceptional',
        'feline friend', 'nurture your', 'with real chicken being the first ingredient',
        'among the protein sources', 'this formula contains', 'additionally, it provides',
        # Add Instinct-specific marketing phrases
        'packed with animal protein', 'strong lean muscles', 'freeze-dried raw',
        'minimally processed bites', 'burn fat to support', 'healthy metabolism',
        'feel fuller longer', 'made without', 'made in the usa',
        'finest ingredients from around the world', 'available in', 'lb bags',
        'more about raw', 'high protein kibble', 'freeze-dried raw together',
        'same bag', 'all natural', 'protein packed', 'raw pieces for raw nutrition',
        'boosted nutrition recipes', 'support healthy digestion', 'healthy skin',
        'immune health', 'perfect for any pet', 'tailored nutrition',
        'variety of healthy solutions', 'life stages'
    ]

    # Check for description patterns - these are NOT ingredient lists
    description_count = sum(1 for desc in description_indicators if desc in text_lower)
    if description_count >= 2:  # If it has multiple description phrases, it's marketing copy
        return False

    # Enhanced marketing detection - reject text that starts with marketing phrases
    marketing_starters = [
        '- packed with', 'freeze-dried raw -', 'all natural,', 'protein packed,',
        'minimally processed', 'l-carnitine to help', 'made without -', 'made in the usa with',
        'available in', 'more about', 'raw + kibble', '100% raw pieces',
        'boosted nutrition', 'perfect for any pet'
    ]
    
    for starter in marketing_starters:
        if text_lower.startswith(starter):
            return False

    # Reject text that contains too much marketing language relative to actual ingredients
    marketing_indicators = [
        'tantalize', 'tastebuds', 'gourmet', 'delicious flavor', 'perfect way',
        'hand-crafted', 'toppers offer', 'invite your cat', 'experience gourmet',
        'looks good enough for you', 'crafted especially for her', 'attention to detail',
        'unique taste cats love', 'tender bites', 'savory broth', 'most refined',
        'between-meal snack', 'complement tray', 'single-serve', 'adult cat food complement',
        'made to meet your', 'ingredient criteria', 'serve fancy feast', 'favorite fancy feast',
        'add delicious flavor to her menu', 'real high quality ingredients',
        'strong lean muscles', 'burn fat', 'healthy metabolism', 'feel fuller',
        'finest ingredients', 'from around the world', 'high protein kibble',
        'raw nutrition and taste', 'boosted nutrition', 'immune health',
        'tailored nutrition', 'healthy solutions'
    ]

    marketing_count = sum(1 for marketing_term in marketing_indicators if marketing_term in text_lower)
    # If it contains multiple marketing terms, it's likely marketing copy
    if marketing_count >= 3:
        return False

    # Immediately reject disclaimer text
    disclaimer_indicators = [
        'can change in consistency', 'microwave', 'refrigerate', 'use by',
        'best by', 'sell by', 'store in', 'keep refrigerated', 'do not microwave'
    ]

    for disclaimer in disclaimer_indicators:
        if disclaimer in text_lower:
            return False

    # Immediately reject nutritional information
    nutritional_indicators = [
        'nutritional info', 'guaranteed analysis', 'crude protein', 'crude fat',
        'crude fiber', 'moisture', 'ash content', 'calorie content', 'kcal per',
        'feeding instructions', 'feed daily', 'body weight'
    ]

    for nutritional in nutritional_indicators:
        if nutritional in text_lower:
            return False

    # Immediately reject page titles/product names
    title_indicators = [
        '| applaws', '| purina', '| hill\'s', '| royal canin', '| blue buffalo', '| instinct',
        'oz can', 'oz bag', 'lb bag', 'kg bag', 'pouches', 'pack of',
        'wet cat food', 'dry cat food', 'cat treats', 'dog food', 'pet food', 
        '- amazon', '- chewy', '- petco', '- petsmart', 'product page', 'buy online'
    ]

    for title in title_indicators:
        if title in text_lower:
            return False

    # For actual ingredient lists, look for specific patterns
    # Real ingredient lists typically start with ingredients and are comma-separated
    actual_ingredient_patterns = [
        text_lower.startswith('chicken'), text_lower.startswith('beef'),
        text_lower.startswith('salmon'), text_lower.startswith('tuna'),
        text_lower.startswith('turkey'),
        text_lower.startswith('ground yellow corn'), text_lower.startswith('ground corn'),
        text_lower.startswith('water sufficient for processing'),
        text_lower.startswith('corn'), text_lower.startswith('rice'),
        text_lower.startswith('wheat'), text_lower.startswith('corn meal')
    ]

    # Check for comma separation and multiple ingredients
    has_commas = ',' in text
    has_percentages = '%' in text or 'percent' in text_lower
    word_count = len(text.split())
    
    # Look for specific ingredient terms that appear in actual lists
    ingredient_indicators = [
        'chicken', 'beef', 'salmon', 'tuna', 'turkey', 'lamb', 'duck', 'fish',
        'rice', 'wheat', 'corn', 'meal', 'by-product', 'oil', 'fat', 'vitamin',
        'mineral', 'starch', 'flour', 'extract', 'powder', 'dried', 'dehydrated',
        'salt', 'phosphate', 'chloride', 'sulfate', 'carbonate', 'oxide',
        'supplement', 'preserve', 'natural flavor', 'artificial flavor',
        'liver', 'heart', 'gizzard', 'bone meal', 'blood meal'
    ]

    ingredient_count = sum(1 for ingredient in ingredient_indicators if ingredient in text_lower)

    # Check for technical ingredient terms that are strong indicators
    technical_indicators = [
        'sodium selenite', 'thiamine mononitrate', 'pyridoxine hydrochloride', 
        'riboflavin supplement', 'biotin', 'folic acid', 'choline chloride',
        'zinc sulfate', 'ferrous sulfate', 'manganese sulfate', 'copper sulfate',
        'vitamin e supplement', 'vitamin a supplement', 'vitamin d-3 supplement'
    ]
    
    # Check for common first ingredients
    common_first_ingredients = [
        'ground yellow corn', 'ground corn', 'chicken', 'beef', 'salmon', 'tuna',
        'water sufficient for processing', 'corn meal', 'rice', 'wheat', 'turkey',
        'lamb', 'fish meal', 'chicken meal', 'poultry meal'
    ]
    
    has_technical_terms = any(term in text_lower for term in technical_indicators)
    starts_with_ingredient = any(text_lower.startswith(ingredient) for ingredient in common_first_ingredients)
    
    # Valid ingredient list criteria (more comprehensive):
    # 1. Starts with an actual ingredient AND has commas
    # 2. Has "water sufficient for processing" (Purina wet food pattern)
    # 3. Has many ingredient terms AND proper formatting
    # 4. Short list with multiple ingredient terms (for compact lists)
    # 5. Contains technical vitamin/mineral terms (strong indicator)
    # 6. Starts with common first ingredient (even without commas initially)
    if (any(actual_ingredient_patterns) and has_commas) or \
       ('water sufficient for processing' in text_lower) or \
       (ingredient_count >= 5 and has_commas and word_count >= 20) or \
       (ingredient_count >= 3 and word_count <= 50 and any(term in text_lower for term in ['tuna', 'chicken', 'salmon', 'beef', 'broth', 'gum', 'vitamin'])) or \
       (has_technical_terms and ingredient_count >= 3) or \
       (starts_with_ingredient and ingredient_count >= 3):
        return True

    return False

def clean_ingredients_text(text):
    """Clean and format ingredients text"""
    try:
        # Remove extra whitespace and normalize
        text = ' '.join(text.split())
        
        # Convert British spelling "fibre" to American spelling "fiber"
        import re
        text = re.sub(r'\bfibre\b', 'fiber', text, flags=re.IGNORECASE)
        
        # Remove "Vitamins" wrapper and keep only the individual vitamins
        # Pattern: "Vitamins (Vitamin E Supplement, Vitamin B3 (Niacin Supplement), ...)"
        # Should become: "Vitamin E Supplement, Vitamin B3 (Niacin Supplement), ..."
        
        # Use a more robust approach to handle nested parentheses
        def extract_vitamins_content(text):
            # Find "Vitamins (" and then match balanced parentheses
            start_pattern = r'\bVitamins\s*\('
            match = re.search(start_pattern, text, re.IGNORECASE)
            if match:
                start_pos = match.end() - 1  # Position of opening parenthesis
                paren_count = 0
                end_pos = start_pos
                
                for i, char in enumerate(text[start_pos:], start_pos):
                    if char == '(':
                        paren_count += 1
                    elif char == ')':
                        paren_count -= 1
                        if paren_count == 0:
                            end_pos = i
                            break
                
                if paren_count == 0:  # Found matching closing parenthesis
                    vitamins_content = text[start_pos + 1:end_pos]  # Content inside parentheses
                    # Replace the entire "Vitamins (...)" with just the content
                    return text[:match.start()] + vitamins_content + text[end_pos + 1:]
            
            return text
        
        # Remove "Minerals" wrapper and keep only the individual minerals
        # Pattern: "Minerals (Zinc Proteinate, Iron Proteinate, Potassium Chloride, ...)"
        # Should become: "Zinc Proteinate, Iron Proteinate, Potassium Chloride, ..."
        
        def extract_minerals_content(text):
            # Find "Minerals (" and then match balanced parentheses
            start_pattern = r'\bMinerals\s*\('
            match = re.search(start_pattern, text, re.IGNORECASE)
            if match:
                start_pos = match.end() - 1  # Position of opening parenthesis
                paren_count = 0
                end_pos = start_pos
                
                for i, char in enumerate(text[start_pos:], start_pos):
                    if char == '(':
                        paren_count += 1
                    elif char == ')':
                        paren_count -= 1
                        if paren_count == 0:
                            end_pos = i
                            break
                
                if paren_count == 0:  # Found matching closing parenthesis
                    minerals_content = text[start_pos + 1:end_pos]  # Content inside parentheses
                    # Replace the entire "Minerals (...)" with just the content
                    return text[:match.start()] + minerals_content + text[end_pos + 1:]
            
            return text
        
        text = extract_vitamins_content(text)
        text = extract_minerals_content(text)
        
        # Check if this looks like a valid ingredient list first
        # Valid ingredient lists are typically comma-separated and contain food ingredients
        if ',' in text and len(text) < 5000:  # Increased length limit to capture complete ingredient lists
            food_count = 0
            food_words = ['chicken', 'beef', 'fish', 'salmon', 'turkey', 'lamb', 'pork', 'duck', 
                         'broth', 'breast', 'fillet', 'liver', 'heart', 'starch', 'gum', 'meal',
                         'protein', 'vitamin', 'mineral', 'oil', 'fat', 'rice', 'corn', 'potato',
                         'flaxseed', 'pumpkinseeds', 'clay', 'carrots', 'apples', 'squash',
                         # Additional supplement/vitamin terms for complete extraction
                         'calcium', 'phosphate', 'supplement', 'acid', 'chloride', 'oxide',
                         'sulfate', 'chelate', 'mononitrate', 'hydrochloride', 'iodate', 'selenite',
                         'biotin', 'niacin', 'riboflavin', 'thiamine', 'pyridoxine', 'cyanocobalamin',
                         'choline', 'taurine', 'microalgae', 'bisulfite', 'menadione', 'tocopherols']
            
            for word in food_words:
                if word.lower() in text.lower():
                    food_count += 1
            
            # If it has multiple food words and commas, it's likely a valid ingredient list
            if food_count >= 3:
                # Only filter out if it's obviously not ingredients
                obvious_non_ingredients = [
                    '| applaws', '| purina', '| hill\'s', '| royal canin', '| blue buffalo',
                    'buy now', 'where to buy', 'subscribe', 'add to cart', 'home page',
                    'main menu', 'navigation', 'site header', 'footer'
                ]
                
                text_lower = text.lower()
                for indicator in obvious_non_ingredients:
                    if indicator in text_lower:
                        return None
                
                # Remove common prefixes including "Our Ingredients"
                prefixes_to_remove = [
                    'ingredients:', 'ingredient list:', 'contains:', 'made with:',
                    'ingredients include:', 'this product contains:', 'our ingredients',
                    'our ingredients:', 'ingredients'
                ]
                
                for prefix in prefixes_to_remove:
                    if text_lower.startswith(prefix.lower()):
                        text = text[len(prefix):].strip()
                        text_lower = text.lower()  # Update text_lower after removing prefix
                        break
                
                # Stop extraction when nutritional information starts
                nutritional_indicators = [
                    'nutritional info', 'nutritional information', 'nutrition facts',
                    'guaranteed analysis', 'caloric content', 'feeding guidelines',
                    'crude protein', 'crude fat', 'crude fiber', 'moisture',
                    'kcal/kg', 'kcal/cup', 'metabolizable energy', 'aafco',
                    'complete + balanced', 'formulated to meet', 'nutrient profiles'
                ]
                
                for indicator in nutritional_indicators:
                    pos = text_lower.find(indicator)
                    if pos != -1:
                        text = text[:pos].strip()
                        break
                
                # Clean up the text
                text = text.strip()
                if text.endswith('.'):
                    text = text[:-1]  # Remove trailing period
                
                # Remove any remaining "ingredients" at the start if it got through
                if text.lower().startswith('ingredients '):
                    text = text[12:].strip()
                
                return text
        
        # If it doesn't look like a valid ingredient list, apply stricter filtering
        # Filter out page titles, product names, and disclaimer content
        title_indicators = [
            '| applaws', '| purina', '| hill\'s', '| royal canin', '| blue buffalo',
            'oz can', 'oz bag', 'lb bag', 'kg bag', 'pouches', 'pack of',
            'can change in consistency', 'cold conditions', 'transportation', 'weather circumstances',
            'beyond our control', 'completely safe', 'microwave', 'removed from the can',
            'nutritional value', 'original consistency', 'gently warming', 'if preferred',
            'shop by', 'discover all', 'product type', 'wet food', 'dry food', 'treats',
            'kitten adult senior', 'flavors textures', 'broth pâté gravy mousse',
            'buy now', 'where to buy', 'subscribe', 'add to cart', 'home page',
            'main menu', 'navigation', 'site header', 'footer', 'terms and conditions',
            'privacy policy', 'shipping information', 'customer service'
        ]
        
        text_lower = text.lower()
        for indicator in title_indicators:
            if indicator in text_lower:
                return None  # Return None to indicate this isn't valid ingredients
        
        # Additional check: if text looks like a product title (has brand + size info)
        if ('|' in text and any(brand in text_lower for brand in ['applaws', 'purina', 'hill\'s', 'royal canin'])):
            return None
        
        # Remove common prefixes including "Our Ingredients"
        prefixes_to_remove = [
            'ingredients:', 'ingredient list:', 'contains:', 'made with:',
            'ingredients include:', 'this product contains:', 'our ingredients',
            'our ingredients:', 'ingredients'
        ]
        
        for prefix in prefixes_to_remove:
            if text_lower.startswith(prefix.lower()):
                text = text[len(prefix):].strip()
                break
        
        # Limit length to avoid overly long ingredient lists (but allow for complete lists)
        if len(text) > 5000:  # Increased from 2500 to 5000 to accommodate complete ingredient lists
            text = text[:5000] + "..."
        
        return text.strip()
    except:
        return text

def extract_ingredients_from_url(url):
    """Extract ingredients from URL only (for direct image URLs) - usually not possible"""
    return "Ingredients not available for direct image URLs"

def extract_ingredients_from_json_data(json_data):
    """Extract ingredients from JSON-LD or other structured data"""
    try:
        # Common paths where ingredients might be stored
        possible_paths = [
            ['ingredients'],
            ['additionalProperty', 'ingredients'],
            ['nutrition', 'ingredients'],
            ['product', 'ingredients'],
            ['offers', 'ingredients'],
            ['description']  # Sometimes full descriptions contain ingredient lists
        ]
        
        def get_nested_value(data, path):
            """Get nested dictionary value by path"""
            for key in path:
                if isinstance(data, dict) and key in data:
                    data = data[key]
                elif isinstance(data, list) and len(data) > 0:
                    data = data[0]
                    if isinstance(data, dict) and key in data:
                        data = data[key]
                else:
                    return None
            return data
        
        for path in possible_paths:
            value = get_nested_value(json_data, path)
            if value and isinstance(value, str) and len(value) > 50:
                if is_likely_ingredient_list(value):
                    formatted_content = format_ingredient_list(value)
                    formatted_content = clean_extra_content(formatted_content)
                    if len(formatted_content) > 50:
                        return formatted_content
        
        return None
    except:
        return None

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/scrape', methods=['POST'])
def scrape_url():
    """Scrape the provided URL for brand information"""
    try:
        url = request.json.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        # Add http if not present
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Validate URL
        parsed = urlparse(url)
        if not parsed.netloc:
            return jsonify({'error': 'Invalid URL format'}), 400
        
        # Set up comprehensive headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
        
        # Make request with retry logic
        session = requests.Session()
        session.headers.update(headers)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Add a small delay to be more polite
                if attempt > 0:
                    time.sleep(2)
                
                response = session.get(url, timeout=15, allow_redirects=True)
                response.raise_for_status()
                break
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    if attempt < max_retries - 1:
                        # Try with a different user agent
                        alternate_agents = [
                            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
                            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        ]
                        session.headers.update({'User-Agent': alternate_agents[attempt]})
                        continue
                    else:
                        return jsonify({'error': f'Access denied by website (403). This site may be blocking automated requests. Try a different URL or the site may require authentication.'}), 400
                else:
                    raise
            except requests.exceptions.RequestException:
                if attempt == max_retries - 1:
                    raise
        
        # Check if this is a direct image URL
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', '.pdf']
        # Handle URLs with query parameters by checking the path part
        parsed_url = urlparse(url.lower())
        url_path = parsed_url.path
        
        # Check both the full URL and the path without query parameters
        is_direct_image = (
            any(url_path.endswith(ext) for ext in image_extensions) or 
            any(url.lower().endswith(ext) for ext in image_extensions) or
            # Also check if the path contains image extensions before query params
            any(ext in url_path for ext in image_extensions) or
            # Super aggressive: check if URL contains 'photo' and image domain
            ('photo' in url.lower() and any(domain in url.lower() for domain in ['images.', 'image.', 'img.', 'static.', 'cdn.']))
        )
        
        if is_direct_image:
            # This is a direct image URL
            brand = extract_brand_from_url(url) or "Brand not found"
            image_url = url
            # For direct images, only extract pet type, food type, and life stage from URL
            pet_type = extract_pet_type_from_url(url)
            texture = extract_food_type_from_url(url)
            life_stage = extract_life_stage_from_url(url)
            ingredients = extract_ingredients_from_url(url)
            guaranteed_analysis = None  # Cannot extract guaranteed analysis from direct images
            nutritional_info = None  # Cannot extract nutritional info from direct images
            
            # For direct images, extract name from URL
            name = extract_product_name_from_url(url)
            
            # OVERRIDE: If "Senior" appears in the product name, set life stage to "senior"
            # This takes priority over any other life stage detection (including "all life stages")
            if name and 'senior' in name.lower():
                life_stage = "senior"
            
            # Debug info for direct images
            total_images = 1  # The direct image itself
            images_with_src = 1
            images_with_data_src = 0
        else:
            # Parse HTML for regular web pages
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract brand, image, pet type, food type, life stage, ingredients, guaranteed analysis, nutritional info, and product name
            brand = extract_brand(soup, url)
            image_url = extract_image_url(soup, url)
            pet_type = extract_pet_type(soup, url)
            texture = extract_food_type(soup, url)
            life_stage = extract_life_stage(soup, url)
            
            # For Applaws, extract all dropdown content in one go to be more efficient
            if 'applaws.com' in url.lower():
                applaws_data = extract_applaws_dropdown_data(url)
                ingredients = applaws_data.get('ingredients') or extract_ingredients(soup, url)
                guaranteed_analysis = applaws_data.get('guaranteed_analysis') or extract_guaranteed_analysis(soup, url)
                nutritional_info = applaws_data.get('nutritional_info') or extract_nutritional_info(soup, url)
            else:
                ingredients = extract_ingredients(soup, url)
                guaranteed_analysis = extract_guaranteed_analysis(soup, url)
                nutritional_info = extract_nutritional_info(soup, url)
            
            # Extract product name and size, then combine them
            product_name = extract_product_name(soup, url)
            product_size = extract_product_size(soup, url)
            
            # Create the final name with size in parentheses if size is found
            if product_name and product_size:
                name = f"{product_name} ({product_size})"
            else:
                name = product_name  # Just the name without size if size not found
            
            # OVERRIDE: If "Senior" appears in the product name, set life stage to "senior"
            # This takes priority over any other life stage detection (including "all life stages")
            if name and 'senior' in name.lower():
                life_stage = "senior"
            
            # Debug: Count total images found on page
            total_images = len(soup.find_all('img'))
            images_with_src = len(soup.find_all('img', src=True))
            images_with_data_src = len(soup.find_all('img', attrs={'data-src': True}))
        
        # Store debug message with image strategy info
        debug_message = f"Found {total_images}/{images_with_src + images_with_data_src} images on page (including data-src)"
        if image_url != "Image not found":
            debug_message += f" - Using strategy: {extract_image_url._last_strategy if hasattr(extract_image_url, '_last_strategy') else 'direct_url'}"
        
        # Generate random barcode ID placeholder
        barcode_id = generate_random_id()
        
        # Save to data file
        data = load_data()
        new_entry = {
            'id': len(data) + 1,
            'barcodeId': barcode_id,
            'url': url,
            'brand': brand,
            'name': name,
            'imageUrl': image_url,
            'petType': pet_type,
            'texture': texture,
            'lifeStage': life_stage,
            'ingredients': ingredients,
            'guaranteedAnalysis': guaranteed_analysis,
            'nutritionalInfo': nutritional_info,
            'timestamp': datetime.now().isoformat(),
            'domain': parsed.netloc,
            'debug_info': {
                'total_images': total_images,
                'images_with_src': images_with_src + images_with_data_src,
                'extraction_method': 'direct_image' if is_direct_image else 'html_parsing'
            }
        }
        data.append(new_entry)
        save_data(data)
        
        return jsonify({
            'success': True,
            'brand': brand,
            'barcodeId': barcode_id,
            'name': name,
            'imageUrl': image_url,
            'petType': pet_type,
            'texture': texture,
            'lifeStage': life_stage,
            'ingredients': ingredients,
            'guaranteedAnalysis': guaranteed_analysis,
            'nutritionalInfo': nutritional_info,
            'id': new_entry['id'],
            'url': url,
            'debug_info': debug_message
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to fetch URL: {str(e)}'}), 400
    except Exception as e:
        import traceback
        print(f"FLASK ERROR: {str(e)}")
        print("Full traceback:")
        traceback.print_exc()
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/data')
def get_data():
    """Get all scraped data"""
    data = load_data()
    return jsonify(data)

@app.route('/data/<int:item_id>', methods=['DELETE'])
def delete_data_item(item_id):
    """Delete a specific data item"""
    data = load_data()
    data = [item for item in data if item.get('id') != item_id]
    save_data(data)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000) 