// Spotlight functionality
const searchInput = document.getElementById('searchInput');
const resultsContainer = document.getElementById('resultsContainer');
const spotlightContainer = document.getElementById('spotlightContainer');

searchInput.addEventListener('input', (e) => {
    if (e.target.value.length > 0) {
        resultsContainer.classList.add('show');
        spotlightContainer.classList.add('active');
    } else {
        resultsContainer.classList.remove('show');
        spotlightContainer.classList.remove('active');
    }
});

// Click outside to close
document.addEventListener('click', (e) => {
    if (!spotlightContainer.contains(e.target)) {
        searchInput.value = '';
        resultsContainer.classList.remove('show');
        spotlightContainer.classList.remove('active');
    }
});

// Result item clicks
document.querySelectorAll('.result-item').forEach(item => {
    item.addEventListener('click', (e) => {
        const action = e.currentTarget.getAttribute('data-action');
        handleAction(action);
        searchInput.value = '';
        resultsContainer.classList.remove('show');
        spotlightContainer.classList.remove('active');
    });
});

function handleAction(action) {
    switch(action) {
        case 'ai':
            console.log('Opening AI assistant...');
            break;
        case 'widget':
            createWidget();
            break;
        case 'corpus':
            console.log('Opening corpus search...');
            break;
        case 'scry':
            console.log('Opening Scry audit platform...');
            break;
    }
}

// Widget system
let widgetCount = 0;
let draggedElement = null;
let offset = { x: 0, y: 0 };

// Global state for documents
let recentDocuments = [];
let currentPage = 0;
const documentsPerPage = 5;

async function fetchRecentDocuments() {
    try {
        console.log('Fetching recent documents via local proxy...');
        // Use our local proxy instead of calling iManage directly
        const response = await fetch('/api/imanage/customers/145/recent-documents', {
            method: 'GET'
        });
        
        console.log('Proxy Response status:', response.status);
        
        if (response.ok) {
            const data = await response.json();
            console.log('Proxy Response data:', data);
            recentDocuments = data.data.results || [];
            console.log('Processed documents:', recentDocuments.length);
            return true;
        } else {
            const errorData = await response.text();
            console.error('Failed to fetch documents:', response.status, response.statusText, errorData);
            return false;
        }
    } catch (error) {
        console.error('Error fetching recent documents:', error);
        return false;
    }
}

const widgetTemplates = [
    { title: 'Sovereign AI Status', content: 'LM Studio: Running\nChromaDB: Active\nLocal Models: 3 loaded' },
    { title: 'Market Watch', content: 'BTC: $45,230 (+2.1%)\nETH: $2,890 (-0.8%)\nXMR: $158 (+1.2%)' },
    { title: 'Quick Notes', content: 'Building the sovereign path...\n\nâ€¢ Memoir progress\nâ€¢ PV relocation planning\nâ€¢ AI corpus indexing' },
    { title: 'Weather - PV', content: 'Puerto Vallarta\n28Â°C â€¢ Partly cloudy\nHumidity: 75%\nWind: 12 km/h SW' },
    { title: 'System Status', content: 'CPU: 23%\nMemory: 8.2/16 GB\nStorage: 1.2TB free\nNetwork: Connected' },
    { 
        title: 'Recent Documents', 
        content: 'documents',
        type: 'documents'
    }
];

function generateDocumentsList() {
    // Return loading state initially
    return `
        <div class="documents-loading">
            <div style="text-align: center; padding: 20px; color: #666;">
                Loading recent documents...
            </div>
        </div>
    `;
}

