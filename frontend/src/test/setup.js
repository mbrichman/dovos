import '@testing-library/jest-dom'

// Setup MSW (Mock Service Worker) for API mocking
import { setupServer } from 'msw/node'
import { handlers } from './handlers.js'

export const server = setupServer(...handlers)

// Start server before all tests
beforeAll(() => {
  console.log('🔧 MSW: Starting server with handlers for:', handlers.length, 'routes')
  server.listen({
    onUnhandledRequest: 'warn'
  })
  console.log('🔧 MSW: Server started')
})

// Reset handlers after each test
afterEach(() => {
  server.resetHandlers()
})

// Clean up after all tests
afterAll(() => {
  server.close()
})