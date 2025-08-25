# 🐾 Pet Food Brand Scraper

A web-based application that scrapes brand information from pet food product URLs. Features a clean, modern interface with data storage and management capabilities.

## Features

- **Brand Detection**: Advanced extraction from meta tags, JSON-LD data, CSS classes, page content, and URLs
- **Pet Type Detection**: Identifies whether products are for cats or dogs based on URL and page content
- **Food Type Classification**: Categorizes food as wet, dry, raw, treats, toppers, or pate
- **Life Stage Detection**: Determines if food is for kitten/puppy, adult, senior, or all life stages
- **Ingredient Extraction**: Comprehensively extracts product ingredients, including from dropdowns and collapsed content
- **Image URL Scraping**: Finds and extracts product image URLs, prioritizing high-quality images
- **Bulk Data Management**: Select and delete multiple stored entries at once
- **Export for App Integration**: Copy data in a formatted structure for easy integration
- **Clear Search**: Reset the scraper interface quickly
- **Debug Information**: View extraction details and troubleshooting info
- **Responsive Design**: Works on desktop and mobile devices

### Ingredient Extraction
The scraper uses advanced techniques to find ingredients even when hidden behind dropdowns or accordion interfaces:

**Detection Strategy:**
- Searches for explicit "Ingredients" sections and headings
- Looks inside collapsed dropdowns, accordions, and tabs
- Extracts from JSON-LD structured data
- Analyzes data attributes and element classes
- Uses pattern matching to identify ingredient lists
- Validates content using ingredient-specific keywords

**Dropdown/Accordion Support:**
- Automatically finds content in collapsed elements
- Searches common dropdown classes (`accordion`, `collapse`, `dropdown`, `expandable`, `toggle`, `tab-content`, `panel`)
- No need to manually click dropdowns - content is extracted directly from the HTML

**Ingredient Validation:**
- Identifies likely ingredient lists using food-specific keywords
- Filters out non-ingredient content
- Handles various formats (comma-separated, bullet lists, paragraphs)
- Cleans and formats the final ingredient text

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

## Usage

1. **Scrape Data**: 
   - Enter a pet food product URL or direct image URL
   - Click "Scrape Brand" 
   - View extracted brand, pet type, food type, life stage, and image URL
   - Use "Clear" to reset and try another URL

2. **View Stored Data**: 
   - Switch to "Stored Data" tab
   - See all previously scraped products with timestamps
   - Select multiple items for bulk deletion
   - Each entry shows brand, pet type, food type, life stage, and image URL

3. **Export for App**: 
   - Click "Export for App" to get formatted data
   - Copy the generated JavaScript object format
   - Integrate directly into your application

**Example Export Format:**
```javascript
{
  brand: 'Purina Friskies',
  petType: 'cat',
  foodType: 'wet',
  lifeStage: 'adult',
  imageUrl: 'https://example.com/product-image.jpg',
  ingredients: 'Chicken, chicken broth, liver, meat by-products, turkey, vitamins, minerals'
}

{
  brand: 'Blue Buffalo',
  petType: 'dog', 
  foodType: 'dry',
  lifeStage: 'puppy',
  imageUrl: 'https://example.com/another-image.jpg',
  ingredients: 'Deboned chicken, chicken meal, brown rice, oatmeal, sweet potatoes, fish meal'
}
```

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

### Life Stage Detection
The scraper automatically determines the target life stage for pet food products:

**Detection Strategy:**
- Analyzes URL, page title, meta descriptions, Open Graph data, headings, main content, and page body
- Comprehensive search through entire page content to catch "all life stages" declarations
- Searches for specific life stage keywords throughout the page

**Life Stage Categories:**
- **For Cats**: kitten, adult, senior, all
- **For Dogs**: puppy, adult, senior, all

**Keywords Detected:**
- **Kitten/Puppy**: "kitten", "kittens", "puppy", "puppies"
- **Senior**: "senior", "seniors", "mature", "aged", "7+", "8+", "9+", "10+", "11+", "12+"
- **All Life Stages**: "all life stages", "all ages", "all stages", "life stages", "any age", "every stage", "AAFCO Cat Food Nutrient Profiles for All Life Stages", "formulated for all life stages", "complete and balanced for all life stages"
- **Default**: "adult" (when no specific life stage is mentioned)

### Pet Type Detection
The scraper automatically determines whether products are for cats or dogs:

**Detection Strategy:**
- Comprehensive search through URL, page title, meta descriptions, Open Graph data, headings, breadcrumbs, navigation, main content areas, and page body
- Enhanced keyword matching with expanded vocabulary
- Multiple fallback strategies to ensure accurate detection

**Keywords Detected:**
- **Cat**: "cat", "cats", "feline", "felines", "kitten", "kittens", "kitty", "kitties"
- **Dog**: "dog", "dogs", "canine", "canines", "puppy", "puppies", "pup", "pups"
- **Fallback**: "unknown" (only when no pet type keywords are found anywhere on the page)

### Brand Exceptions
- **Purina Friskies**: Automatically formats "Friskies" products as "Purina Friskies"

### Troubleshooting

### "Brand not found"
- **URL-based extraction**: The scraper can extract brand names directly from URLs as a fallback
- **Enhanced image detection**: Multiple strategies ensure higher success rates
- **Direct image URLs**: The scraper now supports direct image URLs (.jpg, .png, etc.)

### "Image not found" 
- **Enhanced detection**: The scraper now uses multiple image detection strategies
- **Direct image support**: Can handle direct image URLs (e.g., .jpg, .png, .pdf files)
- **Content compression**: Fixed issue with Brotli compression causing parsing failures
- **Purina images**: For Purina.com, the scraper returns high-quality social share images to ensure reliability

### Common Issues
- **Port conflicts**: Change the port in `app.py` if 8000 is already in use
- **Dependencies**: Make sure you're using the virtual environment (`source venv/bin/activate`)
- **Empty results**: Some websites may block automated requests - try different URLs

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