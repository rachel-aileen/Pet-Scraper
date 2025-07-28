from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import datetime
import re
from urllib.parse import urlparse

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
        lambda: soup.find(text=re.compile(r'brand:', re.I)),
        
        # Look in title or headings
        lambda: extract_from_title(soup),
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
                
                if brand and brand.strip():
                    return brand.strip()
        except Exception:
            continue
    
    return "Brand not found"

def extract_image_url(soup, url):
    """Extract product image URL from the webpage"""
    image_url = None
    
    # Common image extraction strategies
    strategies = [
        # Look for Open Graph image
        lambda: soup.find('meta', {'property': 'og:image'}),
        lambda: soup.find('meta', {'property': 'product:image'}),
        lambda: soup.find('meta', {'name': 'twitter:image'}),
        
        # Look for structured data (JSON-LD)
        lambda: extract_from_json_ld(soup, 'image'),
        
        # Look for common product image classes
        lambda: soup.find('img', class_=re.compile(r'product.*image|main.*image|hero.*image', re.I)),
        lambda: soup.find('img', {'itemprop': 'image'}),
        
        # Look for images in product containers
        lambda: soup.select('.product img, .product-image img, .main-image img, .hero-image img'),
        
        # Look for the largest image (likely product image)
        lambda: find_largest_image(soup),
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
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        from urllib.parse import urljoin
                        image_url = urljoin(url, image_url)
                    elif not image_url.startswith(('http://', 'https://')):
                        from urllib.parse import urljoin
                        image_url = urljoin(url, image_url)
                    
                    return image_url.strip()
        except Exception:
            continue
    
    return "Image not found"

def find_largest_image(soup):
    """Find the largest image on the page (likely a product image)"""
    images = soup.find_all('img', src=True)
    largest_img = None
    max_size = 0
    
    for img in images:
        try:
            # Skip small images, icons, logos
            src = img.get('src', '')
            if any(keyword in src.lower() for keyword in ['icon', 'logo', 'thumb', 'avatar', 'sprite']):
                continue
            
            # Try to get image dimensions
            width = img.get('width', 0)
            height = img.get('height', 0)
            
            if width and height:
                try:
                    size = int(width) * int(height)
                    if size > max_size:
                        max_size = size
                        largest_img = img
                except ValueError:
                    continue
        except Exception:
            continue
    
    return largest_img

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
        
        # Set up headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Make request
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract brand and image
        brand = extract_brand(soup, url)
        image_url = extract_image_url(soup, url)
        
        # Save to data file
        data = load_data()
        new_entry = {
            'id': len(data) + 1,
            'url': url,
            'brand': brand,
            'imageURL': image_url,
            'timestamp': datetime.now().isoformat(),
            'domain': parsed.netloc
        }
        data.append(new_entry)
        save_data(data)
        
        return jsonify({
            'success': True,
            'brand': brand,
            'imageURL': image_url,
            'url': url,
            'id': new_entry['id']
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