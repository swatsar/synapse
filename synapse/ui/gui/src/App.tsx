import React, { useState, useEffect } from 'react'
import { invoke } from '@tauri-apps/api/tauri'

// Types
interface ApiResponse {
  protocol_version: string
  spec_version: string
  success: boolean
  data?: any
  error?: string
}

interface SkillInfo {
  id: string
  name: string
  version: string
  status: string
  trust_level: string
  risk_level: number
  isolation_type: string
  required_capabilities: string[]
  created_at: string
  last_used?: string
}

interface SystemMetrics {
  cpu_percent: number
  memory_percent: number
  memory_used_mb: number
  memory_total_mb: number
  disk_percent: number
  uptime_seconds: number
}

// Components
const Sidebar: React.FC<{ activePage: string; onPageChange: (page: string) => void }> = ({ activePage, onPageChange }) => {
  const pages = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊' },
    { id: 'wizard', label: 'Setup Wizard', icon: '🧙' },
    { id: 'skills', label: 'Skills', icon: '🔧' },
    { id: 'security', label: 'Security', icon: '🔒' },
    { id: 'metrics', label: 'Metrics', icon: '📈' },
  ]

  return (
    <div className="sidebar">
      <div style={{ padding: '16px', borderBottom: '1px solid #E5E7EB' }}>
        <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>Synapse</h2>
        <p style={{ fontSize: '0.75rem', color: '#6B7280' }}>Configurator v3.1</p>
      </div>
      <nav style={{ padding: '8px 0' }}>
        {pages.map(page => (
          <div
            key={page.id}
            className={`sidebar-item ${activePage === page.id ? 'active' : ''}`}
            onClick={() => onPageChange(page.id)}
          >
            <span style={{ marginRight: '8px' }}>{page.icon}</span>
            {page.label}
          </div>
        ))}
      </nav>
    </div>
  )
}

const Dashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await invoke<ApiResponse>('get_system_metrics')
        if (response.success && response.data) {
          setMetrics(response.data)
        }
      } catch (error) {
        console.error('Failed to fetch metrics:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchMetrics()
  }, [])

  if (loading) return <div>Loading...</div>

  return (
    <div>
      <h1 style={{ marginBottom: '24px' }}>Dashboard</h1>
      
      <div className="grid grid-4" style={{ marginBottom: '24px' }}>
        <div className="card">
          <h4 style={{ color: '#6B7280', marginBottom: '8px' }}>CPU Usage</h4>
          <p style={{ fontSize: '2rem', fontWeight: 700 }}>{metrics?.cpu_percent.toFixed(1)}%</p>
        </div>
        <div className="card">
          <h4 style={{ color: '#6B7280', marginBottom: '8px' }}>Memory</h4>
          <p style={{ fontSize: '2rem', fontWeight: 700 }}>{metrics?.memory_percent.toFixed(1)}%</p>
        </div>
        <div className="card">
          <h4 style={{ color: '#6B7280', marginBottom: '8px' }}>Disk</h4>
          <p style={{ fontSize: '2rem', fontWeight: 700 }}>{metrics?.disk_percent.toFixed(1)}%</p>
        </div>
        <div className="card">
          <h4 style={{ color: '#6B7280', marginBottom: '8px' }}>Uptime</h4>
          <p style={{ fontSize: '1.5rem', fontWeight: 700 }}>
            {Math.floor((metrics?.uptime_seconds || 0) / 3600)}h
          </p>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginBottom: '16px' }}>System Status</h3>
        <div className="flex justify-between" style={{ marginBottom: '8px' }}>
          <span>Memory Used</span>
          <span>{metrics?.memory_used_mb} MB / {metrics?.memory_total_mb} MB</span>
        </div>
        <div style={{ background: '#E5E7EB', borderRadius: '4px', height: '8px' }}>
          <div 
            style={{ 
              background: '#2563EB', 
              borderRadius: '4px', 
              height: '100%',
              width: `${metrics?.memory_percent || 0}%`
            }} 
          />
        </div>
      </div>
    </div>
  )
}

