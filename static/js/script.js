// Tab functionality
function openTab(evt, tabName) {
    console.log('Opening tab:', tabName); // Debug log
    
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
    const targetTab = document.getElementById(tabName);
    if (targetTab) {
        targetTab.classList.add('active');
        console.log('Tab found and activated:', tabName); // Debug log
    } else {
        console.error('Tab not found:', tabName); // Debug log
    }
    
    evt.currentTarget.classList.add('active');
    
    // Load data when switching to data tab
    if (tabName === 'data-tab') {
        loadStoredData();
    }
}

// Scraping functionality
async function scrapeUrls() {
    const urlInputs = [
        document.getElementById('url-input-1'),
        document.getElementById('url-input-2'),
        document.getElementById('url-input-3'),
        document.getElementById('url-input-4'),
        document.getElementById('url-input-5'),
        document.getElementById('url-input-6'),
        document.getElementById('url-input-7'),
        document.getElementById('url-input-8'),
        document.getElementById('url-input-9'),
        document.getElementById('url-input-10')
    ];
    
    const scrapeBtn = document.getElementById('scrape-btn');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const error = document.getElementById('error');
    
    // Collect all non-empty URLs
    const urls = urlInputs.map(input => input.value.trim()).filter(url => url);
    
    if (urls.length === 0) {
        showError('Please enter at least one URL');
        return;
    }
    
    // Show loading state
    loading.classList.remove('hidden');
    results.classList.add('hidden');
    error.classList.add('hidden');
    scrapeBtn.disabled = true;
    scrapeBtn.textContent = `Scraping ${urls.length} URL${urls.length > 1 ? 's' : ''}...`;
    
    const resultsContainer = document.getElementById('results-container');
    resultsContainer.innerHTML = '';
    
    let successCount = 0;
    let errorCount = 0;
    const allResults = [];
    
    try {
        // Process URLs sequentially to avoid overwhelming the server
        for (let i = 0; i < urls.length; i++) {
            const url = urls[i];
            const urlNumber = i + 1;
            
            try {
                // Update loading message
                scrapeBtn.textContent = `Scraping URL ${urlNumber}/${urls.length}...`;
                
                const response = await fetch('/scrape', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ url: url })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    successCount++;
                    allResults.push({ ...data, urlNumber, status: 'success' });
                    addResultCard(data, urlNumber, 'success');
                } else {
                    errorCount++;
                    allResults.push({ error: data.error, url, urlNumber, status: 'error' });
                    addResultCard({ error: data.error, url }, urlNumber, 'error');
                }
            } catch (err) {
                errorCount++;
                allResults.push({ error: err.message, url, urlNumber, status: 'error' });
                addResultCard({ error: err.message, url }, urlNumber, 'error');
            }
            
            // Small delay between requests to be respectful to servers
            if (i < urls.length - 1) {
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
        }
        
        // Show results and summary
        showBatchResults(successCount, errorCount, urls.length);
        
    } catch (err) {
        showError('Batch scraping error: ' + err.message);
    } finally {
        // Reset button state
        loading.classList.add('hidden');
        scrapeBtn.disabled = false;
        scrapeBtn.textContent = 'Scrape All URLs';
    }
}

function showResult(data) {
    hideLoading();
    hideError();
    
    document.getElementById('result-url').textContent = data.url;
    document.getElementById('result-brand').textContent = data.brand;
    document.getElementById('result-name').textContent = data.name || 'Not found';
    document.getElementById('result-barcode-id').textContent = data.barcodeId || 'Not found';
    document.getElementById('result-image').textContent = data.imageUrl;
    document.getElementById('result-pet-type').textContent = data.petType;
    document.getElementById('result-food-type').textContent = data.texture;
    document.getElementById('result-life-stage').textContent = data.lifeStage;
    document.getElementById('result-ingredients').textContent = Array.isArray(data.ingredients) ? data.ingredients.join(', ') : (data.ingredients || 'Not found');
    document.getElementById('result-guaranteed-analysis').textContent = data.guaranteedAnalysis || 'Not found';
    
    // Handle nutritional info (nested object)
    let nutritionalInfoText = 'Not found';
    if (data.nutritionalInfo && data.nutritionalInfo.calories) {
        nutritionalInfoText = `Calories: ${data.nutritionalInfo.calories}`;
    }
    document.getElementById('result-nutritional-info').textContent = nutritionalInfoText;
    
    // Show debug info if available
    if (data.debug_info) {
        document.getElementById('debug-details').textContent = data.debug_info;
        document.getElementById('debug-info').style.display = 'block';
    }
    
    document.getElementById('result').classList.remove('hidden');
}

