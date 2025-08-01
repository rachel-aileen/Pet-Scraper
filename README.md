# 🐾 Pet Food Brand Scraper

A web-based application that scrapes brand information from pet food product URLs. Features a clean, modern interface with data storage and management capabilities.

## Features

- **URL Scraping**: Enter any pet food product URL OR direct image URL to extract brand and image information
- **Smart Brand Detection**: Uses multiple strategies to find brand names including:
  - Meta tags (product:brand, brand, itemprop)
  - JSON-LD structured data
  - CSS class patterns
  - Common pet food brand recognition
  - **URL-based extraction** - extracts brand names directly from URLs as fallback
  - **Brand exceptions** - automatically formats "Friskies" as "Purina Friskies"
- **Pet Type Detection**: Automatically determines whether products are for cats or dogs based on:
  - URL analysis (keywords like 'cat', 'dog', 'canine', 'feline')
  - Page title and meta descriptions
  - Open Graph metadata
  - Content headings analysis
- **Food Type Classification**: Automatically classifies food as wet, dry, raw, or treats based on:
  - URL keywords ('wet', 'canned', 'dry', 'kibble', 'raw', 'frozen', 'treat', 'snack')
  - Page content analysis
  - Product descriptions and titles
- **Smart Image Detection**: Finds the first reasonable image using:
  - **Direct image URL support** - handles .jpg, .png, .gif, .webp, .pdf URLs directly
  - Open Graph and Twitter meta tags (highest priority)
  - Structured data (JSON-LD)
  - **First reasonable image on page** - skips only obvious logos/icons
  - Automatic filtering of tiny images and common icon patterns
  - Converts relative URLs to absolute URLs automatically
- **Data Storage**: All scraped data is automatically saved with timestamps
- **App Export**: Format and export data in app-ready JavaScript object format
- **Data Management**: View, browse, and delete stored data entries
- **Responsive Design**: Works on desktop and mobile devices

## Quick Start

1. **Activate the virtual environment** (if not already active):
   ```bash
   source venv/bin/activate
   ```

2. **Run the application**:
   ```bash
   python app.py
   ```

3. **Open your browser** and navigate to:
   ```
   http://localhost:8000
   ```

## How to Use

### Scraping URLs
1. Navigate to the **Scraper** tab
2. Enter a pet food product URL OR direct image URL (.jpg, .png, .pdf, etc.) in the input field
3. Click "Scrape Brand" or press Enter
4. View the extracted brand and image information in the results
5. Use the "Clear" button to reset the search and start fresh

**Tip**: You can right-click any image → "Open image in new tab" and use that direct image URL!

### Managing Data
1. Switch to the **Stored Data** tab
2. View all previously scraped entries with timestamps and domains
3. Use the "Refresh Data" button to reload the list
4. Click "Export for App" to get formatted data for your application
5. Delete individual entries using the red "Delete" button

### Exporting Data for Apps
The "Export for App" feature formats your scraped data perfectly for use in applications:
```javascript
{
  brand: 'Viva Raw',
  petType: 'dog',
  foodType: 'raw',
  imageURL: 'https://example.com/product-image.jpg',
},

{
  brand: 'Hill\'s Science Diet',
  petType: 'cat',
  foodType: 'dry',
  imageURL: 'https://example.com/hills-product.jpg',
}
```
The export modal includes a "Copy to Clipboard" button for easy integration.

## Project Structure

```
Pet Scraper/
├── app.py                 # Flask application and scraping logic
├── requirements.txt       # Python dependencies
├── scraped_data.json     # Data storage file (created automatically)
├── templates/
│   └── index.html        # Main web interface
├── static/
│   ├── css/
│   │   └── style.css     # Application styling
│   └── js/
│       └── script.js     # Frontend functionality
└── venv/                 # Virtual environment
```

## API Endpoints

- `GET /` - Main application interface
- `POST /scrape` - Scrape URL endpoint (JSON: `{"url": "..."}`)
- `GET /data` - Retrieve all stored data
- `DELETE /data/<id>` - Delete specific data entry

## Technical Details

### Brand Extraction Strategies
The scraper uses multiple methods to find brand information:

1. **Meta Tags**: Looks for standard e-commerce meta tags
2. **Structured Data**: Parses JSON-LD for product information
3. **CSS Classes**: Searches for elements with "brand" in class names
4. **Text Patterns**: Finds text containing "brand:" labels
5. **Title Analysis**: Checks page titles for known pet food brands

### Supported Formats
- HTML pages with standard meta tags
- E-commerce sites with structured data
- Product pages with CSS-based layouts

## Troubleshooting

### Common Issues

**"Brand not found"**: This can happen when:
- The page doesn't contain standard brand markup
- The site uses JavaScript to load content dynamically
- The brand information is in images or non-text elements
- **Note**: The scraper now extracts brands from URLs as a fallback - if the brand name appears in the URL (like "instinctpetfood.com" → "Instinct"), it should be detected automatically

**Network errors**: Check that:
- The URL is accessible
- Your internet connection is working
- The target site isn't blocking automated requests

**"Image not found"**: The scraper now includes multiple advanced detection methods:
- Open Graph meta tags (`og:image`)
- CSS background images
- JavaScript and data attributes
- Aggressive pattern matching
- **Fixed**: Content compression issues that previously prevented image detection

**403 Forbidden errors**: Some sites block automated requests:
- The scraper tries multiple user agents and retry attempts
- Try different product pages on the same site
- Some e-commerce sites have strong anti-bot protection
- Government, educational, and smaller business sites often work better

### Improving Results
For better brand detection, try:
- Using the main product page URL
- Checking if the site has structured data
- Looking for alternative product pages on the same site

### Sites That Work Well
The scraper works best with:
- Pet specialty stores and smaller retailers
- Sites with standard e-commerce structure
- Pages with clear product information
- Sites that don't require JavaScript for content loading

### Sites That May Be Challenging
- Large e-commerce platforms with anti-bot protection
- Sites requiring user accounts or authentication
- JavaScript-heavy single-page applications
- Sites with aggressive rate limiting

## Dependencies

- **Flask 3.0.0**: Web framework
- **requests 2.31.0**: HTTP requests
- **beautifulsoup4 4.12.2**: HTML parsing
- **gunicorn 21.2.0**: Production server (optional)

## Development

To modify the scraper:

1. **Brand extraction logic**: Edit the `extract_brand()` function in `app.py`
2. **UI changes**: Modify templates and static files
3. **New features**: Add endpoints to `app.py` and corresponding frontend code

## License

This project is open source and available under the MIT License. 