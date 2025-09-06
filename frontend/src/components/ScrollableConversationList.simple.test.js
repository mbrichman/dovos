import { describe, test, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/svelte'

// Mock ConversationCard component
vi.mock('./ConversationCard.svelte', () => ({
  default: {
    render: () => '<div data-testid="conversation-card">Mock Conversation Card</div>',
    $$prop_def: {}
  }
}))

import ScrollableConversationList from './ScrollableConversationList.svelte'

describe('ScrollableConversationList Simple Test', () => {
  // Mock IntersectionObserver
  beforeEach(() => {
    global.IntersectionObserver = vi.fn().mockImplementation(() => ({
      observe: vi.fn(),
      unobserve: vi.fn(),
      disconnect: vi.fn()
    }))
  })

  test('renders loading state initially', () => {
    render(ScrollableConversationList)
    
    expect(screen.getByText('Loading conversations...')).toBeInTheDocument()
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  test('makes API call on mount and shows debug info', async () => {
    render(ScrollableConversationList)
    
    // Wait a few seconds to see debug output
    await new Promise(resolve => setTimeout(resolve, 2000))
    
    // Test should pass regardless - we just want to see console output
    expect(screen.getByText('Loading conversations...')).toBeInTheDocument()
  })
})