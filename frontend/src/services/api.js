// API service for communicating with Flask backend

const API_BASE_URL = 'http://localhost:5001/api'

class APIError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'APIError'
    this.status = status
  }
}

async function makeRequest(url, options = {}) {
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options
    })

    if (!response.ok) {
      throw new APIError(`Server error: ${response.status}`, response.status)
    }

    return await response.json()
  } catch (error) {
    if (error instanceof APIError) {
      throw error
    }
    
    // Network or other fetch errors
    throw new APIError('Network error', 0)
  }
}

/**
 * Transform API response data to match frontend component expectations
 * @param {Object} result - Raw API result object
 * @returns {Object} Transformed result object
 */
export function transformSearchResult(result) {
  return {
    id: (result.metadata?.id && result.metadata.id !== '') ? result.metadata.id : `result-${Math.random().toString(36).substr(2, 9)}`,
    title: (result.title && result.title !== '') ? result.title : 'Untitled Conversation',
    preview: result.content ? result.content.substring(0, 200) + (result.content.length > 200 ? '...' : '') : '',
    date: result.date !== undefined ? result.date : result.metadata?.earliest_ts,
    source: result.metadata?.source !== undefined ? result.metadata.source : 'unknown'
  }
}

/**
 * Search conversations using the backend API
 * @param {string} query - Search query string
 * @returns {Promise<{results: Array}>} Search results
 */
export async function searchConversations(query) {
  // Handle empty or null queries
  if (!query || query.trim() === '') {
    return { results: [] }
  }

  const url = `${API_BASE_URL}/search?q=${encodeURIComponent(query.trim())}`
  const response = await makeRequest(url)
  
  // Transform the results to match frontend expectations
  const transformedResults = response.results.map(transformSearchResult)
  
  return { results: transformedResults }
}

/**
 * Get a specific conversation by ID
 * @param {string} id - Conversation ID
 * @returns {Promise<Object>} Conversation details
 */
export async function getConversation(id) {
  if (!id) {
    throw new APIError('Conversation ID is required', 400)
  }

  const url = `${API_BASE_URL}/conversation/${encodeURIComponent(id)}`
  return await makeRequest(url)
}

/**
 * Get paginated conversations
 * @param {number} page - Page number (1-based)
 * @param {number} limit - Number of conversations per page
 * @returns {Promise<Object>} Paginated conversations response
 */
export async function getConversations(page = 1, limit = 50) {
  const url = `${API_BASE_URL}/conversations?page=${page}&limit=${limit}`
  return await makeRequest(url)
}

/**
 * Get conversation statistics
 * @returns {Promise<Object>} Statistics data
 */
export async function getStats() {
  const url = `${API_BASE_URL}/stats`
  return await makeRequest(url)
}

export { APIError }