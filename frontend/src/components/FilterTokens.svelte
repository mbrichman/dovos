<script>
  import { createEventDispatcher } from 'svelte'
  
  const dispatch = createEventDispatcher()
  
  // Filter state
  let sourceFilter = 'all'
  let dateFilter = 'all'  
  let sortOrder = 'newest'
  
  // Popover visibility state
  let showSourcePop = false
  let showDatePop = false
  let showSortPop = false
  
  // Filter options
  const sourceOptions = [
    { value: 'all', label: 'All Sources' },
    { value: 'claude', label: 'Claude' },
    { value: 'chatgpt', label: 'ChatGPT' },
    { value: 'docx', label: 'Word Documents' }
  ]
  
  const dateOptions = [
    { value: 'all', label: 'All Time' },
    { value: 'today', label: 'Today' },
    { value: 'week', label: 'Past Week' },
    { value: 'month', label: 'Past Month' },
    { value: 'year', label: 'Past Year' }
  ]
  
  const sortOptions = [
    { value: 'newest', label: 'Newest First' },
    { value: 'oldest', label: 'Oldest First' },
    { value: 'original', label: 'Original Order' }
  ]
  
  // Get display labels
  function getSourceLabel() {
    const option = sourceOptions.find(o => o.value === sourceFilter)
    return option ? option.label : 'All Sources'
  }
  
  function getDateLabel() {
    const option = dateOptions.find(o => o.value === dateFilter)
    return option ? option.label : 'All Time'
  }
  
  function getSortLabel() {
    const option = sortOptions.find(o => o.value === sortOrder)
    return option ? option.label : 'Newest First'
  }
  
  // Handle filter changes
  function updateSource(value) {
    sourceFilter = value
    showSourcePop = false
    emitFilterChange()
  }
  
  function updateDate(value) {
    dateFilter = value
    showDatePop = false
    emitFilterChange()
  }
  
  function updateSort(value) {
    sortOrder = value
    showSortPop = false
    emitFilterChange()
  }
  
  // Toggle functions that close others
  function toggleSourcePop() {
    showDatePop = false
    showSortPop = false
    showSourcePop = !showSourcePop
  }
  
  function toggleDatePop() {
    showSourcePop = false
    showSortPop = false
    showDatePop = !showDatePop
  }
  
  function toggleSortPop() {
    showSourcePop = false
    showDatePop = false
    showSortPop = !showSortPop
  }
  
  // Check if filters are in default state
  $: hasActiveFilters = sourceFilter !== 'all' || dateFilter !== 'all' || sortOrder !== 'newest'
  
  // Clear all filters
  function clearAllFilters() {
    sourceFilter = 'all'
    dateFilter = 'all'
    sortOrder = 'newest'
    showSourcePop = false
    showDatePop = false
    showSortPop = false
    emitFilterChange()
  }
  
  function emitFilterChange() {
    dispatch('filtersChanged', {
      source: sourceFilter,
      date: dateFilter,
      sort: sortOrder
    })
  }
  
  // Close all popovers when clicking outside
  function handleClickOutside() {
    showSourcePop = false
    showDatePop = false
    showSortPop = false
  }
</script>

<svelte:window on:click={handleClickOutside} />

