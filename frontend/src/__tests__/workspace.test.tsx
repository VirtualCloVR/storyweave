import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { WorkspaceProvider, useWorkspace } from '../WorkspaceContext'
import App from '../App'
import type { ApiClient, Project, Session, Thread } from '../types'

function UpdateHarness() {
  const { selectedSession, updateSession, connectionError } = useWorkspace()
  return <div><span data-testid="session-title">{selectedSession?.title}</span><button onClick={() => void updateSession({ title: '変更中' })}>更新</button>{connectionError && <span role="alert">{connectionError}</span>}</div>
}

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

  it('opens the adoption summary flow instead of directly adopting', async () => {
    const user = userEvent.setup()
    render(<WorkspaceProvider><App /></WorkspaceProvider>)
    const status = screen.getByRole('combobox', { name: 'Session status' }) as HTMLSelectElement
    await user.selectOptions(status, 'adopted')
    expect(await screen.findByRole('heading', { name: '採用内容を整理' })).toBeInTheDocument()
    expect(status.value).toBe('considering')
    await user.click(screen.getByRole('button', { name: /保存して採用にする/ }))
    expect(screen.getAllByText('採用').length).toBeGreaterThan(0)
  })

  it('clears the previous thread and session after creating an empty project', async () => {
    const user = userEvent.setup()
    render(<WorkspaceProvider><App /></WorkspaceProvider>)
    await user.click(screen.getAllByRole('button', { name: 'プロジェクトを追加' })[0])
    await user.type(screen.getByPlaceholderText('Projectの名前'), '空のProject')
    await user.click(screen.getByRole('button', { name: 'Projectを作成' }))
    expect(screen.getByText('Sessionを選択してください')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '病院での会話' })).not.toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: 'MyGO ワンライト' })[0])
    expect(screen.getByRole('heading', { name: '事故要素を入れるとして現実的な事故と表現' })).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: '空のProject' })[0])
    expect(screen.getByText('Sessionを選択してください')).toBeInTheDocument()
  })

  it('clears the previous session after creating an empty thread', async () => {
    const user = userEvent.setup()
    render(<WorkspaceProvider><App /></WorkspaceProvider>)
    await user.click(screen.getAllByRole('button', { name: 'スレッドを追加' })[0])
    await user.type(screen.getByPlaceholderText('Threadの名前'), '空のThread')
    await user.click(screen.getByRole('button', { name: 'Threadを作成' }))
    expect(screen.getByText('Sessionを選択してください')).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: /愛音事故SS/ })[0])
    expect(screen.getByRole('heading', { name: '事故要素を入れるとして現実的な事故と表現' })).toBeInTheDocument()
    await user.click(screen.getAllByRole('button', { name: /空のThread/ })[0])
    expect(screen.getByText('Sessionを選択してください')).toBeInTheDocument()
  })

  it('opens the parent session for a message search result', async () => {
    const user = userEvent.setup()
    render(<WorkspaceProvider><App /></WorkspaceProvider>)
    await user.click(screen.getByRole('button', { name: '検索' }))
    await user.type(screen.getByPlaceholderText('Project、Thread、Sessionを検索…'), '説明的')
    await user.click(screen.getByRole('button', { name: /message.*病院での会話/i }))
    expect(screen.getByRole('heading', { name: '病院での会話' })).toBeInTheDocument()
  })

  it('shows the confirmed context inspector', async () => {
    const user = userEvent.setup()
    render(<WorkspaceProvider><App /></WorkspaceProvider>)
    await user.click(screen.getByRole('button', { name: /採用済みSession.*内容を見る/ }))
    const dialog = await screen.findByRole('dialog', { name: '引き継がれる前提' })
    expect(within(dialog).getByText('事故要素を入れるとして現実的な事故と表現')).toBeInTheDocument()
    expect(within(dialog).getByText(/自動Contextから除外/)).toHaveTextContent('検討中 0 / 没 1 / 差し替え済み 1')
  })

  it('supports keyboard search selection and keeps source display', async () => {
    const user = userEvent.setup()
    render(<WorkspaceProvider><App /></WorkspaceProvider>)
    expect(screen.getByText('参照ソース')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '検索' }))
    const input = screen.getByPlaceholderText('Project、Thread、Sessionを検索…')
    await user.type(input, '記憶{Enter}')
    expect(screen.getByRole('heading', { name: '記憶喪失案' })).toBeInTheDocument()
  })

  it('opens the existing mobile drawer', async () => {
    const user = userEvent.setup()
    const { container } = render(<WorkspaceProvider><App /></WorkspaceProvider>)
    await user.click(screen.getAllByRole('button', { name: 'メニュー' })[0])
    expect(container.querySelector('.workspace-grid')).toHaveClass('drawer-open')
  })

  it('rolls back an optimistic session update when the API fails', async () => {
    const project: Project = { id: 'p', title: 'P' }
    const thread: Thread = { id: 't', projectId: 'p', title: 'T' }
    const session: Session = { id: 's', threadId: 't', title: '元の題名', status: 'considering', archived: false, pinned: false, adoptionSummary: null }
    const updateSession = vi.fn().mockRejectedValue(new Error('failed'))
    const client: ApiClient = {
      deleteProject: async () => {}, deleteThread: async () => {}, deleteSession: async () => {},
      getHealth: async () => ({ status: 'ok', database: 'ok', llm: 'unavailable', model: 'test' }),
      listProjects: async () => [project], createProject: async () => project,
      listThreads: async () => [thread], createThread: async () => thread,
      listSessions: async () => [session], createSession: async () => session,
      updateSession, listMessages: async () => [], sendChat: async () => ({ id: 'm', sessionId: 's', role: 'assistant', content: '' }),
      generateSummary: async () => ({ summary: '' }), saveSummary: async () => session,
      getContext: async () => ({ project, thread, currentSession: session, adoptedSessions: [], excludedCounts: { considering: 0, rejected: 0, superseded: 0 }, confirmedContextChars: 0, currentHistoryChars: 0 }),
      search: async () => [],
    }
    const user = userEvent.setup()
    render(<WorkspaceProvider client={client} sync><UpdateHarness /></WorkspaceProvider>)
    expect(await screen.findByTestId('session-title')).toHaveTextContent('元の題名')
    await user.click(screen.getByRole('button', { name: '更新' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Sessionの更新を保存できませんでした。')
    expect(screen.getByTestId('session-title')).toHaveTextContent('元の題名')
    expect(updateSession).toHaveBeenCalledWith('s', { title: '変更中' })
  })
})
