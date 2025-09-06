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
  
  function getSourceBadgeClass(source) {
    switch (source?.toLowerCase()) {
      case 'chatgpt':
        return 'badge--indigo'
      case 'claude':
        return 'badge--amber'
      case 'docx':
        return 'badge'
      default:
        return 'badge'
    }
  }
</script>

<button 
  class="thread"
  on:click={handleClick}
>
  <div class="thread__main">
    <div class="thread__title">
      <h3 class="thread__name">{conversation.title || 'Untitled Conversation'}</h3>
      {#if conversation.date}
        <span class="thread__date" title={conversation.date}>
          {formatDate(conversation.date)}
        </span>
      {/if}
    </div>
    {#if conversation.preview}
      <p class="thread__summary">
        {conversation.preview}
      </p>
    {/if}
    <div class="thread__meta">
      <span class="badge {getSourceBadgeClass(conversation.source)}">
        {getSourceDisplayName(conversation.source)}
      </span>
    </div>
  </div>
</button>

<style>
  /* CSS variables matching the mockup */
  :root {
    --bg: #fafafa;
    --panel: #ffffff;
    --ink: #0b0b0c;
    --muted: #6b7280;
    --line: #e5e7eb;
    --line-strong: #d1d5db;
    --indigo: #4f46e5;
    --indigo-weak: #eef2ff;
    --amber: #f59e0b;
    --shadow: 0 1px 2px rgba(0,0,0,.06), 0 10px 30px rgba(0,0,0,.06);
  }

  /* Thread styles from mockup */
  .thread {
    width: 100%;
    text-align: left;
    background: color-mix(in lab, var(--panel) 96%, transparent);
    border: 1px solid var(--line);
    border-radius: 18px;
    padding: 14px;
    box-shadow: none;
    display: block;
    cursor: pointer;
    color: var(--ink);
  }
  
  .thread:hover {
    box-shadow: var(--shadow);
  }
  
  .thread:focus {
    outline: 2px solid var(--indigo);
    outline-offset: 2px;
  }
  
  .thread__title {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
  }
  
  .thread__name {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .thread__date {
    font-size: 12px;
    color: var(--muted);
    white-space: nowrap;
  }
  
  .thread__summary {
    -webkit-line-clamp: 2;
    display: -webkit-box;
    -webkit-box-orient: vertical;
    overflow: hidden;
    color: var(--muted);
    font-size: 13px;
    margin: 0.4rem 0 0;
  }
  
  .thread__meta {
    display: flex;
    gap: 6px;
    margin-top: 10px;
    align-items: center;
  }
  
  .badge {
    display: inline-flex;
    align-items: center;
    height: 22px;
    padding: 0 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
    background: #eef2f7;
    color: #334155;
  }
  
  .badge--indigo {
    background: var(--indigo-weak);
    color: var(--indigo);
  }
  
  .badge--amber {
    background: color-mix(in oklab, var(--amber) 20%, transparent);
    color: var(--amber);
  }
</style>