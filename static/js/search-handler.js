// static/js/search-handler.js
/**
 * Search functionality for the index page
 */

export class SearchHandler {
    constructor() {
        this.init();
    }

    init() {
        // Handle share button on search results page
        const shareButton = document.getElementById('shareButton');
        if (shareButton) {
            shareButton.addEventListener('click', () => {
                this.handleShareClick();
            });
        }
        
        // Highlight search terms
        this.highlightSearchTerms();
    }

    handleShareClick() {
        try {
            // Get the current search query
            const searchInput = document.querySelector('input[name="query"]');
            const shareQuery = document.getElementById('shareQuery');
            
            if (searchInput && searchInput.value && shareQuery) {
                // Set the query in the shareable form
                shareQuery.value = searchInput.value;
                
                // Create the shareable URL
                const shareForm = document.getElementById('shareForm');
                const formData = new FormData(shareForm);
                const queryString = new URLSearchParams(formData).toString();
                const shareableUrl = window.location.origin + window.location.pathname + '?' + queryString;
                
                // Copy to clipboard
                navigator.clipboard.writeText(shareableUrl).then(() => {
                    // Show success message
                    const successMessage = document.getElementById('copySuccess');
                    if (successMessage) {
                        successMessage.style.display = 'block';
                        
                        // Hide after 2 seconds
                        setTimeout(() => {
                            successMessage.style.display = 'none';
                        }, 2000);
                    }
                });
            }
        } catch (error) {
            console.error('Error handling share click:', error);
        }
    }

    highlightSearchTerms() {
        const searchInput = document.querySelector('input[name="query"]');
        if (searchInput && searchInput.value) {
            const searchTerm = searchInput.value.trim();
            if (searchTerm) {
                const messageContents = document.querySelectorAll('.message-content');

                messageContents.forEach(content => {
                    this.highlightTextNodes(content, searchTerm);
                });
            }
        }
    }

    /**
     * Safely highlights search terms in text nodes only, preserving HTML structure
     * @param {Element} element - The element to search within
     * @param {string} searchTerm - The term to highlight
     */
    highlightTextNodes(element, searchTerm) {
        // Escape special regex characters in search term
        const escapedTerm = searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${escapedTerm})`, 'gi');

        // Walk through all text nodes
        const walker = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: (node) => {
                    // Skip empty text nodes and nodes in script/style tags
                    if (!node.textContent.trim()) return NodeFilter.FILTER_REJECT;
                    const parent = node.parentElement;
                    if (parent.tagName === 'SCRIPT' || parent.tagName === 'STYLE' || parent.tagName === 'MARK') {
                        return NodeFilter.FILTER_REJECT;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                }
            }
        );

        const nodesToHighlight = [];
        let currentNode;

        // Collect all text nodes first (can't modify while walking)
        while (currentNode = walker.nextNode()) {
            if (regex.test(currentNode.textContent)) {
                nodesToHighlight.push(currentNode);
            }
        }

        // Now highlight each text node
        nodesToHighlight.forEach(node => {
            const text = node.textContent;
            const matches = [];
            let match;

            // Reset regex for new text
            regex.lastIndex = 0;

            // Find all matches
            while ((match = regex.exec(text)) !== null) {
                matches.push({
                    index: match.index,
                    length: match[0].length,
                    text: match[0]
                });
            }

            if (matches.length === 0) return;

            // Create document fragment with highlighted text
            const fragment = document.createDocumentFragment();
            let lastIndex = 0;

            matches.forEach(match => {
                // Add text before match
                if (match.index > lastIndex) {
                    fragment.appendChild(
                        document.createTextNode(text.substring(lastIndex, match.index))
                    );
                }

                // Add highlighted match
                const mark = document.createElement('mark');
                mark.textContent = match.text;
                fragment.appendChild(mark);

                lastIndex = match.index + match.length;
            });

            // Add remaining text
            if (lastIndex < text.length) {
                fragment.appendChild(
                    document.createTextNode(text.substring(lastIndex))
                );
            }

            // Replace the text node with the fragment
            node.parentNode.replaceChild(fragment, node);
        });
    }
}