function updateDocumentsWidget(widget) {
    const contentDiv = widget.querySelector('.widget-content');
    if (!contentDiv) return;
    
    const totalPages = Math.ceil(recentDocuments.length / documentsPerPage);
    const startIndex = currentPage * documentsPerPage;
    const endIndex = Math.min(startIndex + documentsPerPage, recentDocuments.length);
    const currentDocs = recentDocuments.slice(startIndex, endIndex);
    
    function getFileIcon(extension) {
        const iconMap = {
            'pptx': 'PPT',
            'ppt': 'PPT',
            'docx': 'DOC',
            'doc': 'DOC',
            'xlsx': 'XLS',
            'xls': 'XLS',
            'pdf': 'PDF',
            'txt': 'TXT',
            'md': 'MD',
            'py': 'PY',
            'js': 'JS',
            'html': 'HTM',
            'css': 'CSS',
            'json': 'JSON'
        };
        return iconMap[extension.toLowerCase()] || 'DOC';
    }
    
    let html = '<div class="documents-container">';
    
    if (currentDocs.length === 0) {
        html += '<div style="text-align: center; padding: 20px; color: #666;">No documents found</div>';
    } else {
        html += '<ul class="document-list">';
        currentDocs.forEach(doc => {
            const activityDate = new Date(doc.activity_date);
            const formattedDate = activityDate.toLocaleDateString('en-CA', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
            
            const iconText = getFileIcon(doc.extension || doc.type || 'doc');
            const displayName = doc.name + (doc.extension ? `.${doc.extension.toLowerCase()}` : '');
            
            html += `
                <li class="document-item" onclick="openIManageDocument('${doc.id}', '${doc.name}', '${doc.extension}')">
                    <div class="document-icon ${doc.extension ? doc.extension.toLowerCase() : 'doc'}">${iconText}</div>
                    <div class="document-details">
                        <div class="document-name" title="${displayName}">${displayName}</div>
                        <div class="document-meta">
                            <span class="document-date">${formattedDate}</span>
                            <span class="document-user">${doc.author_description || doc.author}</span>
                        </div>
                    </div>
                </li>
            `;
        });
        html += '</ul>';
    }
    
    // Add pagination controls if there are multiple pages
    if (totalPages > 1) {
        html += `
            <div class="document-pagination">
                <button class="pagination-btn" onclick="changePage(-1)" ${currentPage === 0 ? 'disabled' : ''}>â€¹</button>
                <span class="pagination-info">${currentPage + 1} of ${totalPages}</span>
                <button class="pagination-btn" onclick="changePage(1)" ${currentPage === totalPages - 1 ? 'disabled' : ''}>â€º</button>
            </div>
        `;
    }
    
    html += '</div>';
    contentDiv.innerHTML = html;
}

function changePage(direction) {
    const totalPages = Math.ceil(recentDocuments.length / documentsPerPage);
    const newPage = currentPage + direction;
    
    if (newPage >= 0 && newPage < totalPages) {
        currentPage = newPage;
        // Update all document widgets
        document.querySelectorAll('.widget').forEach(widget => {
            const title = widget.querySelector('.widget-title');
            if (title && title.textContent === 'Recent Documents') {
                updateDocumentsWidget(widget);
            }
        });
    }
}

function createWidget(template = null) {
    widgetCount++;
    const widget = document.createElement('div');
    widget.className = 'widget';
    widget.style.left = Math.random() * (window.innerWidth - 300) + 'px';
    widget.style.top = Math.random() * (window.innerHeight - 200) + 'px';
    
    const selectedTemplate = template || widgetTemplates[Math.floor(Math.random() * widgetTemplates.length)];
    
    let contentHtml;
    if (selectedTemplate.type === 'documents') {
        contentHtml = generateDocumentsList();
    } else {
        contentHtml = selectedTemplate.content;
    }
    
    widget.innerHTML = `
        <div class="widget-header">
            <div class="widget-title">${selectedTemplate.title}</div>
            <button class="widget-close">Ã—</button>
        </div>
        <div class="widget-content">${contentHtml}</div>
    `;
    
    // Close button
    const closeBtn = widget.querySelector('.widget-close');
    closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        widget.remove();
    });
    
    // Drag functionality
    widget.addEventListener('mousedown', startDrag);
    
    document.getElementById('desktop').appendChild(widget);
    
    // If this is a documents widget, fetch the recent documents
    if (selectedTemplate.type === 'documents') {
        currentPage = 0; // Reset to first page
        console.log('Creating documents widget, fetching live data...');
        fetchRecentDocuments().then(success => {
            if (success) {
                console.log('Successfully fetched documents, updating widget');
                updateDocumentsWidget(widget);
            } else {
                console.log('Failed to fetch documents, showing fallback data');
                // Use fallback static data for testing
                recentDocuments = [
                    {
                        id: "iManage!17740961.1",
                        name: "Test Document (FALLBACK)",
                        extension: "docx",
                        activity_date: "2025-08-17T20:49:19.17Z",
                        author_description: "Test User"
                    }
                ];
                updateDocumentsWidget(widget);
            }
        });
    }
}

