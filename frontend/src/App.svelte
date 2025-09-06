<script>
  import { onMount } from 'svelte'
  import SearchBox from './components/SearchBox.svelte'
  import ConversationList from './components/ConversationList.svelte'
  import ScrollableConversationList from './components/ScrollableConversationList.svelte'
  import { searchConversations, getConversation } from './services/api.js'
  
  // App state
  let conversations = []
  let isLoading = false
  let searchQuery = ''
  let selectedConversation = null
  let errorMessage = ''
  
  // Handle search from SearchBox component
  async function handleSearch(event) {
    const query = event.detail.query
    searchQuery = query
    
    if (!query.trim()) {
      conversations = []
      return
    }
    
    try {
      isLoading = true
      errorMessage = ''
      
      console.log('🔍 Searching for:', query)
      const results = await searchConversations(query)
      
      conversations = results.results
      console.log('✅ Found', conversations.length, 'results')
      
    } catch (error) {
      console.error('❌ Search error:', error)
      errorMessage = 'Search failed. Please try again.'
      conversations = []
    } finally {
      isLoading = false
    }
  }
  
  // Handle conversation selection
  async function handleConversationSelect(event) {
    const conversation = event.detail.conversation
    console.log('📄 Selected conversation:', conversation.title)
    
    try {
      // For now, just log the selection
      // Later we could navigate to a detail view or show in a modal
      selectedConversation = conversation
      
      // Optional: fetch full conversation details
      // const fullConversation = await getConversation(conversation.id)
      // console.log('Full conversation:', fullConversation)
      
    } catch (error) {
      console.error('❌ Error loading conversation:', error)
    }
  }
  
  // Clear search results
  function clearSearch() {
    searchQuery = ''
    conversations = []
    selectedConversation = null
    errorMessage = ''
  }
</script>

