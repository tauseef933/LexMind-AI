import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import AgentTrace from './AgentTrace'

describe('AgentTrace', () => {
  it('shows live agent status while streaming', () => {
    render(
      <AgentTrace
        isStreaming
        steps={[
          { agent: 'orchestrator', status: 'done' },
          { agent: 'document_agent', status: 'running' },
          { agent: 'research_agent', status: 'error' },
        ]}
      />,
    )
    expect(screen.getByText('Document Agent')).toBeInTheDocument()
    expect(screen.getByLabelText('running')).toBeInTheDocument()
    expect(screen.getByLabelText('error')).toBeInTheDocument()
  })

  it('says it is choosing agents while routing', () => {
    render(<AgentTrace isStreaming steps={[{ agent: 'orchestrator', status: 'routing' }]} />)
    expect(screen.getByText('Choosing agents')).toBeInTheDocument()
  })

  it('renders nothing once the answer is finished', () => {
    const { container } = render(
      <AgentTrace isStreaming={false} steps={[{ agent: 'document_agent', status: 'done' }]} />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