function retryFetchDocuments(button) {
    const widget = button.closest('.widget');
    const contentDiv = widget.querySelector('.widget-content');
    contentDiv.innerHTML = generateDocumentsList(); // Show loading state
    
    fetchRecentDocuments().then(success => {
        if (success) {
            updateDocumentsWidget(widget);
        } else {
            contentDiv.innerHTML = `
                <div style="text-align: center; padding: 20px; color: #dc3545;">
                    Failed to load documents
                    <br>
                    <button onclick="retryFetchDocuments(this)" style="margin-top: 10px; padding: 5px 10px; border: 1px solid #dc3545; background: transparent; color: #dc3545; border-radius: 4px; cursor: pointer;">Retry</button>
                </div>
            `;
        }
    });
}

function openIManageDocument(docId, docName, extension) {
    console.log(`Opening iManage document: ${docName} (${docId})`);
    
    // Extract document number from the ID (format: "iManage!17740961.1")
    const docNumber = docId.split('!')[1].split('.')[0];
    
    // Use the coauthoredit endpoint for opening documents
    const apiUrl = `https://im.cloudimanage.com/m365/customers/145/libraries/IMANAGE/documents/IMANAGE!${docNumber}.1/coauthoredit?userId=MARK.RICHMAN&fileName=${encodeURIComponent(docName + '.' + extension)}&extension=${extension}`;
    
    // Make the REST API call
    fetch(apiUrl, {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'X-Auth-Token': 'FC4qmQ9bkcmapxxwAvpws_jrnUplCrubFi_BtGRLNuU'
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        }
        throw new Error(`HTTP error! status: ${response.status}`);
    })
    .then(data => {
        console.log('API Response:', data);
        
        // If the response contains a URL to open, use it
        let openUrl = apiUrl; // Fallback to the API endpoint itself
        
        if (data && data.editUrl) {
            openUrl = data.editUrl;
        } else if (data && data.url) {
            openUrl = data.url;
        }
        
        // Open in new window
        const newWindow = window.open(openUrl, '_blank');
        
        // Close the window after 3 seconds if it's still the API URL
        if (openUrl === apiUrl) {
            setTimeout(() => {
                if (newWindow && !newWindow.closed) {
                    newWindow.close();
                }
            }, 3000);
        }
    })
    .catch(error => {
        console.error('Error opening document:', error);
        
        // Fallback: try to open the API URL directly
        const newWindow = window.open(apiUrl, '_blank');
        
        setTimeout(() => {
            if (newWindow && !newWindow.closed) {
                newWindow.close();
            }
        }, 3000);
    });
}

function startDrag(e) {
    if (e.target.classList.contains('widget-close')) return;
    
    draggedElement = e.currentTarget;
    draggedElement.classList.add('dragging');
    
    const rect = draggedElement.getBoundingClientRect();
    offset.x = e.clientX - rect.left;
    offset.y = e.clientY - rect.top;
    
    document.addEventListener('mousemove', drag);
    document.addEventListener('mouseup', stopDrag);
}

function drag(e) {
    if (draggedElement) {
        const newX = e.clientX - offset.x;
        const newY = e.clientY - offset.y;
        
        // Constrain to viewport
        const maxX = window.innerWidth - draggedElement.offsetWidth;
        const maxY = window.innerHeight - draggedElement.offsetHeight;
        
        draggedElement.style.left = Math.max(0, Math.min(newX, maxX)) + 'px';
        draggedElement.style.top = Math.max(0, Math.min(newY, maxY)) + 'px';
    }
}

function stopDrag() {
    if (draggedElement) {
        draggedElement.classList.remove('dragging');
        draggedElement = null;
    }
    document.removeEventListener('mousemove', drag);
    document.removeEventListener('mouseup', stopDrag);
}

// Add widget button and menu
const addWidgetBtn = document.getElementById('addWidgetBtn');
const widgetMenu = document.getElementById('widgetMenu');

addWidgetBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    widgetMenu.classList.toggle('show');
});

// Close menu when clicking outside
document.addEventListener('click', (e) => {
    if (!addWidgetBtn.contains(e.target) && !widgetMenu.contains(e.target)) {
        widgetMenu.classList.remove('show');
    }
});

// Widget menu item clicks
document.querySelectorAll('.widget-menu-item').forEach(item => {
    item.addEventListener('click', (e) => {
        const widgetIndex = parseInt(e.currentTarget.getAttribute('data-widget'));
        createWidget(widgetTemplates[widgetIndex]);
        widgetMenu.classList.remove('show');
    });
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === ' ') {
        e.preventDefault();
        searchInput.focus();
    }
});

// Initial widgets
setTimeout(() => {
    createWidget(widgetTemplates[0]);
    setTimeout(() => createWidget(widgetTemplates[1]), 200);
}, 1000);