// Tab functionality
function openTab(evt, tabName) {
    // Hide all tab contents
    const tabContents = document.getElementsByClassName('tab-content');
    for (let i = 0; i < tabContents.length; i++) {
        tabContents[i].classList.remove('active');
    }
    
    // Remove active class from all tab buttons
    const tabButtons = document.getElementsByClassName('tab-button');
    for (let i = 0; i < tabButtons.length; i++) {
        tabButtons[i].classList.remove('active');
    }
    
    // Show the selected tab and mark button as active
    document.getElementById(tabName).classList.add('active');
    evt.currentTarget.classList.add('active');
    
    // Load data when switching to data tab
    if (tabName === 'data-tab') {
        loadStoredData();
    }
}

// Scraping functionality
async function scrapeUrl() {
    const urlInput = document.getElementById('url-input');
    const scrapeBtn = document.getElementById('scrape-btn');
    const loading = document.getElementById('loading');
    const result = document.getElementById('result');
    const error = document.getElementById('error');
    
    const url = urlInput.value.trim();
    
    if (!url) {
        showError('Please enter a URL');
        return;
    }
    
    // Show loading state
    loading.classList.remove('hidden');
    result.classList.add('hidden');
    error.classList.add('hidden');
    scrapeBtn.disabled = true;
    scrapeBtn.textContent = 'Scraping...';
    
    try {
        const response = await fetch('/scrape', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showResult(data);
        } else {
            showError(data.error || 'Unknown error occurred');
        }
    } catch (err) {
        showError('Network error: ' + err.message);
    } finally {
        // Reset button state
        loading.classList.add('hidden');
        scrapeBtn.disabled = false;
        scrapeBtn.textContent = 'Scrape Brand';
    }
}

function showResult(data) {
    const result = document.getElementById('result');
    const error = document.getElementById('error');
    const debugInfo = document.getElementById('debug-info');
    
    document.getElementById('result-url').textContent = data.url;
    document.getElementById('result-brand').textContent = data.brand;
    document.getElementById('result-image').textContent = data.imageURL;
    
    // Show debug info if brand or image not found
    if (data.brand === 'Brand not found' || data.imageURL === 'Image not found') {
        let debugText = [];
        if (data.brand === 'Brand not found') {
            debugText.push('💡 Tip: Try a different product page or check if the brand name is visible in the URL');
        }
        if (data.imageURL === 'Image not found') {
            debugText.push('🖼️ Tip: Some sites load images with JavaScript - try a direct product page URL');
        }
        document.getElementById('debug-details').textContent = debugText.join(' | ');
        debugInfo.style.display = 'block';
    } else {
        debugInfo.style.display = 'none';
    }
    
    result.classList.remove('hidden');
    error.classList.add('hidden');
}

function showError(message) {
    const result = document.getElementById('result');
    const error = document.getElementById('error');
    
    document.getElementById('error-message').textContent = message;
    
    error.classList.remove('hidden');
    result.classList.add('hidden');
}

// Data management functionality
async function loadStoredData() {
    const dataLoading = document.getElementById('data-loading');
    const dataList = document.getElementById('data-list');
    const dataCount = document.getElementById('data-count');
    
    dataLoading.classList.remove('hidden');
    
    try {
        const response = await fetch('/data');
        const data = await response.json();
        
        displayData(data);
        dataCount.textContent = `${data.length} item${data.length !== 1 ? 's' : ''}`;
    } catch (err) {
        dataList.innerHTML = '<p class="no-data">Error loading data: ' + err.message + '</p>';
        dataCount.textContent = '0 items';
    } finally {
        dataLoading.classList.add('hidden');
    }
}

function displayData(data) {
    const dataList = document.getElementById('data-list');
    
    if (data.length === 0) {
        dataList.innerHTML = '<p class="no-data">No data available. Start scraping some URLs!</p>';
        return;
    }
    
    // Sort data by timestamp (newest first)
    data.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    const html = data.map(item => {
        const date = new Date(item.timestamp);
        const formattedDate = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        
        return `
            <div class="data-item">
                <div class="data-item-header">
                    <div class="data-item-brand">Brand: ${escapeHtml(item.brand)}</div>
                    <button class="delete-btn" onclick="deleteDataItem(${item.id})">Delete</button>
                </div>
                <div class="data-item-url">URL: ${escapeHtml(item.url)}</div>
                <div class="data-item-image">Image: <span class="image-url">${escapeHtml(item.imageURL || 'Not found')}</span></div>
                <div class="data-item-meta">
                    <span class="data-item-timestamp">${formattedDate}</span>
                    <span class="data-item-domain">${escapeHtml(item.domain)}</span>
                </div>
            </div>
        `;
    }).join('');
    
    dataList.innerHTML = html;
}

async function deleteDataItem(itemId) {
    if (!confirm('Are you sure you want to delete this item?')) {
        return;
    }
    
    try {
        const response = await fetch(`/data/${itemId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            // Reload data to refresh the list
            loadStoredData();
        } else {
            alert('Error deleting item');
        }
    } catch (err) {
        alert('Network error: ' + err.message);
    }
}

// Utility function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Clear search functionality
function clearSearch() {
    const urlInput = document.getElementById('url-input');
    const result = document.getElementById('result');
    const error = document.getElementById('error');
    const loading = document.getElementById('loading');
    const debugInfo = document.getElementById('debug-info');
    
    // Clear input field
    urlInput.value = '';
    
    // Hide all result containers
    result.classList.add('hidden');
    error.classList.add('hidden');
    loading.classList.add('hidden');
    debugInfo.style.display = 'none';
    
    // Focus back on input for better UX
    urlInput.focus();
}

// Export functionality
async function exportForApp() {
    try {
        const response = await fetch('/data');
        const data = await response.json();
        
        if (data.length === 0) {
            alert('No data to export. Please scrape some URLs first.');
            return;
        }
        
        // Format data for app use - brand and imageURL fields
        const formattedData = data.map((item, index) => {
            const isLast = index === data.length - 1;
            const comma = isLast ? '' : ',';
            return `{\n  brand: '${item.brand}',\n  imageURL: '${item.imageURL}',\n}${comma}`;
        }).join('\n\n');
        
        // Show the formatted data in modal
        document.getElementById('export-data').textContent = formattedData;
        document.getElementById('export-modal').classList.remove('hidden');
        
    } catch (err) {
        alert('Error loading data for export: ' + err.message);
    }
}

function closeExportModal() {
    document.getElementById('export-modal').classList.add('hidden');
}

async function copyToClipboard() {
    const exportData = document.getElementById('export-data');
    const copyBtn = document.querySelector('.copy-btn');
    
    try {
        await navigator.clipboard.writeText(exportData.textContent);
        
        // Visual feedback
        const originalText = copyBtn.textContent;
        copyBtn.textContent = 'Copied!';
        copyBtn.classList.add('copied');
        
        setTimeout(() => {
            copyBtn.textContent = originalText;
            copyBtn.classList.remove('copied');
        }, 2000);
        
    } catch (err) {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = exportData.textContent;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        
        alert('Data copied to clipboard!');
    }
}

// Close modal when clicking outside
document.addEventListener('click', function(e) {
    const modal = document.getElementById('export-modal');
    if (e.target === modal) {
        closeExportModal();
    }
});

// Enter key support for URL input
document.addEventListener('DOMContentLoaded', function() {
    const urlInput = document.getElementById('url-input');
    
    urlInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            scrapeUrl();
        }
    });
    
    // Load data on page load
    loadStoredData();
}); 