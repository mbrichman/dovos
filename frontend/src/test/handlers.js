import { rest } from 'msw'

// Mock API handlers for testing
export const handlers = [
  // Mock search endpoint
  rest.get('http://localhost:5001/api/search', (req, res, ctx) => {
    const query = req.url.searchParams.get('q')
    
    if (!query) {
      return res(ctx.json({ results: [] }))
    }
    
    // Mock search results
    const mockResults = [
      {
        id: 'conv-1',
        title: 'Test Conversation 1',
        preview: 'This is a test conversation about ' + query,
        date: '2024-01-01',
        source: 'chatgpt'
      },
      {
        id: 'conv-2', 
        title: 'Another Test Chat',
        preview: 'More content related to ' + query,
        date: '2024-01-02',
        source: 'claude'
      }
    ]
    
    // Filter results based on query
    const filteredResults = mockResults.filter(result => 
      result.title.toLowerCase().includes(query.toLowerCase()) ||
      result.preview.toLowerCase().includes(query.toLowerCase())
    )
    
    return res(ctx.json({ results: filteredResults }))
  }),
  
  // Mock conversation detail endpoint
  rest.get('http://localhost:5001/api/conversation/:id', (req, res, ctx) => {
    return res(ctx.json({
      id: req.params.id,
      title: 'Mock Conversation',
      messages: [
        { role: 'user', content: 'Hello', timestamp: '2024-01-01T10:00:00Z' },
        { role: 'assistant', content: 'Hi there!', timestamp: '2024-01-01T10:00:01Z' }
      ],
      metadata: {
        source: 'chatgpt',
        date: '2024-01-01T10:00:00Z'
      }
    }))
  }),

  // Mock paginated conversations endpoint
  rest.get('http://localhost:5001/api/conversations', (req, res, ctx) => {
    console.log('🔧 MSW: Intercepted request to /api/conversations')
    console.log('🔧 MSW: URL:', req.url.toString())
    const page = parseInt(req.url.searchParams.get('page') || '1')
    const limit = parseInt(req.url.searchParams.get('limit') || '50')
    console.log('🔧 MSW: page:', page, 'limit:', limit)
    
    // Generate mock conversations
    const totalConversations = 150
    const startIndex = (page - 1) * limit
    const endIndex = Math.min(startIndex + limit, totalConversations)
    
    const conversations = []
    for (let i = startIndex; i < endIndex; i++) {
      conversations.push({
        id: `conv-${i + 1}`,
        title: `Conversation ${i + 1}`,
        preview: `This is conversation ${i + 1} content with some interesting details...`,
        date: `2024-01-${String((i % 28) + 1).padStart(2, '0')}T10:00:00Z`,
        source: i % 2 === 0 ? 'chatgpt' : 'claude'
      })
    }
    
    return res(ctx.json({
      conversations,
      pagination: {
        page,
        limit,
        total: totalConversations,
        has_next: endIndex < totalConversations,
        has_prev: page > 1
      }
    }))
  })
]