function showError(message) {
    const result = document.getElementById('result');
    const error = document.getElementById('error');
    
    document.getElementById('error-message').textContent = message;
    
    error.classList.remove('hidden');
    result.classList.add('hidden');
}

function hideLoading() {
    const loading = document.getElementById('loading');
    if (loading) {
        loading.classList.add('hidden');
    }
}

function hideError() {
    const error = document.getElementById('error');
    if (error) {
        error.classList.add('hidden');
    }
}

// Batch scraping helper functions
function addResultCard(data, urlNumber, status) {
    const resultsContainer = document.getElementById('results-container');
    const resultCard = document.createElement('div');
    resultCard.className = 'result-card';
    
    if (status === 'success') {
        resultCard.innerHTML = `
            <div class="result-header">
                <span class="result-number">URL ${urlNumber}</span>
                <span class="result-status success">✓ Success</span>
            </div>
            <div class="result-item"><strong>URL:</strong> ${escapeHtml(data.url)}</div>
            <div class="result-item"><strong>Brand:</strong> ${escapeHtml(data.brand)}</div>
            <div class="result-item"><strong>Name:</strong> ${escapeHtml(data.name || 'Not found')}</div>
            <div class="result-item"><strong>ID:</strong> ${escapeHtml(data.barcodeId || 'Not found')}</div>
            <div class="result-item"><strong>Pet Type:</strong> ${escapeHtml(data.petType)}</div>
            <div class="result-item"><strong>Texture:</strong> ${escapeHtml(data.texture)}</div>
            <div class="result-item"><strong>Life Stage:</strong> ${escapeHtml(data.lifeStage)}</div>
            <div class="result-item"><strong>Ingredients:</strong> ${Array.isArray(data.ingredients) ? escapeHtml(data.ingredients.join(', ')) : escapeHtml(data.ingredients || 'Not found')}</div>
            <div class="result-item"><strong>Guaranteed Analysis:</strong> ${escapeHtml(data.guaranteedAnalysis || 'Not found')}</div>
            <div class="result-item"><strong>Nutritional Info:</strong> ${data.nutritionalInfo && data.nutritionalInfo.calories ? escapeHtml(`Calories: ${data.nutritionalInfo.calories}`) : 'Not found'}</div>
            <div class="result-item"><strong>Image URL:</strong> <span class="image-url">${escapeHtml(data.imageUrl || 'Not found')}</span></div>
        `;
    } else {
        resultCard.innerHTML = `
            <div class="result-header">
                <span class="result-number">URL ${urlNumber}</span>
                <span class="result-status error">✗ Error</span>
            </div>
            <div class="result-item"><strong>URL:</strong> ${escapeHtml(data.url)}</div>
            <div class="result-item"><strong>Error:</strong> ${escapeHtml(data.error || 'Unknown error')}</div>
        `;
    }
    
    resultsContainer.appendChild(resultCard);
}