<main>
  <div class="app-container">
    <!-- Header -->
    <header class="app-header">
      <div class="header-content">
        <h1 class="app-title">DovOS - Conversation Browser</h1>
        <div class="header-actions">
          {#if searchQuery}
            <button class="clear-button" on:click={clearSearch}>
              Clear Search
            </button>
          {/if}
        </div>
      </div>
    </header>
    
    <!-- Two-pane Layout -->
    <div class="main-layout">
      <!-- Left Pane: All Conversations -->
      <aside class="left-pane">
        <div class="pane-header">
          <h2>All Conversations</h2>
        </div>
        <ScrollableConversationList on:select={handleConversationSelect} />
      </aside>
      
      <!-- Right Pane: Search & Details -->
      <main class="right-pane">
        <!-- Search Section -->
        <section class="search-section">
          <SearchBox on:search={handleSearch} />
        </section>
        
        <!-- Error Message -->
        {#if errorMessage}
          <div class="error-message">
            <p>{errorMessage}</p>
          </div>
        {/if}
        
        <!-- Content Area -->
        <section class="content-section">
          {#if searchQuery}
            <!-- Search Results -->
            <div class="search-results">
              <h3>Search Results for "{searchQuery}"</h3>
              <ConversationList 
                {conversations}
                {isLoading}
                {searchQuery}
                on:conversationSelect={handleConversationSelect}
              />
            </div>
          {:else if selectedConversation}
            <!-- Selected Conversation Details -->
            <div class="conversation-details">
              <h3>{selectedConversation.title}</h3>
              <p class="conversation-meta">
                <span class="source">{selectedConversation.source}</span>
                <span class="date">{selectedConversation.date}</span>
              </p>
              <div class="conversation-preview">
                <p>{selectedConversation.preview}</p>
                <p class="coming-soon">Full conversation view coming soon...</p>
              </div>
            </div>
          {:else}
            <!-- Welcome State -->
            <div class="welcome-state">
              <div class="welcome-icon">💬</div>
              <h2>Welcome to DovOS</h2>
              <p>Browse all your conversations in the left panel, or use search to find specific topics.</p>
              <div class="feature-list">
                <div class="feature-item">
                  <span class="feature-icon">📋</span>
                  <div>
                    <h4>Browse All Conversations</h4>
                    <p>Scroll through all your ChatGPT and Claude conversations in chronological order.</p>
                  </div>
                </div>
                <div class="feature-item">
                  <span class="feature-icon">🔍</span>
                  <div>
                    <h4>Powerful Search</h4>
                    <p>Find conversations by keywords, topics, or exact phrases.</p>
                  </div>
                </div>
              </div>
            </div>
          {/if}
        </section>
      </main>
    </div>
  </div>
</main>

<style>
  :global(body) {
    margin: 0;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
    background-color: #f9fafb;
  }
  
  .app-container {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }
  
  .app-header {
    background: white;
    border-bottom: 1px solid #e5e7eb;
    padding: 1rem 2rem;
    flex-shrink: 0;
  }
  
  .main-layout {
    display: flex;
    flex: 1;
    height: calc(100vh - 80px); /* Adjust based on header height */
  }
  
  .left-pane {
    width: 350px;
    background: white;
    border-right: 1px solid #e5e7eb;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
  }
  
  .pane-header {
    padding: 1rem;
    border-bottom: 1px solid #e5e7eb;
    background: #f9fafb;
  }
  
  .pane-header h2 {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: #374151;
  }
  
  .right-pane {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  
  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .app-title {
    color: #111827;
    margin: 0;
    font-size: 1.5rem;
    font-weight: 600;
  }
  
  .clear-button {
    padding: 0.5rem 1rem;
    background: #f3f4f6;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    color: #374151;
    cursor: pointer;
    font-size: 0.875rem;
    transition: all 0.2s;
  }
  
  .clear-button:hover {
    background: #e5e7eb;
    border-color: #9ca3af;
  }
  
  .search-section {
    padding: 1.5rem;
    border-bottom: 1px solid #e5e7eb;
    background: white;
  }
  
  .content-section {
    flex: 1;
    padding: 2rem;
    overflow-y: auto;
  }
  
  .error-message {
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-radius: 0.5rem;
    padding: 1rem;
    margin-bottom: 2rem;
    color: #dc2626;
    text-align: center;
  }
  
  .conversation-details {
    background: white;
    border-radius: 0.5rem;
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  }
  
  .conversation-details h3 {
    margin: 0 0 1rem 0;
    font-size: 1.25rem;
    color: #111827;
  }
  
  .conversation-meta {
    display: flex;
    gap: 1rem;
    margin-bottom: 1rem;
    font-size: 0.875rem;
  }
  
  .source {
    background: #dbeafe;
    color: #1e40af;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-weight: 500;
  }
  
  .date {
    color: #6b7280;
  }
  
  .conversation-preview {
    line-height: 1.6;
    color: #374151;
  }
  
  .coming-soon {
    color: #9ca3af;
    font-style: italic;
    margin-top: 1rem;
  }
  
  .feature-list {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    margin-top: 2rem;
  }
  
  .feature-item {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    padding: 1rem;
    background: white;
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  }
  
  .feature-icon {
    font-size: 1.5rem;
    flex-shrink: 0;
  }
  
  .feature-item h4 {
    margin: 0 0 0.5rem 0;
    color: #111827;
    font-size: 1rem;
  }
  
  .feature-item p {
    margin: 0;
    color: #6b7280;
    font-size: 0.875rem;
  }
  
  .welcome-state {
    text-align: center;
    padding: 4rem 2rem;
    background: white;
    border-radius: 0.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  }
  
  .welcome-icon {
    font-size: 4rem;
    margin-bottom: 1.5rem;
    opacity: 0.7;
  }
  
  .welcome-state h2 {
    color: #111827;
    margin-bottom: 1rem;
    font-size: 1.5rem;
  }
  
  .welcome-state p {
    color: #6b7280;
    margin-bottom: 2rem;
    font-size: 1.1rem;
  }
  
  .search-tips {
    background: #f9fafb;
    border-radius: 0.5rem;
    padding: 1.5rem;
    text-align: left;
    max-width: 400px;
    margin: 0 auto;
  }
  
  .search-tips h3 {
    color: #374151;
    margin: 0 0 1rem 0;
    font-size: 1rem;
  }
  
  .search-tips ul {
    margin: 0;
    padding-left: 1.5rem;
  }
  
  .search-tips li {
    color: #6b7280;
    margin-bottom: 0.5rem;
    line-height: 1.5;
  }
  
  .selection-info {
    margin-top: 2rem;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    border-radius: 0.5rem;
    padding: 1rem;
    max-width: 800px;
    margin-left: auto;
    margin-right: auto;
  }
  
  .selection-info p {
    margin: 0;
    color: #1e40af;
  }
  
  .text-sm {
    font-size: 0.875rem;
  }
  
  .text-gray-600 {
    color: #4b5563;
  }
  
  /* Responsive Design */
  @media (max-width: 768px) {
    .app-header {
      padding: 1rem;
    }
    
    .header-content {
      flex-direction: column;
      align-items: flex-start;
      gap: 1rem;
    }
    
    .main-content {
      padding: 1rem;
    }
    
    .welcome-state {
      padding: 2rem 1rem;
    }
    
    .search-tips {
      max-width: none;
    }
  }
</style>