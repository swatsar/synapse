import '@testing-library/jest-dom'

// Mock Tauri API
global.window = Object.create(window)
Object.defineProperty(window, '__TAURI__', {
  value: {
    invoke: jest.fn(),
  },
})