const SkillsPage: React.FC = () => {
  const [skills, setSkills] = useState<SkillInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchSkills = async () => {
      try {
        const response = await invoke<ApiResponse>('get_skills')
        if (response.success && response.data) {
          setSkills(response.data)
        }
      } catch (error) {
        console.error('Failed to fetch skills:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchSkills()
  }, [])

  const handleApprove = async (skillId: string) => {
    try {
      await invoke<ApiResponse>('approve_skill', { skillId, approvedBy: 'gui-user' })
      // Refresh skills
      const response = await invoke<ApiResponse>('get_skills')
      if (response.success && response.data) {
        setSkills(response.data)
      }
    } catch (error) {
      console.error('Failed to approve skill:', error)
    }
  }

  const getStatusBadge = (status: string) => {
    const classes: Record<string, string> = {
      active: 'badge-success',
      pending: 'badge-warning',
      verified: 'badge-info',
      unverified: 'badge-warning',
    }
    return <span className={`badge ${classes[status] || 'badge-info'}`}>{status}</span>
  }

  const getRiskColor = (level: number) => {
    if (level <= 2) return 'risk-low'
    if (level <= 3) return 'risk-medium'
    return 'risk-high'
  }

  if (loading) return <div>Loading skills...</div>

  return (
    <div>
      <h1 style={{ marginBottom: '24px' }}>Skills Management</h1>
      
      <div className="card">
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #E5E7EB' }}>
              <th style={{ textAlign: 'left', padding: '12px' }}>Name</th>
              <th style={{ textAlign: 'left', padding: '12px' }}>Version</th>
              <th style={{ textAlign: 'left', padding: '12px' }}>Status</th>
              <th style={{ textAlign: 'left', padding: '12px' }}>Trust Level</th>
              <th style={{ textAlign: 'left', padding: '12px' }}>Risk</th>
              <th style={{ textAlign: 'left', padding: '12px' }}>Isolation</th>
              <th style={{ textAlign: 'left', padding: '12px' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {skills.map(skill => (
              <tr key={skill.id} style={{ borderBottom: '1px solid #E5E7EB' }}>
                <td style={{ padding: '12px', fontWeight: 500 }}>{skill.name}</td>
                <td style={{ padding: '12px' }}>{skill.version}</td>
                <td style={{ padding: '12px' }}>{getStatusBadge(skill.status)}</td>
                <td style={{ padding: '12px' }}>{skill.trust_level}</td>
                <td style={{ padding: '12px' }}>
                  <span className={getRiskColor(skill.risk_level)}>
                    Level {skill.risk_level}
                  </span>
                </td>
                <td style={{ padding: '12px' }}>{skill.isolation_type}</td>
                <td style={{ padding: '12px' }}>
                  {skill.status === 'pending' && (
                    <>
                      <button 
                        className="btn btn-success"
                        style={{ marginRight: '8px', padding: '4px 8px', fontSize: '0.75rem' }}
                        onClick={() => handleApprove(skill.id)}
                      >
                        Approve
                      </button>
                      <button 
                        className="btn btn-danger"
                        style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                      >
                        Reject
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const WizardPage: React.FC = () => {
  const [step, setStep] = useState(0)
  const [config, setConfig] = useState({
    language: 'en',
    llmProvider: 'openai',
    apiKey: '',
    model: 'gpt-4o',
    mode: 'supervised',
  })

  const steps = [
    { title: 'Welcome', description: 'Welcome to Synapse Configurator' },
    { title: 'Language', description: 'Select your preferred language' },
    { title: 'LLM Provider', description: 'Configure your LLM provider' },
    { title: 'Security Mode', description: 'Choose security settings' },
    { title: 'Review', description: 'Review your configuration' },
  ]

  return (
    <div>
      <h1 style={{ marginBottom: '24px' }}>Setup Wizard</h1>
      
      <div className="card" style={{ maxWidth: '600px', margin: '0 auto' }}>
        {/* Progress */}
        <div className="flex justify-between" style={{ marginBottom: '32px' }}>
          {steps.map((s, i) => (
            <div 
              key={i} 
              style={{ 
                textAlign: 'center',
                opacity: i <= step ? 1 : 0.5,
              }}
            >
              <div 
                style={{ 
                  width: '32px', 
                  height: '32px', 
                  borderRadius: '50%', 
                  background: i <= step ? '#2563EB' : '#E5E7EB',
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  margin: '0 auto 8px',
                }}
              >
                {i + 1}
              </div>
              <span style={{ fontSize: '0.75rem' }}>{s.title}</span>
            </div>
          ))}
        </div>

        {/* Content */}
        <div style={{ minHeight: '200px' }}>
          <h2 style={{ marginBottom: '8px' }}>{steps[step].title}</h2>
          <p style={{ color: '#6B7280', marginBottom: '24px' }}>{steps[step].description}</p>

          {step === 1 && (
            <div>
              <label className="label">Language</label>
              <select 
                className="input"
                value={config.language}
                onChange={(e) => setConfig({ ...config, language: e.target.value })}
              >
                <option value="en">English</option>
                <option value="ru">Русский</option>
              </select>
            </div>
          )}

          {step === 2 && (
            <div>
              <label className="label">LLM Provider</label>
              <select 
                className="input"
                value={config.llmProvider}
                onChange={(e) => setConfig({ ...config, llmProvider: e.target.value })}
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="ollama">Ollama (Local)</option>
              </select>
              
              <label className="label" style={{ marginTop: '16px' }}>API Key</label>
              <input 
                type="password"
                className="input"
                value={config.apiKey}
                onChange={(e) => setConfig({ ...config, apiKey: e.target.value })}
                placeholder="Enter your API key"
              />
            </div>
          )}

          {step === 3 && (
            <div>
              <label className="label">Security Mode</label>
              <select 
                className="input"
                value={config.mode}
                onChange={(e) => setConfig({ ...config, mode: e.target.value })}
              >
                <option value="safe">Safe - Maximum restrictions</option>
                <option value="supervised">Supervised - Human approval for risky actions</option>
                <option value="autonomous">Autonomous - Minimal restrictions</option>
              </select>
            </div>
          )}

          {step === 4 && (
            <div>
              <h4 style={{ marginBottom: '16px' }}>Configuration Summary</h4>
              <div style={{ background: '#F9FAFB', padding: '16px', borderRadius: '8px' }}>
                <p><strong>Language:</strong> {config.language}</p>
                <p><strong>LLM Provider:</strong> {config.llmProvider}</p>
                <p><strong>Model:</strong> {config.model}</p>
                <p><strong>Security Mode:</strong> {config.mode}</p>
              </div>
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="flex justify-between" style={{ marginTop: '32px' }}>
          <button 
            className="btn btn-secondary"
            onClick={() => setStep(Math.max(0, step - 1))}
            disabled={step === 0}
          >
            Previous
          </button>
          
          {step < steps.length - 1 ? (
            <button 
              className="btn btn-primary"
              onClick={() => setStep(step + 1)}
            >
              Next
            </button>
          ) : (
            <button className="btn btn-success">
              Apply Configuration
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

const SecurityPage: React.FC = () => {
  const [settings, setSettings] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await invoke<ApiResponse>('get_security_settings')
        if (response.success && response.data) {
          setSettings(response.data)
        }
      } catch (error) {
        console.error('Failed to fetch security settings:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchSettings()
  }, [])

  if (loading) return <div>Loading...</div>

  return (
    <div>
      <h1 style={{ marginBottom: '24px' }}>Security Settings</h1>
      
      <div className="grid grid-2">
        <div className="card">
          <h3 style={{ marginBottom: '16px' }}>Security Configuration</h3>
          <div style={{ marginBottom: '16px' }}>
            <label className="label">Require Approval for Risk Level</label>
            <input 
              type="number"
              className="input"
              value={settings?.require_approval_for_risk || 3}
              min={1}
              max={5}
            />
          </div>
          <div style={{ marginBottom: '16px' }}>
            <label className="label">Isolation Policy</label>
            <select className="input" value={settings?.isolation_policy || 'container'}>
              <option value="subprocess">Subprocess</option>
              <option value="container">Container</option>
            </select>
          </div>
          <div style={{ marginBottom: '16px' }}>
            <label className="label">Audit Enabled</label>
            <input 
              type="checkbox"
              checked={settings?.audit_enabled || false}
            />
          </div>
          <button className="btn btn-primary">Save Settings</button>
        </div>

        <div className="card">
          <h3 style={{ marginBottom: '16px' }}>Trusted Users</h3>
          <p style={{ color: '#6B7280', marginBottom: '16px' }}>
            Users with elevated permissions
          </p>
          <div style={{ background: '#F9FAFB', padding: '16px', borderRadius: '8px' }}>
            <p style={{ color: '#6B7280' }}>No trusted users configured</p>
          </div>
          <button className="btn btn-secondary" style={{ marginTop: '16px' }}>
            Add Trusted User
          </button>
        </div>
      </div>
    </div>
  )
}

const MetricsPage: React.FC = () => {
  const [llmUsage, setLlmUsage] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchUsage = async () => {
      try {
        const response = await invoke<ApiResponse>('get_llm_usage')
        if (response.success && response.data) {
          setLlmUsage(response.data)
        }
      } catch (error) {
        console.error('Failed to fetch LLM usage:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchUsage()
  }, [])

  if (loading) return <div>Loading...</div>

  return (
    <div>
      <h1 style={{ marginBottom: '24px' }}>Metrics & Usage</h1>
      
      <div className="grid grid-3" style={{ marginBottom: '24px' }}>
        <div className="card">
          <h4 style={{ color: '#6B7280', marginBottom: '8px' }}>Total Tokens</h4>
          <p style={{ fontSize: '2rem', fontWeight: 700 }}>
            {llmUsage?.total_tokens?.toLocaleString() || 0}
          </p>
        </div>
        <div className="card">
          <h4 style={{ color: '#6B7280', marginBottom: '8px' }}>Prompt Tokens</h4>
          <p style={{ fontSize: '2rem', fontWeight: 700 }}>
            {llmUsage?.prompt_tokens?.toLocaleString() || 0}
          </p>
        </div>
        <div className="card">
          <h4 style={{ color: '#6B7280', marginBottom: '8px' }}>Completion Tokens</h4>
          <p style={{ fontSize: '2rem', fontWeight: 700 }}>
            {llmUsage?.completion_tokens?.toLocaleString() || 0}
          </p>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginBottom: '16px' }}>Estimated Cost</h3>
        <p style={{ fontSize: '3rem', fontWeight: 700, color: '#2563EB' }}>
          ${llmUsage?.estimated_cost_usd?.toFixed(2) || '0.00'}
        </p>
      </div>
    </div>
  )
}

// Main App
const App: React.FC = () => {
  const [activePage, setActivePage] = useState('dashboard')

  const renderPage = () => {
    switch (activePage) {
      case 'dashboard': return <Dashboard />
      case 'wizard': return <WizardPage />
      case 'skills': return <SkillsPage />
      case 'security': return <SecurityPage />
      case 'metrics': return <MetricsPage />
      default: return <Dashboard />
    }
  }

  return (
    <div style={{ minHeight: '100vh' }}>
      <Sidebar activePage={activePage} onPageChange={setActivePage} />
      <main className="main-content">
        {renderPage()}
      </main>
      <div className="protocol-badge">
        protocol_version: 1.0 | spec_version: 3.1
      </div>
    </div>
  )
}

export default App
