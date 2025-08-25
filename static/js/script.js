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
    hideLoading();
    hideError();
    
    document.getElementById('result-url').textContent = data.url;
    document.getElementById('result-brand').textContent = data.brand;
    document.getElementById('result-name').textContent = data.name || 'Not found';
    document.getElementById('result-image').textContent = data.imageUrl;
    document.getElementById('result-pet-type').textContent = data.petType;
    document.getElementById('result-food-type').textContent = data.foodType;
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
                    <button class="delete-btn" onclick="deleteDataItem(${item.id})">Delete</button>
                </div>
                <div class="data-item-name">Name: ${escapeHtml(item.name || 'Not found')}</div>
                <div class="data-item-pet-type">Pet Type: ${escapeHtml(item.petType || 'unknown')}</div>
                <div class="data-item-food-type">Food Type: ${escapeHtml(item.foodType || 'unknown')}</div>
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
    document.getElementById('url-input').value = '';
    document.getElementById('result').classList.add('hidden');
    document.getElementById('error').classList.add('hidden');
    document.getElementById('loading').classList.add('hidden');
    
    // Clear all result fields
    document.getElementById('result-url').textContent = '';
    document.getElementById('result-brand').textContent = '';
    document.getElementById('result-name').textContent = '';
    document.getElementById('result-image').textContent = '';
    document.getElementById('result-pet-type').textContent = '';
    document.getElementById('result-food-type').textContent = '';
    document.getElementById('result-life-stage').textContent = '';
    document.getElementById('result-ingredients').textContent = '';
    document.getElementById('result-guaranteed-analysis').textContent = '';
    document.getElementById('result-nutritional-info').textContent = '';
    
    // Hide debug info
    document.getElementById('debug-info').style.display = 'none';
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
        
        // Format data for app use - brand, petType, foodType, lifeStage, imageUrl, and ingredients fields
        // UPDATED: Fixed food type formatting to use individual quotes (v2)
        const formattedData = data.map((item, index) => {
            const isLast = index === data.length - 1;
            const comma = isLast ? '' : ',';
            
            // Format foodType with individual quotes for each type
            const foodType = item.foodType || 'unknown';
            let formattedFoodType;
            
            if (foodType.includes(',')) {
                // Multiple food types - split and format each with quotes
                const types = foodType.split(',').map(type => `'${type.trim()}'`);
                formattedFoodType = types.join(', ');
            } else {
                // Single food type
                formattedFoodType = `'${foodType}'`;
            }
            
            // Format nutritional info for export
            let nutritionalInfoExport = 'Not found';
            if (item.nutritionalInfo && item.nutritionalInfo.calories) {
                nutritionalInfoExport = `{ calories: '${item.nutritionalInfo.calories}' }`;
            }
            
            // Format ingredients - handle both array and string formats
            let ingredientsExport;
            if (Array.isArray(item.ingredients)) {
                // Format as array with individual quotes
                const ingredientsList = item.ingredients.map(ingredient => `'${ingredient.replace(/'/g, "\\'")}'`).join(', ');
                ingredientsExport = `[${ingredientsList}]`;
            } else {
                // Fallback for string format
                ingredientsExport = `'${(item.ingredients || 'Not found').replace(/'/g, "\\'").replace(/\n/g, ' ')}'`;
            }
            
            return `{\n  brand: '${item.brand}',\n  name: '${(item.name || 'Not found').replace(/'/g, "\\'")}',\n  petType: '${item.petType || 'unknown'}',\n  foodType: ${formattedFoodType},\n  lifeStage: '${item.lifeStage || 'adult'}',\n  imageUrl: '${item.imageUrl}',\n  ingredients: ${ingredientsExport},\n  guaranteedAnalysis: '${(item.guaranteedAnalysis || 'Not found').replace(/'/g, "\\'").replace(/\n/g, ' ')}',\n  nutritionalInfo: ${nutritionalInfoExport}\n}${comma}`;
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