function showBatchResults(successCount, errorCount, totalCount) {
    const results = document.getElementById('results');
    const batchSummary = document.getElementById('batch-summary');
    const summaryText = document.getElementById('summary-text');
    
    results.classList.remove('hidden');
    batchSummary.classList.remove('hidden');
    
    let summaryMessage = `Processed ${totalCount} URL${totalCount > 1 ? 's' : ''}`;
    if (successCount > 0) {
        summaryMessage += ` - ${successCount} successful`;
    }
    if (errorCount > 0) {
        summaryMessage += ` - ${errorCount} failed`;
    }
    
    summaryText.textContent = summaryMessage;
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
                    <div class="data-item-left">
                        <label class="checkbox-container">
                            <input type="checkbox" class="item-checkbox" data-id="${item.id}" onchange="updateSelectionCount()">
                            <span class="checkmark"></span>
                        </label>
                        <div class="data-item-brand">Brand: ${escapeHtml(item.brand)}</div>
                    </div>
                    <button class="sheets-export-btn" onclick="copyItemForSheets(${item.id})">Copy for Sheets</button>
                    <button class="delete-btn" onclick="deleteDataItem(${item.id})">Delete</button>
                </div>
                <div class="data-item-name">Name: ${escapeHtml(item.name || 'Not found')}</div>
                <div class="data-item-barcode-id">ID: ${escapeHtml(item.barcodeId || 'Not found')}</div>
                <div class="data-item-pet-type">Pet Type: ${escapeHtml(item.petType || 'unknown')}</div>
                <div class="data-item-texture">Texture: ${escapeHtml(item.texture || 'unknown')}</div>
                <div class="data-item-life-stage">Life Stage: ${escapeHtml(item.lifeStage || 'adult')}</div>
                <div class="data-item-ingredients">Ingredients: ${Array.isArray(item.ingredients) ? escapeHtml(item.ingredients.join(', ')) : escapeHtml(item.ingredients || 'Not found')}</div>
                <div class="data-item-guaranteed-analysis">Guaranteed Analysis: ${escapeHtml(item.guaranteedAnalysis || 'Not found')}</div>
                <div class="data-item-nutritional-info">Nutritional Info: ${item.nutritionalInfo && item.nutritionalInfo.calories ? escapeHtml(`Calories: ${item.nutritionalInfo.calories}`) : 'Not found'}</div>
                <div class="data-item-url">URL: ${escapeHtml(item.url)}</div>
                <div class="data-item-image">Image: <span class="image-url">${escapeHtml(item.imageUrl || 'Not found')}</span></div>
                <div class="data-item-meta">
                    <span class="data-item-timestamp">${formattedDate}</span>
                    <span class="data-item-domain">${escapeHtml(item.domain)}</span>
                </div>
            </div>
        `;
    }).join('');
    
    dataList.innerHTML = html;
    
    // Show bulk controls if there's data
    const bulkControls = document.getElementById('bulk-controls');
    if (data.length > 0) {
        bulkControls.classList.remove('hidden');
    } else {
        bulkControls.classList.add('hidden');
    }
    
    // Reset bulk selection state
    updateSelectionCount();
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
    // Clear all URL inputs
    document.getElementById('url-input-1').value = '';
    document.getElementById('url-input-2').value = '';
    document.getElementById('url-input-3').value = '';
    document.getElementById('url-input-4').value = '';
    document.getElementById('url-input-5').value = '';
    document.getElementById('url-input-6').value = '';
    document.getElementById('url-input-7').value = '';
    document.getElementById('url-input-8').value = '';
    document.getElementById('url-input-9').value = '';
    document.getElementById('url-input-10').value = '';
    
    // Hide results and error sections
    document.getElementById('results').classList.add('hidden');
    document.getElementById('error').classList.add('hidden');
    document.getElementById('loading').classList.add('hidden');
    
    // Clear results container
    document.getElementById('results-container').innerHTML = '';
    document.getElementById('batch-summary').classList.add('hidden');
    
    // Reset button text
    const scrapeBtn = document.getElementById('scrape-btn');
    scrapeBtn.textContent = 'Scrape All URLs';
    scrapeBtn.disabled = false;
}

// Export functionality
// Export for App function removed - replaced with Copy All for Sheets functionality

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

// Bulk selection functions
function toggleSelectAll() {
    const selectAllCheckbox = document.getElementById('select-all');
    const itemCheckboxes = document.querySelectorAll('.item-checkbox');
    
    itemCheckboxes.forEach(checkbox => {
        checkbox.checked = selectAllCheckbox.checked;
    });
    
    updateSelectionCount();
}

function updateSelectionCount() {
    const itemCheckboxes = document.querySelectorAll('.item-checkbox');
    const selectedCheckboxes = document.querySelectorAll('.item-checkbox:checked');
    const selectAllCheckbox = document.getElementById('select-all');
    const selectedCountSpan = document.getElementById('selected-count');
    const deleteSelectedBtn = document.getElementById('delete-selected-btn');
    
    const selectedCount = selectedCheckboxes.length;
    const totalCount = itemCheckboxes.length;
    
    // Update selected count display
    selectedCountSpan.textContent = `${selectedCount} selected`;
    
    // Update "Select All" checkbox state
    if (selectedCount === 0) {
        selectAllCheckbox.indeterminate = false;
        selectAllCheckbox.checked = false;
    } else if (selectedCount === totalCount) {
        selectAllCheckbox.indeterminate = false;
        selectAllCheckbox.checked = true;
    } else {
        selectAllCheckbox.indeterminate = true;
    }
    
    // Enable/disable delete button
    deleteSelectedBtn.disabled = selectedCount === 0;
}

async function deleteSelected() {
    const selectedCheckboxes = document.querySelectorAll('.item-checkbox:checked');
    const selectedIds = Array.from(selectedCheckboxes).map(cb => parseInt(cb.dataset.id));
    
    if (selectedIds.length === 0) {
        alert('No items selected for deletion.');
        return;
    }
    
    const confirmMessage = `Are you sure you want to delete ${selectedIds.length} selected item${selectedIds.length > 1 ? 's' : ''}? This action cannot be undone.`;
    
    if (!confirm(confirmMessage)) {
        return;
    }
    
    try {
        // Delete each selected item
        const deletePromises = selectedIds.map(id => 
            fetch(`/data/${id}`, { method: 'DELETE' })
        );
        
        await Promise.all(deletePromises);
        
        // Reload the data to show updated list
        await loadStoredData();
        
        alert(`Successfully deleted ${selectedIds.length} item${selectedIds.length > 1 ? 's' : ''}.`);
        
    } catch (error) {
        alert('Error deleting selected items: ' + error.message);
    }
}

// Simple Copy for Google Sheets Functions

async function copyHeadersForSheets() {
    const headers = [
        'productKey',
        'brand', 
        'name',
        'ID',
        'petType',
        'texture',
        'lifeStage',
        'ingredients',
        'guaranteedAnalysis',
        'calories',
        'imageUrl'
    ];
    
    // Tab-separated format for Google Sheets
    const headerText = headers.join('\t');
    
    try {
        await navigator.clipboard.writeText(headerText);
        showCopyStatus('✅ Headers copied to clipboard! Paste into row 1 of your Google Sheet.', 'success');
    } catch (error) {
        showCopyStatus('❌ Failed to copy headers. Please try again.', 'error');
    }
}

async function copyAllDataForSheets() {
    try {
        showCopyStatus('Loading data...', 'info');
        
        const response = await fetch('/data');
        const data = await response.json();
        
        if (!data || data.length === 0) {
            showCopyStatus('No data to copy. Please scrape some products first.', 'info');
            return;
        }
        
        const formattedData = formatDataForSheets(data);
        
        await navigator.clipboard.writeText(formattedData);
        showCopyStatus(`✅ ${data.length} products copied to clipboard! Paste into your Google Sheet starting from row 2.`, 'success');
        
    } catch (error) {
        showCopyStatus('❌ Failed to copy data. Please try again.', 'error');
    }
}

async function copyAllForSheetsFromStoredData() {
    try {
        const response = await fetch('/data');
        const data = await response.json();
        
        if (!data || data.length === 0) {
            alert('No data to copy. Please scrape some products first.');
            return;
        }
        
        const formattedData = formatDataForSheets(data);
        
        await navigator.clipboard.writeText(formattedData);
        alert(`✅ ${data.length} products copied to clipboard!\n\nPaste into your Google Sheet starting from row 2.\nEach product will appear in its own row with the correct column format.`);
        
    } catch (error) {
        alert('❌ Failed to copy data. Please try again.');
    }
}

async function copyItemForSheets(itemId) {
    try {
        const response = await fetch('/data');
        const data = await response.json();
        
        const item = data.find(item => item.id === itemId);
        if (!item) {
            alert('❌ Item not found');
            return;
        }
        
        const formattedData = formatDataForSheets([item]);
        
        await navigator.clipboard.writeText(formattedData);
        alert('✅ Product copied to clipboard! Paste into your Google Sheet.');
        
    } catch (error) {
        alert('❌ Failed to copy item. Please try again.');
    }
}

async function showPreview() {
    try {
        const response = await fetch('/data');
        const data = await response.json();
        
        if (!data || data.length === 0) {
            showCopyStatus('No data to preview. Please scrape some products first.', 'info');
            return;
        }
        
        // Show preview of first 3 items
        const previewData = data.slice(0, 3);
        const formattedData = formatDataForSheets(previewData);
        
        document.getElementById('preview-content').textContent = formattedData;
        document.getElementById('preview-area').style.display = 'block';
        
        showCopyStatus(`Preview showing first ${previewData.length} of ${data.length} products`, 'info');
        
    } catch (error) {
        showCopyStatus('❌ Failed to load preview.', 'error');
    }
}

async function copyPreviewToClipboard() {
    const previewContent = document.getElementById('preview-content').textContent;
    
    try {
        await navigator.clipboard.writeText(previewContent);
        showCopyStatus('✅ Preview copied to clipboard!', 'success');
    } catch (error) {
        showCopyStatus('❌ Failed to copy preview.', 'error');
    }
}

function formatDataForSheets(data) {
    return data.map(item => {
        // Generate productKey (brand-id format)
        const brand = (item.brand || '').toLowerCase().replace(/\s+/g, '-').replace(/&/g, 'and');
        const barcode_id = item.barcodeId || '';
        let product_key = '';
        
        if (barcode_id && barcode_id !== 'Not found') {
            if (barcode_id.includes('-')) {
                const suffix = barcode_id.split('-').pop();
                product_key = `${brand}-${suffix}`;
            } else {
                product_key = `${brand}-${barcode_id}`;
            }
        } else {
            product_key = `${brand}-${(item.name || '').length}`;
        }
        
        // Handle ingredients - convert array to comma-separated string
        let ingredients = '';
        if (Array.isArray(item.ingredients)) {
            ingredients = item.ingredients.join(', ');
        } else if (item.ingredients) {
            ingredients = item.ingredients.toString();
        }
        
        // Handle nutritional info - extract calories
        let calories = '';
        if (item.nutritionalInfo && typeof item.nutritionalInfo === 'object' && item.nutritionalInfo.calories) {
            calories = item.nutritionalInfo.calories;
        } else if (item.nutritionalInfo && typeof item.nutritionalInfo === 'string') {
            calories = item.nutritionalInfo;
        }
        
        // Create row data in exact column order (tab-separated)
        const rowData = [
            product_key || '',                                    // A: productKey
            item.brand || '',                                     // B: brand
            item.name || '',                                      // C: name
            item.barcodeId || '',                                 // D: ID
            item.petType || '',                                   // E: petType
            item.texture || '',                                   // F: texture
            item.lifeStage || '',                                 // G: lifeStage
            ingredients,                                          // H: ingredients
            item.guaranteedAnalysis || '',                        // I: guaranteedAnalysis
            calories,                                             // J: calories
            item.imageUrl || ''                                   // K: imageUrl
        ];
        
        return rowData.join('\t');
    }).join('\n');
}

function showCopyStatus(message, type) {
    const statusDiv = document.getElementById('copy-status');
    statusDiv.textContent = message;
    statusDiv.className = `copy-status ${type}`;
} 