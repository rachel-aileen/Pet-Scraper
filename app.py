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
    
    # Remove periods from individual ingredients and at the end
    if ',' in cleaned_text:
        # Split by commas, remove periods from each ingredient, then rejoin
        ingredients = [ing.strip().rstrip('.') for ing in cleaned_text.split(',')]
        cleaned_text = ', '.join(ingredients)
    
    # Remove any trailing period
    cleaned_text = cleaned_text.rstrip('.')
    
    return cleaned_text

def format_ingredient_list(ingredient_text):
    """Universal function to format ingredient lists with proper comma separation"""
    import re
    
    # Remove any periods at the end of the entire text first
    ingredient_text = ingredient_text.strip()
    if ingredient_text.endswith('.'):
        ingredient_text = ingredient_text[:-1].strip()
    
    # If already has good comma separation, clean and return
    if ', ' in ingredient_text and ingredient_text.count(',') > 3:
        # Split into individual ingredients, remove periods from each, then rejoin
        ingredients = [ing.strip().rstrip('.') for ing in ingredient_text.split(',')]
        return ', '.join(ingredients)
    
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
    
    # Final cleanup: split ingredients, remove periods from each, then rejoin
    if ',' in formatted_text:
        ingredients = [ing.strip().rstrip('.') for ing in formatted_text.split(',')]
        formatted_text = ', '.join(ingredients)
    
    # Remove any remaining period at the end
    formatted_text = formatted_text.strip().rstrip('.')
    
    return formatted_text