<div class="filter-container">
  <div class="filter-tokens">
    <!-- Source Token -->
    <div class="token-container">
    <button 
      class="token {sourceFilter !== 'all' ? 'active' : ''}"
      on:click|stopPropagation={toggleSourcePop}
    >
      <span class="token-icon">📦</span>
      <span class="token-label">{getSourceLabel()}</span>
    </button>
    
    {#if showSourcePop}
      <div class="popover" on:click|stopPropagation>
        <div class="popover-content">
          <ul class="option-list">
            {#each sourceOptions as option}
              <li>
                <button 
                  class="option {sourceFilter === option.value ? 'selected' : ''}"
                  on:click={() => updateSource(option.value)}
                >
                  {option.label}
                </button>
              </li>
            {/each}
          </ul>
        </div>
      </div>
    {/if}
  </div>
  
  <!-- Date Token -->
  <div class="token-container">
    <button 
      class="token {dateFilter !== 'all' ? 'active' : ''}"
      on:click|stopPropagation={toggleDatePop}
    >
      <span class="token-icon">🗓️</span>
      <span class="token-label">{getDateLabel()}</span>
    </button>
    
    {#if showDatePop}
      <div class="popover" on:click|stopPropagation>
        <div class="popover-content">
          <ul class="option-list">
            {#each dateOptions as option}
              <li>
                <button 
                  class="option {dateFilter === option.value ? 'selected' : ''}"
                  on:click={() => updateDate(option.value)}
                >
                  {option.label}
                </button>
              </li>
            {/each}
          </ul>
        </div>
      </div>
    {/if}
  </div>
  
  <!-- Sort Token -->
  <div class="token-container">
    <button 
      class="token {sortOrder !== 'newest' ? 'active' : ''}"
      on:click|stopPropagation={toggleSortPop}
    >
      <span class="token-icon">↕️</span>
      <span class="token-label">{getSortLabel()}</span>
    </button>
    
    {#if showSortPop}
      <div class="popover popover-right" on:click|stopPropagation>
        <div class="popover-content">
          <ul class="option-list">
            {#each sortOptions as option}
              <li>
                <button 
                  class="option {sortOrder === option.value ? 'selected' : ''}"
                  on:click={() => updateSort(option.value)}
                >
                  {option.label}
                </button>
              </li>
            {/each}
          </ul>
        </div>
      </div>
    {/if}
  </div>
  </div>
  
  <!-- Clear All Button -->
  {#if hasActiveFilters}
    <button class="clear-all-btn" on:click={clearAllFilters}>
      <span>Clear All</span>
      <svg class="clear-icon" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  {/if}
</div>

<style>
  .filter-container {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    padding: 0.5rem 0.75rem;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
    margin-top: 0.5rem;
  }
  
  .filter-tokens {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }
  
  .token-container {
    position: relative;
  }
  
  .token {
    height: 2.25rem;
    padding: 0 0.75rem;
    border-radius: 0.75rem;
    border: 1px solid #d4d4d8;
    background: white;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
    cursor: pointer;
    transition: all 0.2s;
    color: #18181b;
  }
  
  .token:hover {
    background: #f4f4f5;
    border-color: #a1a1aa;
  }
  
  .token.active {
    border-color: #6366f1;
    background: #eef2ff;
    color: #4338ca;
  }
  
  .token-icon {
    opacity: 0.7;
    font-size: 0.875rem;
  }
  
  .token-label {
    max-width: 12rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .popover {
    position: absolute;
    top: calc(100% + 0.5rem);
    left: 0;
    z-index: 30;
    min-width: 15rem;
    border-radius: 1rem;
    border: 1px solid #e4e4e7;
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(8px);
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
    overflow: hidden;
  }
  
  .popover-right {
    right: 0;
    left: auto;
  }
  
  .popover-content {
    padding: 0.75rem;
  }
  
  .option-list {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  
  .option {
    width: 100%;
    text-align: left;
    padding: 0.75rem;
    border-radius: 0.5rem;
    border: none;
    background: transparent;
    cursor: pointer;
    transition: background-color 0.2s;
    font-size: 0.875rem;
    color: #18181b;
  }
  
  .option:hover {
    background: #f4f4f5;
  }
  
  .option.selected {
    background: #eef2ff;
    color: #4338ca;
    font-weight: 500;
  }
  
  .clear-all-btn {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    color: #6b7280;
    font-size: 0.875rem;
    background: transparent;
    border: none;
    cursor: pointer;
    transition: color 0.2s;
    padding: 0.25rem;
  }
  
  .clear-all-btn:hover {
    color: #374151;
  }
  
  .clear-icon {
    width: 1rem;
    height: 1rem;
  }
  
</style>