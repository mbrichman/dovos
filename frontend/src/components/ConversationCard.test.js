import { render, screen, fireEvent } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import ConversationCard from './ConversationCard.svelte'

describe('ConversationCard', () => {
  const mockConversation = {
    id: 'conv-123',
    title: 'Test Conversation About React',
    preview: 'This is a conversation about React components and state management.',
    date: '2024-01-15T10:30:00Z',
    source: 'chatgpt'
  }

  test('renders conversation title', () => {
    render(ConversationCard, { conversation: mockConversation })
    
    expect(screen.getByText('Test Conversation About React')).toBeInTheDocument()
  })

  test('renders conversation preview text', () => {
    render(ConversationCard, { conversation: mockConversation })
    
    expect(screen.getByText(/This is a conversation about React components/)).toBeInTheDocument()
  })

  test('displays source badge', () => {
    render(ConversationCard, { conversation: mockConversation })
    
    expect(screen.getByText('ChatGPT')).toBeInTheDocument()
  })

  test('displays formatted date', () => {
    render(ConversationCard, { conversation: mockConversation })
    
    // Should display formatted date (not raw ISO string)
    expect(screen.queryByText('2024-01-15T10:30:00Z')).not.toBeInTheDocument()
    expect(screen.getByText(/Jan 15/)).toBeInTheDocument()
  })

  test('handles Claude source correctly', () => {
    const claudeConversation = { ...mockConversation, source: 'claude' }
    render(ConversationCard, { conversation: claudeConversation })
    
    expect(screen.getByText('Claude')).toBeInTheDocument()
  })

  test('is clickable and dispatches select event', async () => {
    const user = userEvent.setup()
    const mockSelectHandler = vi.fn()
    
    const { component } = render(ConversationCard, { conversation: mockConversation })
    component.$on('select', mockSelectHandler)
    
    const card = screen.getByRole('button')
    await user.click(card)
    
    expect(mockSelectHandler).toHaveBeenCalledWith(
      expect.objectContaining({
        detail: { conversation: mockConversation }
      })
    )
  })

  test('has hover effect styling', () => {
    render(ConversationCard, { conversation: mockConversation })
    
    const card = screen.getByRole('button')
    expect(card).toHaveClass('thread')
  })

  test('truncates long titles appropriately', () => {
    const longTitleConversation = {
      ...mockConversation,
      title: 'This is a very long conversation title that should be truncated because it exceeds reasonable length'
    }
    
    render(ConversationCard, { conversation: longTitleConversation })
    
    // Title should be present but styling should handle truncation
    expect(screen.getByText(/This is a very long conversation title/)).toBeInTheDocument()
  })

  test('handles missing preview gracefully', () => {
    const noPreviewConversation = { ...mockConversation, preview: '' }
    render(ConversationCard, { conversation: noPreviewConversation })
    
    // Should still render without crashing
    expect(screen.getByText('Test Conversation About React')).toBeInTheDocument()
  })
})