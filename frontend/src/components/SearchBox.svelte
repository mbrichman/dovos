<script>
  import { createEventDispatcher } from 'svelte'
  
  const dispatch = createEventDispatcher()
  
  let query = ''
  let isSearching = false
  let searchTimeout
  
  // Debounced search function
  function handleInput() {
    clearTimeout(searchTimeout)
    
    if (query.trim() === '') {
      isSearching = false
      return
    }
    
    isSearching = true
    
    searchTimeout = setTimeout(() => {
      dispatch('search', { query: query.trim() })
      isSearching = false
    }, 300)
  }
  
  function clearSearch() {
    query = ''
    clearTimeout(searchTimeout)
    isSearching = false
    dispatch('search', { query: '' })
  }
</script>

<div class="search-box">
  <div class="search-input-container">
    <input
      type="text"
      placeholder="Search conversations"
      bind:value={query}
      on:input={handleInput}
      class="search-input"
    />
    
    {#if query}
      <button
        type="button"
        on:click={clearSearch}
        class="clear-button"
        aria-label="Clear search"
      >
        ×
      </button>
    {/if}
  </div>
  
  {#if isSearching}
    <div class="loading-indicator">
      Searching...
    </div>
  {/if}
</div>

<style>
  .search-box {
    position: relative;
    width: 100%;
  }
  
  .search-input-container {
    position: relative;
    display: flex;
    align-items: center;
  }
  
  .search-input {
    width: 100%;
    padding: 0.5rem 0.75rem;
    border: 1px solid #d4d4d8;
    border-radius: 0.75rem;
    font-size: 0.875rem;
    outline: none;
    transition: all 0.2s;
    background: white;
  }
  
  .search-input:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.25);
  }
  
  .clear-button {
    position: absolute;
    right: 0.75rem;
    background: none;
    border: none;
    font-size: 1.25rem;
    color: #6b7280;
    cursor: pointer;
    padding: 0;
    width: 1.5rem;
    height: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .clear-button:hover {
    color: #374151;
  }
  
  .loading-indicator {
    position: absolute;
    top: 100%;
    left: 0;
    margin-top: 0.25rem;
    font-size: 0.75rem;
    color: #6b7280;
    animation: pulse 1.5s ease-in-out infinite;
  }
  
  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.5;
    }
  }
</style>