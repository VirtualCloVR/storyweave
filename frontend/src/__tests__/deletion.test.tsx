import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { WorkspaceProvider, useWorkspace } from '../WorkspaceContext'
import { ProjectRail, SessionRail } from '../components'
import { createApiClient } from '../api'
import type { ApiClient, Session } from '../types'

const projects = [{ id: 'p1', title: '作品A' }, { id: 'p2', title: '作品B' }]
const threads = [{ id: 't1', projectId: 'p1', title: '章A' }, { id: 't2', projectId: 'p1', title: '章B' }, { id: 't3', projectId: 'p2', title: '別作品の章' }]
const sessions: Session[] = [
  { id: 's1', threadId: 't1', title: '採用した相談', status: 'adopted', adoptionSummary: '確定設定', archived: false, pinned: false },
  { id: 's2', threadId: 't1', title: '保管した相談', status: 'considering', archived: true, pinned: false },
  { id: 's3', threadId: 't2', title: '別の章の相談', status: 'considering', archived: false, pinned: false },
  { id: 's4', threadId: 't3', title: '別作品の相談', status: 'considering', archived: false, pinned: false },
]
function makeClient(): ApiClient {
  return {
    ...createApiClient(vi.fn(async () => { throw new Error('Unexpected request') })),
    getHealth: async () => ({ status: 'ok', database: 'ok', llm: 'ok', model: 'test' }),
    listProjects: async () => projects,
    listThreads: async (id) => threads.filter((item) => item.projectId === id),
    listSessions: async (id) => sessions.filter((item) => item.threadId === id),
    listMessages: async (id) => [{ id: 'm-' + id, sessionId: id, role: 'user', content: '保存済みの会話' }],
    deleteProject: vi.fn(async () => {}), deleteThread: vi.fn(async () => {}), deleteSession: vi.fn(async () => {}),
  }
}
function Probe() {
  const w = useWorkspace()
  return <div><output data-testid="counts">{w.projects.length}/{w.threads.length}/{w.sessions.length}</output><output data-testid="selected">{w.selectedProject?.id}/{w.selectedThread?.id}/{w.selectedSession?.id}</output>{w.messages.map((m) => <p key={m.id}>{m.content}</p>)}<button onClick={() => void w.sendMessage('生成確認')}>生成する</button></div>
}
function mount(client: ApiClient) {
  return render(<WorkspaceProvider client={client} sync><ProjectRail onCreateProject={vi.fn()} onCreateThread={vi.fn()} /><SessionRail onCreateSession={vi.fn()} /><Probe /></WorkspaceProvider>)
}

describe('Workspace hierarchy deletion', () => {
  it.each([
    ['project', 'Workspace', 'deleteProject', 'p1', '1/1/1', '//'],
    ['thread', 'Thread', 'deleteThread', 't1', '2/2/2', 'p1//'],
    ['session', 'Session', 'deleteSession', 's1', '2/3/3', 'p1/t1/'],
  ] as const)('confirms %s deletion and clears only the affected hierarchy after success', async (_kind, label, method, id, counts, selected) => {
    const client = makeClient()
    let resolve!: () => void
    client[method] = vi.fn(() => new Promise<void>((done) => { resolve = done }))
    const user = userEvent.setup()
    mount(client)
    await screen.findByText('保存済みの会話')
    await user.click(screen.getByRole('button', { name: '選択中の' + label + 'を削除' }))
    expect(screen.getByRole('alertdialog')).toHaveTextContent('この操作は取り消せません')
    expect(screen.getByRole('button', { name: 'キャンセル' })).toHaveFocus()
    expect(client[method]).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: '削除する' }))
    expect(client[method]).toHaveBeenCalledExactlyOnceWith(id)
    expect(screen.getByTestId('counts')).toHaveTextContent('2/3/4')
    expect(screen.getByText('保存済みの会話')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '削除中…' })).toBeDisabled()
    await act(async () => resolve())
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
    expect(screen.getByTestId('counts').textContent).toBe(counts)
    expect(screen.getByTestId('selected').textContent).toBe(selected)
    expect(screen.queryByText('保存済みの会話')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '作品B' }))
    expect(screen.getByRole('button', { name: /別作品の相談/ })).toBeInTheDocument()
  })

  it('counts archived descendants, cancels without a request, and keeps data on API failure', async () => {
    const client = makeClient()
    client.deleteThread = vi.fn().mockRejectedValue(new Error('offline'))
    const user = userEvent.setup()
    mount(client)
    await screen.findByText('保存済みの会話')
    const trigger = screen.getByRole('button', { name: '選択中のThreadを削除' })
    await user.click(trigger)
    expect(screen.getByRole('alertdialog')).toHaveTextContent('Session 2件')
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(trigger).toHaveFocus()
    expect(client.deleteThread).not.toHaveBeenCalled()
    await user.click(trigger)
    await user.click(screen.getByRole('button', { name: '削除する' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('削除できませんでした')
    expect(screen.getByTestId('counts')).toHaveTextContent('2/3/4')
    expect(screen.getByTestId('selected')).toHaveTextContent('p1/t1/s1')
    expect(screen.getByText('保存済みの会話')).toBeInTheDocument()
  })

  it('blocks deletion of a parent while its session is generating', async () => {
    const client = makeClient()
    let finish!: (value: Awaited<ReturnType<ApiClient['sendChat']>>) => void
    client.sendChat = vi.fn(() => new Promise<Awaited<ReturnType<ApiClient['sendChat']>>>((resolve) => { finish = resolve }))
    const user = userEvent.setup()
    mount(client)
    await screen.findByText('保存済みの会話')
    await user.click(screen.getByRole('button', { name: '生成する' }))
    await user.click(screen.getByRole('button', { name: '選択中のWorkspaceを削除' }))
    expect(screen.getByRole('button', { name: '削除する' })).toBeDisabled()
    expect(within(screen.getByRole('alertdialog')).getByRole('status')).toHaveTextContent('回答の生成が終わってから')
    expect(client.deleteProject).not.toHaveBeenCalled()
    await act(async () => finish({ id: 'done', sessionId: 's1', role: 'assistant', content: '回答' }))
    expect(screen.getByRole('button', { name: '削除する' })).toBeEnabled()
  })

  it('sends DELETE to each resource and accepts an empty 204 response', async () => {
    const fetcher = vi.fn(async () => new Response(null, { status: 204 }))
    const api = createApiClient(fetcher)
    await api.deleteProject('p1'); await api.deleteThread('t1'); await api.deleteSession('s1')
    expect(fetcher.mock.calls.map((call) => (call as unknown[])[0])).toEqual(['/api/projects/p1', '/api/threads/t1', '/api/sessions/s1'])
    for (const call of fetcher.mock.calls) expect((call as unknown[])[1]).toMatchObject({ method: 'DELETE' })
  })
})
