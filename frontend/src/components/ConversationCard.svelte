<script>
  import { createEventDispatcher } from 'svelte'
  
  export let conversation
  
  const dispatch = createEventDispatcher()
  
  function handleClick() {
    dispatch('select', { conversation })
  }
  
  function formatDate(dateString) {
    if (!dateString) return ''
    
    try {
      const date = new Date(dateString)
      if (isNaN(date.getTime())) return dateString
      
      const now = new Date()
      const isThisYear = date.getFullYear() === now.getFullYear()
      
      const options = {
        month: 'short',
        day: 'numeric'
      }
      
      if (!isThisYear) {
        options.year = 'numeric'
      }
      
      return date.toLocaleDateString(undefined, options)
    } catch (e) {
      return dateString
    }
  }
  
  function getSourceDisplayName(source) {
    switch (source?.toLowerCase()) {
      case 'chatgpt':
        return 'ChatGPT'
      case 'claude':
        return 'Claude'
      case 'docx':
        return 'Word Doc'
      default:
        return source || 'Unknown'
    }
  }
  
  function getSourceBadgeColor(source) {
    switch (source?.toLowerCase()) {
      case 'chatgpt':
        return 'bg-green-100 text-green-800'
      case 'claude':
        return 'bg-blue-100 text-blue-800'
      case 'docx':
        return 'bg-purple-100 text-purple-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }
</script>

<button 
  class="conversation-card"
  on:click={handleClick}
  role="button"
  tabindex="0"
>
  <div class="flex items-center justify-between gap-2 mb-1">
    <h3 class="font-medium text-gray-900 truncate flex-1">
      {conversation.title || 'Untitled Conversation'}
    </h3>
    <div class="flex items-center gap-2 flex-shrink-0">
      <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium {getSourceBadgeColor(conversation.source)}">
        {getSourceDisplayName(conversation.source)}
      </span>
      {#if conversation.date}
        <span class="text-xs text-gray-500 whitespace-nowrap">
          {formatDate(conversation.date)}
        </span>
      {/if}
    </div>
  </div>
  
  {#if conversation.preview}
    <p class="text-sm text-gray-600 truncate mt-1">
      {conversation.preview}
    </p>
  {/if}
</button>

<style>
  .conversation-card {
    width: 100%;
    text-align: left;
    padding: 0.5rem;
    border-radius: 0.75rem;
    border: 1px solid #e4e4e7;
    background: white;
    transition: all 0.2s ease;
    cursor: pointer;
  }
  
  .conversation-card:hover {
    background: rgba(244, 244, 245, 0.4);
    border-color: #d4d4d8;
  }
  
  .conversation-card:focus {
    outline: 2px solid #6366f1;
    outline-offset: 2px;
  }
  
  .line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  
  .flex {
    display: flex;
  }
  
  .items-start {
    align-items: flex-start;
  }
  
  .items-center {
    align-items: center;
  }
  
  .justify-between {
    justify-content: space-between;
  }
  
  .gap-2 {
    gap: 0.5rem;
  }
  
  .gap-3 {
    gap: 0.75rem;
  }
  
  .mb-1 {
    margin-bottom: 0.25rem;
  }

  .mb-2 {
    margin-bottom: 0.5rem;
  }

  .mt-1 {
    margin-top: 0.25rem;
  }

  .truncate {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .flex-1 {
    flex: 1;
  }
  
  .flex-shrink-0 {
    flex-shrink: 0;
  }
  
  .font-medium {
    font-weight: 500;
  }
  
  .text-gray-900 {
    color: #18181b;
  }
  
  .text-sm {
    font-size: 0.875rem;
  }
  
  .text-xs {
    font-size: 0.75rem;
  }
  
  .text-gray-600 {
    color: #71717a;
  }
  
  .text-gray-500 {
    color: #71717a;
  }
  
  .whitespace-nowrap {
    white-space: nowrap;
  }
  
  .leading-relaxed {
    line-height: 1.625;
  }
  
  .inline-flex {
    display: inline-flex;
  }
  
  .px-2 {
    padding-left: 0.5rem;
    padding-right: 0.5rem;
  }
  
  .py-1 {
    padding-top: 0.25rem;
    padding-bottom: 0.25rem;
  }
  
  .rounded-full {
    border-radius: 9999px;
  }
  
  .bg-green-100 {
    background-color: #dcfce7;
  }
  
  .text-green-800 {
    color: #166534;
  }
  
  .bg-blue-100 {
    background-color: #dbeafe;
  }
  
  .text-blue-800 {
    color: #1e40af;
  }
  
  .bg-purple-100 {
    background-color: #f3e8ff;
  }
  
  .text-purple-800 {
    color: #6b21a8;
  }
  
  .bg-gray-100 {
    background-color: #f4f4f5;
  }
  
  .text-gray-800 {
    color: #27272a;
  }
</style>