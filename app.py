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
                    return brand.strip()
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
            'pro-plan', 'pro plan', 'beneful', 'fancy-feast', 'fancy feast', 'friskies',
            'whiskas', 'temptations', 'greenies', 'dentastix', 'cesar', 'sheba',
            'viva-raw', 'viva raw', 'stella-chewy', 'stella chewy', 'ziwi-peak', 'ziwi peak',
            'fromm', 'canidae', 'diamond', 'kirkland', 'costco', 'rachael-ray', 'rachael ray',
            'blue-wilderness', 'blue wilderness', 'nulo', 'earthborn', 'solid-gold', 'solid gold'
        ]
        
        # Clean URL for analysis
        url_lower = url.lower()
        url_parts = url_lower.replace('https://', '').replace('http://', '').replace('www.', '')
        
        # Look for brand in domain name
        for brand in pet_brands:
            brand_clean = brand.replace('-', '').replace(' ', '')
            if brand_clean in url_parts.replace('-', '').replace('/', '').replace('.', ''):
                # Format brand name properly
                return brand.replace('-', ' ').title()
        
        # Extract potential brand from URL path segments
        path_segments = url_parts.split('/')
        for segment in path_segments:
            # Clean segment
            segment = segment.replace('-', ' ').replace('_', ' ')
            # Look for brand patterns in segments
            for brand in pet_brands:
                if brand.replace('-', ' ').lower() in segment.lower():
                    return brand.replace('-', ' ').title()
            
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
                    return brand.replace('-', ' ').title()
        
        # Extract from domain name
        domain = url_parts.split('/')[0].split('.')[0]
        if domain and len(domain) > 3 and domain not in ['www', 'shop', 'store', 'pet', 'dog', 'cat', 'images', 'img', 'cdn', 'assets']:
            return domain.replace('-', ' ').title()
            
    except Exception:
        pass
    
    return None

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

def extract_image_url(soup, url):
    """Extract image URL from the webpage - prioritizes first reasonable image"""
    image_url = None
    
    # Simple and effective image extraction strategies
    strategies = [
        # Look for Open Graph image first (most reliable) - try multiple variations
        lambda: find_best_og_image(soup),
        lambda: soup.find('meta', {'property': 'product:image'}),
        lambda: soup.find('meta', {'name': 'twitter:image'}),
        
        # Look for structured data (JSON-LD)
        lambda: extract_from_json_ld(soup, 'image'),
        
        # Just find the first reasonable image on the page
        lambda: find_first_reasonable_image(soup),
        
        # Fallback to any image that's not tiny
        lambda: find_any_decent_image(soup),
        
        # Look for images in CSS background-image properties
        lambda: find_background_images(soup),
        
        # Look for images in JavaScript or data attributes
        lambda: find_script_images(soup),
        
        # AGGRESSIVE: Search entire HTML for any image-like URLs
        lambda: find_any_image_url_in_html(soup),
        
        # SUPER AGGRESSIVE: Direct regex search for og:image in HTML text
        lambda: find_og_image_in_raw_html(soup),
    ]
    
    for strategy in strategies:
        try:
            result = strategy()
            if result:
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
                    
                    return image_url
        except Exception:
            continue
    
    return "Image not found"



def find_first_reasonable_image(soup):
    """Find the first image that's not obviously a logo/icon"""
    images = soup.find_all('img', src=True)
    
    for img in images:
        try:
            src = img.get('src', '')
            alt = img.get('alt', '').lower()
            class_name = ' '.join(img.get('class', [])).lower()
            
            # Skip only obvious logos, icons, and navigation elements
            skip_keywords = ['logo', 'icon', 'nav', 'menu', 'header', 'footer', 'sprite']
            
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
        else:
            # Parse HTML for regular web pages
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract brand and image
            brand = extract_brand(soup, url)
            image_url = extract_image_url(soup, url)
        
        # Debug: Count total images found on page
        if is_direct_image:
            total_images = 1
            images_with_src = 1
            images_with_data_src = 0
            debug_message = "Direct image URL detected"
        else:
            total_images = len(soup.find_all('img'))
            images_with_src = len(soup.find_all('img', src=True))
            images_with_data_src = len(soup.find_all('img', {'data-src': True}))
            total_image_sources = images_with_src + images_with_data_src
            
            if total_image_sources == 0:
                debug_message = f'Found {total_image_sources}/{total_images} images - trying advanced detection (CSS, JavaScript, data attributes)'
            else:
                debug_message = f'Found {total_image_sources}/{total_images} images on page (including data-src)'
        
        # Save to data file
        data = load_data()
        new_entry = {
            'id': len(data) + 1,
            'url': url,
            'brand': brand,
            'imageURL': image_url,
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
            'url': url,
            'id': new_entry['id'],
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