def extract_ingredients(soup, url):
    """Extract ingredients from the soup with multiple strategies"""
    
    # PRIORITY 0: Look for "Ingredients:" label followed by actual ingredient list
    page_text = soup.get_text()
    
    # Pattern to find "Ingredients:" followed by content, stopping at nutritional info or other sections
    ingredient_label_pattern = r'ingredients?[:\s]*(.{20,2000}?)(?=\s*(?:nutritional|guaranteed|feeding|analysis|instructions|calories|kcal|crude protein|crude fat|moisture|ash content|view all ingredients|download.*ingredient|$))'
    
    import re
    
    # Find ALL matches, not just the first one
    all_ingredient_matches = list(re.finditer(ingredient_label_pattern, page_text, re.IGNORECASE | re.DOTALL))
    
    # Score each match to find the best one (actual ingredient list vs marketing copy)
    best_match = None
    best_score = 0
    
    for match in all_ingredient_matches:
        potential_ingredients = match.group(1).strip()
        
        # Clean up common prefixes and navigation elements that appear after "Ingredients:"
        prefixes_to_remove = [
            r'^\d+\s+of\s+\d+',  # "1 of 8"
            r'^enlarge\s+view',   # "Enlarge View"
            r'^previous',         # "Previous"
            r'^next',            # "Next"
            r'^view\s+all',      # "View All"
            r'^expand',          # "Expand"
            r'^show\s+more',     # "Show More"
        ]
        
        for prefix in prefixes_to_remove:
            potential_ingredients = re.sub(prefix, '', potential_ingredients, flags=re.IGNORECASE).strip()
        
        # Score this match based on how likely it is to be an actual ingredient list
        score = 0
        potential_lower = potential_ingredients.lower()
        
        # VERY high score for actual ingredient starters (common first ingredients)
        primary_starters = [
            'ground yellow corn', 'ground corn', 'chicken', 'beef', 'salmon', 'tuna', 
            'water sufficient for processing', 'corn meal', 'rice', 'wheat', 'turkey',
            'lamb', 'fish meal', 'chicken meal', 'poultry meal', 'meat and bone meal',
            'tuna fillet'  # Added for Applaws
        ]
        for starter in primary_starters:
            if potential_lower.startswith(starter):
                score += 100  # Very high score for likely first ingredients
                break
        
        # High score for technical ingredient terms (these appear in real ingredient lists)
        technical_terms = [
            'sodium selenite', 'thiamine mononitrate', 'pyridoxine hydrochloride', 
            'riboflavin supplement', 'biotin', 'folic acid', 'choline chloride',
            'zinc sulfate', 'ferrous sulfate', 'manganese sulfate', 'copper sulfate',
            'potassium iodide', 'calcium carbonate', 'tricalcium phosphate',
            'dicalcium phosphate', 'monocalcium phosphate', 'vitamin e supplement',
            'vitamin a supplement', 'vitamin d-3 supplement', 'menadione sodium bisulfite',
            'natural flavor', 'artificial flavor', 'mixed tocopherols', 'citric acid',
            'rosemary extract', 'bha', 'bht', 'ethoxyquin',
            'thiamine mononitrate', 'riboflavin', 'menadione nicotinamide bisulfite',  # Added for Applaws
            'marine microalgae oil', 'amino acid chelate', 'pantothenic acid'
        ]
        for term in technical_terms:
            if term in potential_lower:
                score += 15  # High score for technical vitamin/mineral terms
        
        # Medium score for common ingredient terms
        common_ingredients = [
            'broth', 'gum', 'powder', 'vitamin', 'mineral', 'supplement', 'extract', 
            'oil', 'starch', 'flour', 'meal', 'by-product', 'gluten', 'protein',
            'concentrate', 'isolate', 'digest', 'hydrolysate',
            'egg whites', 'taurine', 'calcium chloride'  # Added for Applaws
        ]
        for term in common_ingredients:
            if term in potential_lower:
                score += 8
        
        # NEGATIVE score for marketing language (these indicate marketing copy, not ingredients)
        marketing_terms = [
            'tempt', 'delicate', 'flavorful', 'extraordinary', 'convenient', 'serve', 
            'indulgence', 'recipe', 'featuring', 'gourmet', 'perfect', 'delicious',
            'appetizing', 'irresistible', 'savory', 'tender', 'wholesome', 'nutritious',
            'complete and balanced', 'specially formulated', 'premium', 'quality',
            'authentic', 'restaurant', 'chef', 'culinary', 'artisan', 'handcrafted',
            'natural goodness', 'real taste', 'mouth-watering', 'delectable'
        ]
        for term in marketing_terms:
            if term in potential_lower:
                score -= 15  # Heavy penalty for marketing language
        
        # VERY negative score for promotional content
        promotional_terms = [
            'earn points', 'purchase', 'app', 'discount', 'offer', 'sale', 'buy',
            'shop', 'store', 'retailer', 'order', 'shipping', 'delivery', 'cart'
        ]
        for term in promotional_terms:
            if term in potential_lower:
                score -= 50  # Very heavy penalty for promotional content
        
        # Positive score for proper ingredient list characteristics
        # Real ingredient lists tend to be concise and technical
        if len(potential_ingredients) < 1000:  # Not too long
            score += 5
        if potential_ingredients.count(',') >= 5:  # Has many comma-separated items
            score += 10
        if len(potential_ingredients.split()) < 200:  # Not too wordy (marketing copy is wordy)
            score += 5
        
        # If this is the best scoring match so far
        if score > best_score and score > 0:
            best_score = score
            best_match = potential_ingredients
    
    # Use the best match if we found one
    if best_match:
        # Only proceed if it looks like an actual ingredient list
        if (best_match and 
            len(best_match) > 10 and  # Substantial content (reduced threshold)
            (',' in best_match or  # Has comma separation OR
             any(ingredient in best_match.lower() for ingredient in ['tuna', 'chicken', 'beef', 'salmon', 'broth', 'gum', 'vitamin', 'water sufficient for processing']) or  # Contains actual ingredients OR
             (len(best_match) < 200 and best_score > 30))):  # Short text with high ingredient score
            
            # Validate using our existing validation function
            if is_likely_ingredient_list(best_match):
                formatted_content = format_ingredient_list(best_match)
                formatted_content = clean_extra_content(formatted_content)
                if len(formatted_content) > 50:
                    return formatted_content

    # PRIORITY 1: Look for specific high-quality ingredient containers
    # Check for <p class="p1"> tags which often contain complete ingredient lists (Applaws)
    p1_tags = soup.find_all('p', class_='p1')
    for p1_tag in p1_tags:
        potential_content = p1_tag.get_text().strip()
        if potential_content and len(potential_content) > 50:
            # Check if this looks like an ingredient list
            if (any(starter in potential_content.lower()[:50] for starter in ['tuna fillet', 'chicken', 'beef', 'salmon', 'water sufficient for processing', 'ground yellow corn']) and
                potential_content.count(',') >= 3):  # Has multiple comma-separated items
                if is_likely_ingredient_list(potential_content):
                    formatted_content = format_ingredient_list(potential_content)
                    formatted_content = clean_extra_content(formatted_content)
                    if len(formatted_content) > 50:
                        return formatted_content

    # PRIORITY 2: Try to find explicit "Ingredients" sections and dropdowns
    ingredient_patterns = [
        r'ingredients?[:\s]*([^.!?\n]+(?:[,.][^.!?\n]+)*)',
        r'ingredient\s*list[:\s]*([^.!?\n]+(?:[,.][^.!?\n]+)*)'
    ]
    
    for pattern in ingredient_patterns:
        matches = re.finditer(pattern, page_text, re.IGNORECASE)
        for match in matches:
            potential_content = match.group(1).strip()
            if len(potential_content) > 20 and potential_content.count(',') >= 2:
                if is_likely_ingredient_list(potential_content):
                    formatted_content = format_ingredient_list(potential_content)
                    formatted_content = clean_extra_content(formatted_content)
                    if len(formatted_content) > 50:
                        return formatted_content
    
    # PRIORITY 3: Look for ingredient information in dropdowns and accordions
    dropdown_classes = [
        'collapse', 'accordion', 'dropdown', 'expandable', 'toggle',
        'ingredient-info', 'product-details', 'nutrition-info'
    ]
    
    for class_name in dropdown_classes:
        elements = soup.find_all(class_=re.compile(class_name, re.I))
        for element in elements:
            text = element.get_text()
            if 'ingredient' in text.lower():
                lines = text.split('\n')
                for line in lines:
                    if 'ingredient' in line.lower() and len(line) > 20:
                        # Look for the next substantial line that might be ingredients
                        idx = lines.index(line)
                        for next_line in lines[idx:idx+5]:  # Check next few lines
                            if (len(next_line.strip()) > 30 and 
                                next_line.count(',') >= 2 and
                                is_likely_ingredient_list(next_line.strip())):
                                formatted_content = format_ingredient_list(next_line.strip())
                                formatted_content = clean_extra_content(formatted_content)
                                if len(formatted_content) > 50:
                                    return formatted_content

    # ... existing code ...

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
                        return clean_ingredients_text(text)
            current = current.next_sibling
        
        # If we found content, combine it
        if content_parts:
            combined = ' '.join(content_parts)
            if is_likely_ingredient_list(combined):
                return clean_ingredients_text(combined)
                
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
                        return clean_ingredients_text(ingredients)
            
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
    try:
        text_lower = text.lower()
        
        # Look for ingredient section patterns
        patterns = [
            r'ingredients?[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
            r'ingredient (?:list|panel)[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
            r'contains[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
            r'made with[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)'
        ]
        
        for pattern in patterns:
            import re
            matches = re.findall(pattern, text_lower, re.DOTALL | re.IGNORECASE)
            for match in matches:
                if len(match.strip()) > 20 and is_likely_ingredient_list(match):
                    return clean_ingredients_text(match)
        
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
        'among the protein sources', 'this formula contains', 'additionally, it provides'
    ]

    # Check for description patterns - these are NOT ingredient lists
    description_count = sum(1 for desc in description_indicators if desc in text_lower)
    if description_count >= 2:  # If it has multiple description phrases, it's marketing copy
        return False

    # Immediately reject marketing descriptions
    marketing_indicators = [
        'tantalize', 'tastebuds', 'gourmet', 'delicious flavor', 'perfect way',
        'hand-crafted', 'toppers offer', 'invite your cat', 'experience gourmet',
        'looks good enough for you', 'crafted especially for her', 'attention to detail',
        'unique taste cats love', 'tender bites', 'savory broth', 'most refined',
        'between-meal snack', 'complement tray', 'single-serve', 'adult cat food complement',
        'made to meet your', 'ingredient criteria', 'serve fancy feast', 'favorite fancy feast',
        'add delicious flavor to her menu', 'real high quality ingredients'
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
        '| applaws', 'oz can', 'lb bag', 'wet cat food', 'dry cat food',
        'cat treats', 'dog food', 'pet food', '- amazon', '- chewy',
        '- petco', '- petsmart', 'product page', 'buy online'
    ]

    for title in title_indicators:
        if title in text_lower:
            return False

    # For actual ingredient lists, look for specific patterns
    # Real ingredient lists typically start with ingredients and are comma-separated
    actual_ingredient_patterns = [
        text_lower.startswith('chicken'),
        text_lower.startswith('beef'),
        text_lower.startswith('salmon'),
        text_lower.startswith('tuna'),
        text_lower.startswith('turkey'),
        text_lower.startswith('water sufficient for processing'),
        text_lower.startswith('corn'),
        text_lower.startswith('rice'),
        text_lower.startswith('wheat')
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

    # Enhanced validation for ingredient lists
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
        
        # Check if this looks like a valid ingredient list first
        # Valid ingredient lists are typically comma-separated and contain food ingredients
        if ',' in text and len(text) < 1500:  # Increased length limit
            food_count = 0
            food_words = ['chicken', 'beef', 'fish', 'salmon', 'turkey', 'lamb', 'pork', 'duck', 
                         'broth', 'breast', 'fillet', 'liver', 'heart', 'starch', 'gum', 'meal',
                         'protein', 'vitamin', 'mineral', 'oil', 'fat', 'rice', 'corn', 'potato',
                         'flaxseed', 'pumpkinseeds', 'clay', 'carrots', 'apples', 'squash']
            
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
        
        # Limit length to avoid overly long ingredient lists
        if len(text) > 1000:
            text = text[:1000] + "..."
        
        return text.strip()
    except:
        return text

def extract_ingredients_from_url(url):
    """Extract ingredients from URL only (for direct image URLs) - usually not possible"""
    return "Ingredients not available for direct image URLs"

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
            ingredients = extract_ingredients_from_url(url)
            
            # Debug info for direct images
            total_images = 1  # The direct image itself
            images_with_src = 1
            images_with_data_src = 0
        else:
            # Parse HTML for regular web pages
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract brand, image, pet type, food type, life stage, and ingredients
            brand = extract_brand(soup, url)
            image_url = extract_image_url(soup, url)
            pet_type = extract_pet_type(soup, url)
            food_type = extract_food_type(soup, url)
            life_stage = extract_life_stage(soup, url)
            ingredients = extract_ingredients(soup, url)
            
            # Debug: Count total images found on page
            total_images = len(soup.find_all('img'))
            images_with_src = len(soup.find_all('img', src=True))
            images_with_data_src = len(soup.find_all('img', attrs={'data-src': True}))
        
        # Store debug message with image strategy info
        debug_message = f"Found {total_images}/{images_with_src + images_with_data_src} images on page (including data-src)"
        if image_url != "Image not found":
            debug_message += f" - Using strategy: {extract_image_url._last_strategy if hasattr(extract_image_url, '_last_strategy') else 'direct_url'}"
        
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
            'ingredients': ingredients,
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
            'ingredients': ingredients,
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