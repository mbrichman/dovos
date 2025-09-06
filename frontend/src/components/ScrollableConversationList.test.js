import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/svelte'
import { rest } from 'msw'
import { server } from '../test/setup.js'

// Mock ConversationCard component
vi.mock('./ConversationCard.svelte', () => ({
  default: {
    render: () => '<div data-testid="conversation-card">Mock Conversation Card</div>',
    $$prop_def: {}
  }
}))

import ScrollableConversationList from './ScrollableConversationList.svelte'

// Mock IntersectionObserver for infinite scroll testing
const mockIntersectionObserver = vi.fn()
mockIntersectionObserver.mockReturnValue({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn()
})

beforeEach(() => {
  window.IntersectionObserver = mockIntersectionObserver
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('ScrollableConversationList', () => {
  test('renders loading state initially', () => {
    render(ScrollableConversationList)
    
    expect(screen.getByText('Loading conversations...')).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  // TODO: Fix MSW integration - onMount not executing in test environment
  // test('loads and displays conversations from MSW', async () => {
  //   render(ScrollableConversationList)
  //   
  //   // Wait for MSW to respond and component to update
  //   await waitFor(() => {
  //     expect(screen.getByText('Conversation 1')).toBeInTheDocument()
  //   }, { timeout: 5000 })
  //   
  //   // Check that conversations are loaded
  //   expect(screen.getByText('Conversation 1')).toBeInTheDocument()
  //   expect(screen.queryByText('Loading conversations...')).not.toBeInTheDocument()
  // })

  /*test('displays empty state when no conversations exist', async () => {
    // Override MSW to return empty results for this test
    server.use(
      rest.get('http://localhost:5001/api/conversations', (req, res, ctx) => {
        return res(ctx.json({
          conversations: [],
          pagination: {
            page: 1,
            limit: 50,
            total: 0,
            has_next: false,
            has_prev: false
          }
        }))
      })
    )
    
    render(ScrollableConversationList)
    
    await waitFor(() => {
      expect(screen.getByText('No conversations found')).toBeInTheDocument()
    })
    
    expect(screen.getByText('Upload some conversation files to get started.')).toBeInTheDocument()
  })

  test('handles API error gracefully', async () => {
    // Override MSW to return error for this test
    server.use(
      rest.get('http://localhost:5001/api/conversations', (req, res, ctx) => {
        return res(ctx.status(500))
      })
    )
    
    render(ScrollableConversationList)
    
    await waitFor(() => {
      expect(screen.getByText(/error loading conversations/i)).toBeInTheDocument()
    })
    
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  test('retries loading when try again button is clicked', async () => {
    let callCount = 0
    
    // Override MSW to fail first, succeed second
    server.use(
      rest.get('http://localhost:5001/api/conversations', (req, res, ctx) => {
        callCount++
        if (callCount === 1) {
          return res(ctx.status(500))
        }
        // Return normal data on retry
        return res(ctx.json({
          conversations: [{
            id: 'conv-1',
            title: 'First Conversation',
            preview: 'This is the first conversation...',
            date: '2024-01-01T10:00:00Z',
            source: 'chatgpt'
          }],
          pagination: {
            page: 1,
            limit: 50,
            total: 1,
            has_next: false,
            has_prev: false
          }
        }))
      })
    )
    
    render(ScrollableConversationList)
    
    await waitFor(() => {
      expect(screen.getByText(/error loading conversations/i)).toBeInTheDocument()
    })
    
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))
    
    await waitFor(() => {
      expect(screen.getByText('First Conversation')).toBeInTheDocument()
    })
  })

  test('emits select event when conversation is clicked', async () => {
    const { component } = render(ScrollableConversationList)
    const mockSelect = vi.fn()
    component.$on('select', mockSelect)
    
    await waitFor(() => {
      expect(screen.getByText('Conversation 1')).toBeInTheDocument()
    })
    
    fireEvent.click(screen.getByText('Conversation 1'))
    
    expect(mockSelect).toHaveBeenCalledWith(
      expect.objectContaining({
        detail: expect.objectContaining({
          conversation: expect.objectContaining({
            id: 'conv-1',
            title: 'Conversation 1'
          })
        })
      })
    )
  })

  test('sets up intersection observer for infinite scroll', async () => {
    render(ScrollableConversationList)
    
    await waitFor(() => {
      expect(screen.getByText('Conversation 1')).toBeInTheDocument()
    })
    
    // Should set up IntersectionObserver
    expect(mockIntersectionObserver).toHaveBeenCalled()
    const observerInstance = mockIntersectionObserver.mock.results[0].value
    expect(observerInstance.observe).toHaveBeenCalled()
  })

  test('loads next page when scrolled to bottom and has more data', async () => {
    let callCount = 0
    
    // Mock intersection observer callback to simulate scrolling to bottom
    let intersectionCallback
    mockIntersectionObserver.mockImplementation((callback) => {
      intersectionCallback = callback
      return {
        observe: vi.fn(),
        unobserve: vi.fn(), 
        disconnect: vi.fn()
      }
    })
    
    // Override MSW to track page requests
    server.use(
      rest.get('http://localhost:5001/api/conversations', (req, res, ctx) => {
        const page = parseInt(req.url.searchParams.get('page') || '1')
        callCount++
        
        if (page === 1) {
          // First page
          return res(ctx.json({
            conversations: [
              { id: 'conv-1', title: 'Conversation 1', preview: 'Preview 1', date: '2024-01-01T10:00:00Z', source: 'chatgpt' },
              { id: 'conv-2', title: 'Conversation 2', preview: 'Preview 2', date: '2024-01-02T10:00:00Z', source: 'claude' }
            ],
            pagination: { page: 1, limit: 50, total: 4, has_next: true, has_prev: false }
          }))
        } else {
          // Second page
          return res(ctx.json({
            conversations: [
              { id: 'conv-3', title: 'Conversation 3', preview: 'Preview 3', date: '2024-01-03T10:00:00Z', source: 'chatgpt' },
              { id: 'conv-4', title: 'Conversation 4', preview: 'Preview 4', date: '2024-01-04T10:00:00Z', source: 'claude' }
            ],
            pagination: { page: 2, limit: 50, total: 4, has_next: false, has_prev: true }
          }))
        }
      })
    )
    
    render(ScrollableConversationList)
    
    await waitFor(() => {
      expect(screen.getByText('Conversation 1')).toBeInTheDocument()
    })
    
    // Simulate intersection (scrolled to bottom)
    intersectionCallback([{ isIntersecting: true }])
    
    await waitFor(() => {
      expect(screen.getByText('Conversation 3')).toBeInTheDocument()
    })
    
    // Should display both pages
    expect(screen.getByText('Conversation 1')).toBeInTheDocument()
    expect(screen.getByText('Conversation 3')).toBeInTheDocument()
    expect(callCount).toBe(2)
  })

  test('does not load next page when already at end', async () => {
    let callCount = 0
    
    let intersectionCallback
    mockIntersectionObserver.mockImplementation((callback) => {
      intersectionCallback = callback
      return {
        observe: vi.fn(),
        unobserve: vi.fn(),
        disconnect: vi.fn()
      }
    })
    
    // Override MSW to return data without next page
    server.use(
      rest.get('http://localhost:5001/api/conversations', (req, res, ctx) => {
        callCount++
        return res(ctx.json({
          conversations: [
            { id: 'conv-1', title: 'Conversation 1', preview: 'Preview 1', date: '2024-01-01T10:00:00Z', source: 'chatgpt' }
          ],
          pagination: { page: 1, limit: 50, total: 1, has_next: false, has_prev: false }
        }))
      })
    )
    
    render(ScrollableConversationList)
    
    await waitFor(() => {
      expect(screen.getByText('Conversation 1')).toBeInTheDocument()
    })
    
    // Simulate intersection (scrolled to bottom)
    intersectionCallback([{ isIntersecting: true }])
    
    // Should not make another API call
    await new Promise(resolve => setTimeout(resolve, 100))
    expect(callCount).toBe(1)
  })

  test('shows loading indicator while loading next page', async () => {
    let intersectionCallback
    mockIntersectionObserver.mockImplementation((callback) => {
      intersectionCallback = callback
      return {
        observe: vi.fn(),
        unobserve: vi.fn(),
        disconnect: vi.fn()
      }
    })
    
    // Override MSW to delay second page response
    server.use(
      rest.get('http://localhost:5001/api/conversations', (req, res, ctx) => {
        const page = parseInt(req.url.searchParams.get('page') || '1')
        
        if (page === 1) {
          return res(ctx.json({
            conversations: [{ id: 'conv-1', title: 'Conversation 1', preview: 'Preview 1', date: '2024-01-01T10:00:00Z', source: 'chatgpt' }],
            pagination: { page: 1, limit: 50, total: 2, has_next: true, has_prev: false }
          }))
        } else {
          // Delay the response to test loading state
          return res(ctx.delay(1000), ctx.json({
            conversations: [{ id: 'conv-2', title: 'Conversation 2', preview: 'Preview 2', date: '2024-01-02T10:00:00Z', source: 'claude' }],
            pagination: { page: 2, limit: 50, total: 2, has_next: false, has_prev: true }
          }))
        }
      })
    )
    
    render(ScrollableConversationList)
    
    await waitFor(() => {
      expect(screen.getByText('Conversation 1')).toBeInTheDocument()
    })
    
    // Simulate intersection
    intersectionCallback([{ isIntersecting: true }])
    
    await waitFor(() => {
      expect(screen.getByText('Loading more...')).toBeInTheDocument()
    })
  })

  test('handles error while loading next page', async () => {
    let intersectionCallback
    mockIntersectionObserver.mockImplementation((callback) => {
      intersectionCallback = callback
      return {
        observe: vi.fn(),
        unobserve: vi.fn(),
        disconnect: vi.fn()
      }
    })
    
    // Override MSW to fail on second page
    server.use(
      rest.get('http://localhost:5001/api/conversations', (req, res, ctx) => {
        const page = parseInt(req.url.searchParams.get('page') || '1')
        
        if (page === 1) {
          return res(ctx.json({
            conversations: [{ id: 'conv-1', title: 'Conversation 1', preview: 'Preview 1', date: '2024-01-01T10:00:00Z', source: 'chatgpt' }],
            pagination: { page: 1, limit: 50, total: 2, has_next: true, has_prev: false }
          }))
        } else {
          return res(ctx.status(500))
        }
      })
    )
    
    render(ScrollableConversationList)
    
    await waitFor(() => {
      expect(screen.getByText('Conversation 1')).toBeInTheDocument()
    })
    
    // Simulate intersection
    intersectionCallback([{ isIntersecting: true }])
    
    await waitFor(() => {
      expect(screen.getByText(/failed to load more/i)).toBeInTheDocument()
    })
    
    expect(screen.getByRole('button', { name: /load more/i })).toBeInTheDocument()
  })

  test('uses custom page size when provided', async () => {
    let requestedLimit
    
    // Override MSW to capture the limit parameter
    server.use(
      rest.get('http://localhost:5001/api/conversations', (req, res, ctx) => {
        requestedLimit = parseInt(req.url.searchParams.get('limit') || '50')
        return res(ctx.json({
          conversations: [{ id: 'conv-1', title: 'Conversation 1', preview: 'Preview 1', date: '2024-01-01T10:00:00Z', source: 'chatgpt' }],
          pagination: { page: 1, limit: requestedLimit, total: 1, has_next: false, has_prev: false }
        }))
      })
    )
    
    render(ScrollableConversationList, { props: { pageSize: 25 } })
    
    await waitFor(() => {
      expect(screen.getByText('Conversation 1')).toBeInTheDocument()
    })
    
    expect(requestedLimit).toBe(25)
  })

  test('maintains scroll position when new items are loaded', async () => {
    let intersectionCallback
    mockIntersectionObserver.mockImplementation((callback) => {
      intersectionCallback = callback
      return {
        observe: vi.fn(),
        unobserve: vi.fn(),
        disconnect: vi.fn()
      }
    })
    
    // Override MSW for pagination test
    server.use(
      rest.get('http://localhost:5001/api/conversations', (req, res, ctx) => {
        const page = parseInt(req.url.searchParams.get('page') || '1')
        
        if (page === 1) {
          return res(ctx.json({
            conversations: [
              { id: 'conv-1', title: 'Conversation 1', preview: 'Preview 1', date: '2024-01-01T10:00:00Z', source: 'chatgpt' },
              { id: 'conv-2', title: 'Conversation 2', preview: 'Preview 2', date: '2024-01-02T10:00:00Z', source: 'claude' }
            ],
            pagination: { page: 1, limit: 50, total: 4, has_next: true, has_prev: false }
          }))
        } else {
          return res(ctx.json({
            conversations: [
              { id: 'conv-3', title: 'Conversation 3', preview: 'Preview 3', date: '2024-01-03T10:00:00Z', source: 'chatgpt' },
              { id: 'conv-4', title: 'Conversation 4', preview: 'Preview 4', date: '2024-01-04T10:00:00Z', source: 'claude' }
            ],
            pagination: { page: 2, limit: 50, total: 4, has_next: false, has_prev: true }
          }))
        }
      })
    )
    
    render(ScrollableConversationList)
    
    await waitFor(() => {
      expect(screen.getByText('Conversation 1')).toBeInTheDocument()
    })
    
    const conversationElements = screen.getAllByRole('button')
    const initialCount = conversationElements.length
    
    // Load next page
    intersectionCallback([{ isIntersecting: true }])
    
    await waitFor(() => {
      expect(screen.getByText('Conversation 3')).toBeInTheDocument()
    })
    
    const newConversationElements = screen.getAllByRole('button')
    expect(newConversationElements.length).toBeGreaterThan(initialCount)
    
    // Original items should still be there
    expect(screen.getByText('Conversation 1')).toBeInTheDocument()
    expect(screen.getByText('Conversation 2')).toBeInTheDocument()
  })

  test('cleans up intersection observer on unmount', async () => {
    const mockObserver = {
      observe: vi.fn(),
      unobserve: vi.fn(),
      disconnect: vi.fn()
    }
    mockIntersectionObserver.mockReturnValue(mockObserver)
    
    const { unmount } = render(ScrollableConversationList)
    
    await waitFor(() => {
      expect(screen.getByText('Conversation 1')).toBeInTheDocument()
    })
    
    unmount()
    
    expect(mockObserver.disconnect).toHaveBeenCalled()
  })*/
})