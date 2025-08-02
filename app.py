from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import re
import time
from urllib.parse import urlparse, urljoin

app = Flask(__name__)

# File to store scraped data
DATA_FILE = 'scraped_data.json'

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

def extract_brand(soup, url):
    """Extract brand information from the webpage"""
    brand = None
    
    # Common brand extraction strategies
    strategies = [
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
    
    for strategy in strategies:
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
            'blue-wilderness', 'blue wilderness', 'nulo', 'earthborn', 'solid-gold', 'solid gold'
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
    """Extract food type (wet, dry, raw, treats) from URL and page content"""
    try:
        # Convert to lowercase for easier matching
        url_lower = url.lower()
        
        # Define keywords for each food type
        wet_keywords = ['wet', 'canned', 'pate', 'gravy', 'sauce', 'stew', 'chunks', 'shreds', 'morsels']
        dry_keywords = ['dry', 'kibble', 'pellets', 'biscuits', 'crunch', 'formula']
        raw_keywords = ['raw', 'freeze-dried', 'frozen', 'fresh', 'refrigerated']
        treat_keywords = ['treat', 'snack', 'chew', 'jerky', 'dental', 'training', 'reward', 'biscuit']
        
        # Check URL path first (most reliable)
        for keyword in treat_keywords:
            if keyword in url_lower:
                return 'treats'
        
        for keyword in raw_keywords:
            if keyword in url_lower:
                return 'raw'
        
        for keyword in wet_keywords:
            if keyword in url_lower:
                return 'wet'
        
        for keyword in dry_keywords:
            if keyword in url_lower:
                return 'dry'
        
        # Check page title
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text('').lower()
            for keyword in treat_keywords:
                if keyword in title_text:
                    return 'treats'
            for keyword in raw_keywords:
                if keyword in title_text:
                    return 'raw'
            for keyword in wet_keywords:
                if keyword in title_text:
                    return 'wet'
            for keyword in dry_keywords:
                if keyword in title_text:
                    return 'dry'
        
        # Check meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            desc_content = meta_desc.get('content', '').lower()
            for keyword in treat_keywords:
                if keyword in desc_content:
                    return 'treats'
            for keyword in raw_keywords:
                if keyword in desc_content:
                    return 'raw'
            for keyword in wet_keywords:
                if keyword in desc_content:
                    return 'wet'
            for keyword in dry_keywords:
                if keyword in desc_content:
                    return 'dry'
        
        # Check Open Graph title and description
        og_title = soup.find('meta', {'property': 'og:title'})
        if og_title:
            og_title_content = og_title.get('content', '').lower()
            for keyword in treat_keywords:
                if keyword in og_title_content:
                    return 'treats'
            for keyword in raw_keywords:
                if keyword in og_title_content:
                    return 'raw'
            for keyword in wet_keywords:
                if keyword in og_title_content:
                    return 'wet'
            for keyword in dry_keywords:
                if keyword in og_title_content:
                    return 'dry'
        
        og_desc = soup.find('meta', {'property': 'og:description'})
        if og_desc:
            og_desc_content = og_desc.get('content', '').lower()
            for keyword in treat_keywords:
                if keyword in og_desc_content:
                    return 'treats'
            for keyword in raw_keywords:
                if keyword in og_desc_content:
                    return 'raw'
            for keyword in wet_keywords:
                if keyword in og_desc_content:
                    return 'wet'
            for keyword in dry_keywords:
                if keyword in og_desc_content:
                    return 'dry'
        
        # Check first few headings
        headings = soup.find_all(['h1', 'h2', 'h3'], limit=5)
        for heading in headings:
            heading_text = heading.get_text('').lower()
            for keyword in treat_keywords:
                if keyword in heading_text:
                    return 'treats'
            for keyword in raw_keywords:
                if keyword in heading_text:
                    return 'raw'
            for keyword in wet_keywords:
                if keyword in heading_text:
                    return 'wet'
            for keyword in dry_keywords:
                if keyword in heading_text:
                    return 'dry'
        
        # Default fallback - could not determine
        return 'unknown'
        
    except Exception:
        return 'unknown'

def extract_food_type_from_url(url):
    """Extract food type from URL only (for direct image URLs)"""
    try:
        url_lower = url.lower()
        
        # Define keywords for each food type
        wet_keywords = ['wet', 'canned', 'pate', 'gravy', 'sauce', 'stew', 'chunks', 'shreds', 'morsels']
        dry_keywords = ['dry', 'kibble', 'pellets', 'biscuits', 'crunch', 'formula']
        raw_keywords = ['raw', 'freeze-dried', 'frozen', 'fresh', 'refrigerated']
        treat_keywords = ['treat', 'snack', 'chew', 'jerky', 'dental', 'training', 'reward', 'biscuit']
        
        # Check URL for keywords (priority order: treats, raw, wet, dry)
        for keyword in treat_keywords:
            if keyword in url_lower:
                return 'treats'
        
        for keyword in raw_keywords:
            if keyword in url_lower:
                return 'raw'
        
        for keyword in wet_keywords:
            if keyword in url_lower:
                return 'wet'
        
        for keyword in dry_keywords:
            if keyword in url_lower:
                return 'dry'
        
        return 'unknown'
        
    except Exception:
        return 'unknown'

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

def extract_life_stage(soup, url):
    """Extract life stage from the webpage content and URL"""
    try:
        # Get text content from various sources
        url_lower = url.lower()
        title = soup.find('title')
        title_text = title.get_text().lower() if title else ""
        
        # Get meta description
        meta_desc = soup.find('meta', {'name': 'description'})
        desc_text = meta_desc.get('content', '').lower() if meta_desc else ""
        
        # Get Open Graph data
        og_title = soup.find('meta', {'property': 'og:title'})
        og_title_text = og_title.get('content', '').lower() if og_title else ""
        
        og_desc = soup.find('meta', {'property': 'og:description'})
        og_desc_text = og_desc.get('content', '').lower() if og_desc else ""
        
        # Get main heading content
        headings = soup.find_all(['h1', 'h2', 'h3'])
        heading_text = ' '.join([h.get_text().lower() for h in headings[:5]])  # First 5 headings
        
        # Get main content areas for more comprehensive search
        main_content = soup.find_all(['main', 'article', 'section', 'div'], limit=5)
        content_text = ' '.join([content.get_text()[:500].lower() for content in main_content])  # First 500 chars each
        
        # Get entire page body text (limited to avoid noise) for thorough search
        body = soup.find('body')
        body_text = body.get_text()[:3000].lower() if body else ""  # First 3000 characters
        
        # Combine all text sources
        all_text = f"{url_lower} {title_text} {desc_text} {og_title_text} {og_desc_text} {heading_text} {content_text} {body_text}"
        
        # Life stage keywords (expanded and more specific)
        kitten_keywords = ['kitten', 'kittens']
        puppy_keywords = ['puppy', 'puppies'] 
        senior_keywords = ['senior', 'seniors', 'mature', 'aged', '7+', '8+', '9+', '10+', '11+', '12+']
        all_stages_keywords = [
            'all life stages', 'all ages', 'all stages', 'life stages', 'any age', 'every stage',
            'aafco cat food nutrient profiles for all life stages',
            'aafco dog food nutrient profiles for all life stages',
            'formulated for all life stages',
            'complete and balanced for all life stages',
            'suitable for all life stages'
        ]
        
        # Check for all life stages first (most specific) - be more thorough
        for keyword in all_stages_keywords:
            if keyword in all_text:
                return "all"
        
        # Check for specific life stages
        for keyword in kitten_keywords:
            if keyword in all_text:
                return "kitten"
        
        for keyword in puppy_keywords:
            if keyword in all_text:
                return "puppy"
            
        for keyword in senior_keywords:
            if keyword in all_text:
                return "senior"
        
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
            food_type = extract_food_type_from_url(url)
            life_stage = extract_life_stage_from_url(url)
        else:
            # Parse HTML for regular web pages
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract brand, image, pet type, food type, and life stage
            brand = extract_brand(soup, url)
            image_url = extract_image_url(soup, url)
            pet_type = extract_pet_type(soup, url)
            food_type = extract_food_type(soup, url)
            life_stage = extract_life_stage(soup, url)
        
        # Debug: Count total images found on page
        total_images = len(soup.find_all('img'))
        images_with_src = len(soup.find_all('img', src=True))
        images_with_data_src = len(soup.find_all('img', attrs={'data-src': True}))
        
        # Store debug message with image strategy info
        debug_message = f"Found {total_images}/{images_with_src + images_with_data_src} images on page (including data-src)"
        if image_url != "Image not found":
            debug_message += f" - Using strategy: {extract_image_url._last_strategy}"
        
        # Save to data file
        data = load_data()
        new_entry = {
            'id': len(data) + 1,
            'url': url,
            'brand': brand,
            'imageURL': image_url,
            'petType': pet_type,
            'foodType': food_type,
            'lifeStage': life_stage,
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
            'imageURL': image_url,
            'petType': pet_type,
            'foodType': food_type,
            'lifeStage': life_stage,
            'id': new_entry['id'],
            'url': url,
            'debug_info': debug_message
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Failed to fetch URL: {str(e)}'}), 400
    except Exception as e:
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