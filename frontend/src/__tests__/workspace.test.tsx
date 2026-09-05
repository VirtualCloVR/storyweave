import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { WorkspaceProvider } from '../WorkspaceContext'
import App from '../App'

describe('Storyweave workspace', () => {
  it('renders the three-pane workspace with the current session', () => {
    render(<WorkspaceProvider><App /></WorkspaceProvider>)
    expect(screen.getAllByText('storyweave').length).toBeGreaterThan(0)
    expect(screen.getAllByText('病院での会話').length).toBeGreaterThan(0)
    expect(screen.getByPlaceholderText('このSessionについて相談する…')).toBeInTheDocument()
  })

  it('opens the search dialog and filters sessions', async () => {
    const user = userEvent.setup()
    render(<WorkspaceProvider><App /></WorkspaceProvider>)
    await user.click(screen.getByRole('button', { name: '検索' }))
    const input = screen.getByPlaceholderText('Project、Thread、Sessionを検索…')
    await user.type(input, '記憶')
    expect(screen.getByText('記憶喪失案')).toBeInTheDocument()
  })

  it('changes session status from the chat header', async () => {
    const user = userEvent.setup()
    render(<WorkspaceProvider><App /></WorkspaceProvider>)
    await user.selectOptions(screen.getByRole('combobox', { name: 'Session status' }), 'adopted')
    expect(screen.getAllByText('採用').length).toBeGreaterThan(0)
  })
})
