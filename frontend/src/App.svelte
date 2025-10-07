<script>
  import { onMount } from 'svelte'
  import SearchBox from './components/SearchBox.svelte'
  import FilterTokens from './components/FilterTokens.svelte'
  import ConversationList from './components/ConversationList.svelte'
  import ScrollableConversationList from './components/ScrollableConversationList.svelte'
  import MessageView from './components/MessageView.svelte'
  import { searchConversations, getConversation } from './services/api.js'
  
  // App state
  let conversations = []
  let isLoading = false
  let searchQuery = ''
  let selectedConversation = null
  let fullConversation = null
  let loadingConversation = false
  let errorMessage = ''
  
  // Filter state
  let filters = {
    source: 'all',
    date: 'all', 
    sort: 'newest'
  }
  
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
      selectedConversation = conversation
      loadingConversation = true
      fullConversation = null
      
      // Fetch full conversation details with messages
      const details = await getConversation(conversation.id)
      console.log('✅ Loaded conversation details:', details)
      
      fullConversation = details
      
    } catch (error) {
      console.error('❌ Error loading conversation:', error)
      fullConversation = null
    } finally {
      loadingConversation = false
    }
  }
  
  // Clear search results
  function clearSearch() {
    searchQuery = ''
    conversations = []
    selectedConversation = null
    fullConversation = null
    errorMessage = ''
  }
  
  // Handle filter changes
  function handleFiltersChanged(event) {
    filters = event.detail
    console.log('🔧 Filters changed:', filters)
    // TODO: Apply filters to conversations list
  }
</script>

<main>
  <div class="app-container">
    <!-- Header -->
    <header class="app-header">
      <div class="header-content">
        <h1 class="app-title">DovOS - Conversation Browser</h1>
      </div>
    </header>
    
    <!-- Two-pane Layout -->
    <div class="main-layout">
      <!-- Left Pane: Search & Conversations List -->
      <aside class="left-pane">
        <!-- Search Section -->
        <div class="search-header">
          <SearchBox on:search={handleSearch} />
          <FilterTokens on:filtersChanged={handleFiltersChanged} />
        </div>
        
        <!-- Error Message -->
        {#if errorMessage}
          <div class="error-message-left">
            <p>{errorMessage}</p>
          </div>
        {/if}
        
        <!-- Conversations List (All or Search Results) -->
        <div class="conversations-container">
          {#if searchQuery}
            <!-- Search Results in Left Pane -->
            <div class="search-results-header">
              <h3>Search Results for "{searchQuery}"</h3>
              <button class="clear-search-btn" on:click={clearSearch}>Clear</button>
            </div>
            <ConversationList 
              {conversations}
              {isLoading}
              {searchQuery}
              on:conversationSelect={handleConversationSelect}
            />
          {:else}
            <!-- All Conversations -->
            <div class="pane-header">
              <h2>All Conversations</h2>
            </div>
            <ScrollableConversationList on:select={handleConversationSelect} />
          {/if}
        </div>
      </aside>
      
      <!-- Right Pane: Conversation Details -->
      <main class="right-pane">
        <!-- Content Area -->
        <section class="content-section">
          {#if fullConversation}
            <!-- Full Message View -->
            <MessageView conversation={fullConversation} />
          {:else if loadingConversation}
            <!-- Loading State -->
            <div class="loading-state">
              <div class="loading-spinner">Loading conversation...</div>
            </div>
          {:else if selectedConversation}
            <!-- Selected Conversation Preview -->
            <div class="conversation-details">
              <h3>{selectedConversation.title}</h3>
              <p class="conversation-meta">
                <span class="source">{selectedConversation.source}</span>
                <span class="date">{selectedConversation.date}</span>
              </p>
              <div class="conversation-preview">
                <p>{selectedConversation.preview}</p>
                <p class="coming-soon">Loading full conversation...</p>
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
    background-color: #fafafa;
    color: #18181b;
  }
  
  .app-container {
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  
  .app-header {
    background: #fafafa;
    border-bottom: 1px solid #e4e4e7;
    padding: 1rem 2rem;
    flex-shrink: 0;
  }
  
  .main-layout {
    display: flex;
    flex: 1;
    min-height: 0; /* Allow flex children to shrink */
    overflow: hidden;
  }
  
  .left-pane {
    width: 400px;
    background: white;
    border-right: 1px solid #e4e4e7;
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    overflow: hidden;
  }
  
  .search-header {
    padding: 0.75rem;
    border-bottom: 1px solid #e4e4e7;
    background: rgba(250, 250, 250, 0.8);
    backdrop-filter: blur(8px);
    flex-shrink: 0;
    position: sticky;
    top: 0;
    z-index: 10;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }
  
  .conversations-container {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  
  
  .pane-header {
    padding: 1rem;
    border-bottom: 1px solid #e4e4e7;
    background: #fafafa;
    flex-shrink: 0;
  }
  
  .pane-header h2 {
    margin: 0;
    font-size: 1.125rem;
    font-weight: 600;
    color: #18181b;
  }
  
  .search-results-header {
    padding: 1rem;
    border-bottom: 1px solid #e4e4e7;
    background: #fafafa;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-shrink: 0;
  }
  
  .search-results-header h3 {
    margin: 0;
    font-size: 1rem;
    font-weight: 600;
    color: #18181b;
  }
  
  .clear-search-btn {
    padding: 0.25rem 0.75rem;
    background: #f3f4f6;
    border: 1px solid #d1d5db;
    border-radius: 0.375rem;
    color: #374151;
    cursor: pointer;
    font-size: 0.75rem;
    transition: all 0.2s;
  }
  
  .clear-search-btn:hover {
    background: #e5e7eb;
    border-color: #9ca3af;
  }
  
  .error-message-left {
    background: #fef2f2;
    border-bottom: 1px solid #fecaca;
    padding: 0.75rem 1rem;
    color: #dc2626;
    font-size: 0.875rem;
    flex-shrink: 0;
  }
  
  .right-pane {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 0;
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
  
  
  .content-section {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
  }
  
  .content-section :global(.messages) {
    flex: 1;
    overflow-y: auto;
  }
  
  .loading-state {
    display: flex;
    align-items: center;
    justify-content: center;
    flex: 1;
    padding: 2rem;
  }
  
  .loading-spinner {
    color: #6b7280;
    font-size: 1rem;
  }
  
  
  .conversation-details {
    background: white;
    border-radius: 0.5rem;
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    margin: 2rem;
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
    margin: 2rem;
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
    
    .welcome-state {
      padding: 2rem 1rem;
    }
  }
</style>