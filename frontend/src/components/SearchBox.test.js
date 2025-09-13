import { render, screen, fireEvent, waitFor } from '@testing-library/svelte'
import userEvent from '@testing-library/user-event'
import SearchBox from './SearchBox.svelte'

describe('SearchBox', () => {
  test('renders search input with placeholder', () => {
    render(SearchBox)
    
    const input = screen.getByPlaceholderText('Search conversations')
    expect(input).toBeInTheDocument()
  })
  
  test('shows loading state during search', async () => {
    const user = userEvent.setup()
    render(SearchBox)
    
    const input = screen.getByPlaceholderText('Search conversations')
    
    // Start typing
    await user.type(input, 'test query')
    
    // Should show loading indicator
    expect(screen.getByText('Searching...')).toBeInTheDocument()
  })
  
  test('dispatches search event with query', async () => {
    const user = userEvent.setup()
    const mockSearchHandler = vi.fn()
    
    const { component } = render(SearchBox)
    component.$on('search', mockSearchHandler)
    
    const input = screen.getByPlaceholderText('Search conversations')
    
    await user.type(input, 'test query')
    
    // Wait for debounced search
    await waitFor(() => {
      expect(mockSearchHandler).toHaveBeenCalledWith(
        expect.objectContaining({
          detail: { query: 'test query' }
        })
      )
    }, { timeout: 1000 })
  })
  
  test('clears search when clear button is clicked', async () => {
    const user = userEvent.setup()
    render(SearchBox)
    
    const input = screen.getByPlaceholderText('Search conversations')
    
    // Type something first
    await user.type(input, 'test')
    expect(input.value).toBe('test')
    
    // Click clear button
    const clearButton = screen.getByRole('button', { name: /clear/i })
    await user.click(clearButton)
    
    expect(input.value).toBe('')
  })
  
  test('does not search for empty queries', async () => {
    const user = userEvent.setup()
    const mockSearchHandler = vi.fn()
    
    const { component } = render(SearchBox)
    component.$on('search', mockSearchHandler)
    
    const input = screen.getByPlaceholderText('Search conversations')
    
    // Type and then clear
    await user.type(input, 'test')
    await user.clear(input)
    
    await waitFor(() => {
      // Should not have called search with empty query
      expect(mockSearchHandler).not.toHaveBeenCalledWith(
        expect.objectContaining({
          detail: { query: '' }
        })
      )
    })
  })
})