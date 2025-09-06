<script>
  import { onMount, onDestroy, createEventDispatcher } from 'svelte'
  import { getConversations } from '../services/api.js'
  import ConversationCard from './ConversationCard.svelte'

  export let pageSize = 50

  const dispatch = createEventDispatcher()

  let conversations = []
  let isLoading = true
  let isLoadingMore = false
  let error = null
  let loadMoreError = null
  let currentPage = 1
  let hasNextPage = false
  let sentinelElement
  let intersectionObserver

  async function loadConversations(page = 1, append = false) {
    try {
      if (!append) {
        isLoading = true
        error = null
      } else {
        isLoadingMore = true
        loadMoreError = null
      }

      const response = await getConversations(page, pageSize)
      
      if (append) {
        conversations = [...conversations, ...response.conversations]
      } else {
        conversations = response.conversations
      }

      currentPage = response.pagination.page
      hasNextPage = response.pagination.has_next

    } catch (err) {
      if (append) {
        loadMoreError = err.message
      } else {
        error = err.message
        conversations = []
      }
    } finally {
      isLoading = false
      isLoadingMore = false
    }
  }

  function handleConversationSelect(event) {
    dispatch('select', event.detail)
  }

  function handleTryAgain() {
    loadConversations(1, false)
  }

  function handleLoadMore() {
    if (hasNextPage && !isLoadingMore) {
      loadConversations(currentPage + 1, true)
    }
  }

  function setupIntersectionObserver() {
    if (!sentinelElement) return

    intersectionObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting && hasNextPage && !isLoadingMore) {
            handleLoadMore()
          }
        })
      },
      {
        rootMargin: '100px'
      }
    )

    intersectionObserver.observe(sentinelElement)
  }

  onMount(() => {
    loadConversations()
  })

  onDestroy(() => {
    if (intersectionObserver) {
      intersectionObserver.disconnect()
    }
  })

  // Setup intersection observer after conversations load
  $: if (conversations.length > 0 && sentinelElement && !intersectionObserver) {
    setupIntersectionObserver()
  }
</script>

<div class="scrollable-conversation-list">
  {#if isLoading && conversations.length === 0}
    <div class="loading-state" role="status" aria-live="polite">
      <div class="flex items-center justify-center py-8">
        <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-600 mr-3"></div>
        <span class="text-gray-600">Loading conversations...</span>
      </div>
    </div>
  {:else if error && conversations.length === 0}
    <div class="error-state py-8 text-center">
      <div class="text-red-500 mb-4">Error loading conversations: {error}</div>
      <button 
        class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        on:click={handleTryAgain}
      >
        Try Again
      </button>
    </div>
  {:else if conversations.length === 0}
    <div class="empty-state py-12 text-center">
      <div class="text-gray-400 text-4xl mb-4">💬</div>
      <h3 class="text-lg font-medium text-gray-900 mb-2">No conversations found</h3>
      <p class="text-gray-500">Upload some conversation files to get started.</p>
    </div>
  {:else}
    <div class="conversation-list">
      {#each conversations as conversation (conversation.id)}
        <div class="mb-2">
          <ConversationCard 
            {conversation} 
            on:select={handleConversationSelect}
          />
        </div>
      {/each}

      <!-- Loading more indicator -->
      {#if isLoadingMore}
        <div class="loading-more py-4 text-center">
          <div class="flex items-center justify-center">
            <div class="animate-spin rounded-full h-4 w-4 border-b-2 border-indigo-600 mr-2"></div>
            <span class="text-gray-600">Loading more...</span>
          </div>
        </div>
      {/if}

      <!-- Load more error -->
      {#if loadMoreError}
        <div class="load-more-error py-4 text-center">
          <div class="text-red-500 mb-2">Failed to load more: {loadMoreError}</div>
          <button 
            class="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
            on:click={handleLoadMore}
          >
            Load More
          </button>
        </div>
      {/if}

      <!-- Intersection observer sentinel -->
      <div bind:this={sentinelElement} class="sentinel" aria-hidden="true"></div>
    </div>
  {/if}
</div>

<style>
  .scrollable-conversation-list {
    height: 100%;
    overflow-y: auto;
    padding: 1rem;
  }

  .loading-state,
  .error-state,
  .empty-state {
    min-height: 200px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  .conversation-list {
    width: 100%;
  }

  .sentinel {
    height: 1px;
    margin: 1px;
  }

  .flex {
    display: flex;
  }

  .items-center {
    align-items: center;
  }

  .justify-center {
    justify-content: center;
  }

  .animate-spin {
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>