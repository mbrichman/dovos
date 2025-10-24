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
}

function generateDocumentsList() {
    const documents = [
        {
            name: 'Sovereign Path Protocol v2.3.md',
            modified: '2025-08-15',
            user: 'Dov'
        },
        {
            name: 'Empire Has No Clothes - Draft.docx',
            modified: '2025-08-14',
            user: 'Dov'
        },
        {
            name: 'ChromaDB Vector Config.py',
            modified: '2025-08-13',
            user: 'Dov'
        },
        {
            name: 'PV Housing Research.xlsx',
            modified: '2025-08-12',
            user: 'Dov'
        },
        {
            name: 'Memoir - Lilith Arc Chapter 3.md',
            modified: '2025-08-11',
            user: 'Dov'
        }
    ];

    function getFileExtension(filename) {
        return filename.split('.').pop().toLowerCase();
    }

    function getFileIcon(extension) {
        const iconMap = {
            'md': 'MD',
            'docx': 'W',
            'doc': 'W',
            'py': 'PY',
            'xlsx': 'X',
            'xls': 'X',
            'pdf': 'PDF',
            'txt': 'TXT',
            'js': 'JS',
            'html': 'H',
            'css': 'CSS',
            'json': 'JS'
        };
        return iconMap[extension] || 'DOC';
    }

    let html = '<ul class="document-list">';
    documents.forEach(doc => {
        const formattedDate = new Date(doc.modified).toLocaleDateString('en-CA', {
            month: 'short',
            day: 'numeric'
        });
        
        const extension = getFileExtension(doc.name);
        const iconText = getFileIcon(extension);
        
        html += `
            <li class="document-item" onclick="openDocument('${doc.name}')">
                <div class="document-icon ${extension}">${iconText}</div>
                <div class="document-details">
                    <div class="document-name" title="${doc.name}">${doc.name}</div>
                    <div class="document-meta">
                        <span class="document-date">${formattedDate}</span>
                        <span class="document-user">${doc.user}</span>
                    </div>
                </div>
            </li>
        `;
    });
    html += '</ul>';
    
    return html;
}

function openDocument(docName) {
    console.log(`Opening document: ${docName}`);
    
    // Use the exact API URL for "Hello World" purposes
    const apiUrl = "https://im.cloudimanage.com/m365/customers/145/libraries/IMANAGE/documents/IMANAGE!17740961.1/coauthoredit?userId=MARK.RICHMAN&fileName=Hello%20World!.pptx&extension=pptx";
    
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
        // Otherwise, construct a fallback URL or handle accordingly
        let openUrl = apiUrl; // Fallback to the API endpoint itself
        
        // Check if response contains a redirect URL or edit URL
        if (data && data.editUrl) {
            openUrl = data.editUrl;
        } else if (data && data.url) {
            openUrl = data.url;
        }
        
        // Open in new window and close it after a short delay
        const newWindow = window.open(openUrl, '_blank');
        
        // Close the window after 3 seconds (enough time for redirect/loading)
        setTimeout(() => {
            if (newWindow && !newWindow.closed) {
                newWindow.close();
            }
        }, 3000);
    })
    .catch(error => {
        console.error('Error opening document:', error);
        
        // Fallback: still try to open the API URL in case it redirects properly
        const newWindow = window.open(apiUrl, '_blank');
        
        // Close the fallback window after 3 seconds too
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