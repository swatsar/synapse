import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import App from '../App'

// Mock Tauri invoke
const mockInvoke = vi.fn()
vi.mock('@tauri-apps/api/tauri', () => ({
  invoke: (cmd: string, args?: any) => mockInvoke(cmd, args),
}))

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    
    // Default mock responses
    mockInvoke.mockImplementation(async (cmd: string) => {
      switch (cmd) {
        case 'get_system_metrics':
          return {
            protocol_version: '1.0',
            spec_version: '3.1',
            success: true,
            data: {
              cpu_percent: 25.5,
              memory_percent: 45.2,
              memory_used_mb: 1843,
              memory_total_mb: 4096,
              disk_percent: 35.0,
              uptime_seconds: 86400,
            },
          }
        case 'get_skills':
          return {
            protocol_version: '1.0',
            spec_version: '3.1',
            success: true,
            data: [
              {
                id: 'skill-001',
                name: 'read_file',
                version: '1.0.0',
                status: 'active',
                trust_level: 'trusted',
                risk_level: 1,
                isolation_type: 'subprocess',
                required_capabilities: ['fs:read'],
                created_at: '2026-02-20T00:00:00Z',
              },
            ],
          }
        case 'get_security_settings':
          return {
            protocol_version: '1.0',
            spec_version: '3.1',
            success: true,
            data: {
              require_approval_for_risk: 3,
              isolation_policy: 'container',
              audit_enabled: true,
            },
          }
        case 'get_llm_usage':
          return {
            protocol_version: '1.0',
            spec_version: '3.1',
            success: true,
            data: {
              total_tokens: 100000,
              prompt_tokens: 60000,
              completion_tokens: 40000,
              estimated_cost_usd: 1.25,
            },
          }
        default:
          return {
            protocol_version: '1.0',
            spec_version: '3.1',
            success: true,
            data: null,
          }
      }
    })
  })

  it('renders the app with sidebar', () => {
    render(<App />)
    expect(screen.getByText('Synapse')).toBeInTheDocument()
    expect(screen.getByText('Configurator v3.1')).toBeInTheDocument()
  })

  it('displays protocol version badge', () => {
    render(<App />)
    expect(screen.getByText(/protocol_version: 1.0/)).toBeInTheDocument()
  })

  it('shows dashboard by default', async () => {
    render(<App />)
    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
    })
  })

  it('navigates to skills page', async () => {
    render(<App />)
    
    // Click on Skills in sidebar
    fireEvent.click(screen.getByText('Skills'))
    
    await waitFor(() => {
      expect(screen.getByText('Skills Management')).toBeInTheDocument()
    })
  })

  it('navigates to wizard page', async () => {
    render(<App />)
    
    fireEvent.click(screen.getByText('Setup Wizard'))
    
    await waitFor(() => {
      expect(screen.getByText('Setup Wizard')).toBeInTheDocument()
    })
  })

  it('navigates to security page', async () => {
    render(<App />)
    
    fireEvent.click(screen.getByText('Security'))
    
    await waitFor(() => {
      expect(screen.getByText('Security Settings')).toBeInTheDocument()
    })
  })

  it('navigates to metrics page', async () => {
    render(<App />)
    
    fireEvent.click(screen.getByText('Metrics'))
    
    await waitFor(() => {
      expect(screen.getByText('Metrics & Usage')).toBeInTheDocument()
    })
  })
})

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays system metrics', async () => {
    mockInvoke.mockResolvedValueOnce({
      protocol_version: '1.0',
      spec_version: '3.1',
      success: true,
      data: {
        cpu_percent: 25.5,
        memory_percent: 45.2,
        memory_used_mb: 1843,
        memory_total_mb: 4096,
        disk_percent: 35.0,
        uptime_seconds: 86400,
      },
    })

    render(<App />)
    
    await waitFor(() => {
      expect(screen.getByText('25.5%')).toBeInTheDocument()
      expect(screen.getByText('45.2%')).toBeInTheDocument()
    })
  })

  it('calls get_system_metrics on mount', async () => {
    render(<App />)
    
    await waitFor(() => {
      expect(mockInvoke).toHaveBeenCalledWith('get_system_metrics')
    })
  })
})

describe('Skills Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays skills list', async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === 'get_skills') {
        return {
          protocol_version: '1.0',
          spec_version: '3.1',
          success: true,
          data: [
            {
              id: 'skill-001',
              name: 'read_file',
              version: '1.0.0',
              status: 'active',
              trust_level: 'trusted',
              risk_level: 1,
              isolation_type: 'subprocess',
              required_capabilities: ['fs:read'],
              created_at: '2026-02-20T00:00:00Z',
            },
            {
              id: 'skill-002',
              name: 'write_file',
              version: '1.0.0',
              status: 'pending',
              trust_level: 'unverified',
              risk_level: 3,
              isolation_type: 'container',
              required_capabilities: ['fs:write'],
              created_at: '2026-02-20T00:00:00Z',
            },
          ],
        }
      }
      return { protocol_version: '1.0', success: true, data: null }
    })

    render(<App />)
    fireEvent.click(screen.getByText('Skills'))
    
    await waitFor(() => {
      expect(screen.getByText('read_file')).toBeInTheDocument()
      expect(screen.getByText('write_file')).toBeInTheDocument()
    })
  })

  it('shows approve button for pending skills', async () => {
    mockInvoke.mockImplementation(async (cmd: string) => {
      if (cmd === 'get_skills') {
        return {
          protocol_version: '1.0',
          spec_version: '3.1',
          success: true,
          data: [
            {
              id: 'skill-002',
              name: 'write_file',
              version: '1.0.0',
              status: 'pending',
              trust_level: 'unverified',
              risk_level: 3,
              isolation_type: 'container',
              required_capabilities: ['fs:write'],
              created_at: '2026-02-20T00:00:00Z',
            },
          ],
        }
      }
      return { protocol_version: '1.0', success: true, data: null }
    })

    render(<App />)
    fireEvent.click(screen.getByText('Skills'))
    
    await waitFor(() => {
      expect(screen.getByText('Approve')).toBeInTheDocument()
      expect(screen.getByText('Reject')).toBeInTheDocument()
    })
  })
})

describe('Wizard Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays wizard steps', async () => {
    render(<App />)
    fireEvent.click(screen.getByText('Setup Wizard'))
    
    await waitFor(() => {
      expect(screen.getByText('Welcome')).toBeInTheDocument()
      expect(screen.getByText('Language')).toBeInTheDocument()
      expect(screen.getByText('LLM Provider')).toBeInTheDocument()
    })
  })

  it('navigates through wizard steps', async () => {
    render(<App />)
    fireEvent.click(screen.getByText('Setup Wizard'))
    
    await waitFor(() => {
      expect(screen.getByText('Welcome to Synapse Configurator')).toBeInTheDocument()
    })

    // Click Next
    fireEvent.click(screen.getByText('Next'))
    
    await waitFor(() => {
      expect(screen.getByText('Select your preferred language')).toBeInTheDocument()
    })
  })
})
