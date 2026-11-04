import '@testing-library/jest-dom'
import { vi } from 'vitest'

// Mock Tauri API without replacing the browser window global.
Object.defineProperty(window, '__TAURI__', {
  configurable: true,
  value: {
    invoke: vi.fn(),
  },
})
