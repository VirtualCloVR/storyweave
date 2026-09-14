import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CharacterLibrary, ThreadContextSettings } from '../StructuredContext'
import { ContextInspector } from '../ContextInspector'
import App from '../App'
import { WorkspaceProvider } from '../WorkspaceContext'
import type { ContextInspectorData, Project, Session, Thread } from '../types'

const character = { id: 'c1', name: '千早愛音', sourceTitle: 'MyGO', aliases: ['愛音'], facts: [{ id: 'f1', key: '身長', value: '160cm' }] }
const response = (value: unknown, status = 200) => new Response(status === 204 ? null : JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } })

afterEach(() => vi.unstubAllGlobals())

describe('Structured Context frontend', () => {
  it('keeps alias inputs mounted and focused while typing and composing Japanese', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response([character])))
    const user = userEvent.setup()
    render(<CharacterLibrary onClose={vi.fn()} />)
    await user.click(await screen.findByRole('button', { name: /千早愛音/ }))
    const existing = screen.getByRole('textbox', { name: 'Alias 1' })
    await user.type(existing, 'ちゃん')
    expect(existing).toHaveFocus()
    expect(existing).toHaveValue('愛音ちゃん')
    expect(screen.getByRole('textbox', { name: 'Alias 1' })).toBe(existing)

    await user.click(screen.getByRole('button', { name: 'Aliasを追加' }))
    const added = screen.getByRole('textbox', { name: 'Alias 2' })
    await user.type(added, 'Anon')
    expect(added).toHaveFocus()
    expect(added).toHaveValue('Anon')
    await user.clear(added)
    fireEvent.compositionStart(added)
    fireEvent.change(added, { target: { value: 'あのん' } })
    expect(added).toHaveFocus()
    fireEvent.compositionEnd(added, { data: '愛音' })
    fireEvent.change(added, { target: { value: '愛音' } })
    expect(screen.getByRole('textbox', { name: 'Alias 2' })).toBe(added)
    expect(added).toHaveFocus()
    expect(added).toHaveValue('愛音')
  })

  it('displays, filters, creates, and edits aliases/facts in Character Library', async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => { const url = String(input); calls.push({ url, init }); if (init?.method === 'POST') return response({ ...character, id: 'c2', name: '高松燈', aliases: ['燈'], facts: [{ key: '学年', value: '高等部1年' }] }); return response([character]) }))
    const user = userEvent.setup()
    render(<CharacterLibrary onClose={vi.fn()} />)
    expect(await screen.findByText('千早愛音')).toBeInTheDocument()
    await user.type(screen.getByRole('textbox', { name: 'Characterを検索' }), '愛音')
    expect(screen.getByText('千早愛音')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Characterを追加' }))
    await user.type(screen.getByLabelText('名前'), '高松燈')
    await user.click(screen.getByRole('button', { name: 'Aliasを追加' }))
    await user.type(screen.getByRole('textbox', { name: 'Alias 1' }), '燈')
    await user.click(screen.getByRole('button', { name: '項目を追加' }))
    await user.type(screen.getByRole('textbox', { name: 'Facts key 1' }), '学年')
    await user.type(screen.getByRole('textbox', { name: 'Facts value 1' }), '高等部1年')
    await user.click(screen.getByRole('button', { name: '保存' }))
    expect(calls.some((call) => call.init?.method === 'POST' && String(call.init.body).includes('高松燈'))).toBe(true)
  })

  it('adds cast members and toggles alwaysInclude, then saves scene facts', async () => {
    const second = { id: 'c2', name: '高松燈', sourceTitle: null, aliases: ['燈'], facts: [] }
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => { const url = String(input); if (url.includes('/threads/cast/characters')) return response([]); if (url.includes('/scene-facts')) return response([{ key: '舞台', value: '無人島' }]); if (url.endsWith('/characters')) return response([character, second]); if (init?.method === 'PUT') return response([]); return response([]) })
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    render(<ThreadContextSettings threadId="cast" onClose={vi.fn()} />)
    expect(await screen.findByText('高松燈')).toBeInTheDocument()
    await user.click(screen.getByRole('checkbox', { name: /高松燈/ }))
    await user.click(screen.getByRole('checkbox', { name: '常時参照' }))
    expect(screen.getByRole('checkbox', { name: '常時参照' })).toBeChecked()
    await user.click(screen.getByRole('button', { name: '項目を追加' }))
    const keys = screen.getAllByRole('textbox', { name: /Scene Facts key/ })
    const values = screen.getAllByRole('textbox', { name: /Scene Facts value/ })
    await user.type(keys[keys.length - 1], '季節')
    await user.type(values[values.length - 1], '夏')
    await user.click(screen.getByRole('button', { name: '保存' }))
    expect(fetcher.mock.calls.some((call) => call[1]?.method === 'PUT' && String(call[0]).includes('/threads/cast/characters'))).toBe(true)
    expect(fetcher.mock.calls.some((call) => call[1]?.method === 'PUT' && String(call[0]).includes('/threads/cast/scene-facts'))).toBe(true)
  })

  it('keeps settings scoped by thread id when switching the component', async () => {
    const seen: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => { const url = String(input); if (url.includes('/characters')) return response([]); if (url.includes('/scene-facts')) { seen.push(url); return response([]) } return response([]) }))
    const { rerender } = render(<ThreadContextSettings threadId="thread-a" onClose={vi.fn()} />)
    await screen.findByText('Cast')
    rerender(<ThreadContextSettings threadId="thread-b" onClose={vi.fn()} />)
    await screen.findByText('Cast')
    expect(seen.some((url) => url.includes('/threads/thread-a/scene-facts'))).toBe(true)
    expect(seen.some((url) => url.includes('/threads/thread-b/scene-facts'))).toBe(true)
  })

  it('shows v0.2 inspector character, scene, budget, digest, and degraded warning', () => {
    const project: Project = { id: 'p', title: 'P' }; const thread: Thread = { id: 't', projectId: 'p', title: 'T' }; const session: Session = { id: 's', threadId: 't', title: 'S', status: 'considering', archived: false, pinned: false }
    const data: ContextInspectorData = { project, thread, currentSession: session, adoptedSessions: [], excludedCounts: { considering: 0, rejected: 0, superseded: 0 }, confirmedContextChars: 300, currentHistoryChars: 100, budgetChars: 1000, totalChars: 800, mode: 'digest', includedCharacters: [{ character, reason: 'mentioned' }], sceneFacts: [{ key: '舞台', value: '無人島' }], canon: { digestStatus: 'fresh' }, sizes: { system: 80, characters: 120, scene: 40, canon: 300, history: 100, web: 0 }, compressionDegraded: true }
    render(<ContextInspector data={data} onClose={vi.fn()} />)
    const dialog = screen.getByRole('dialog', { name: '引き継がれる前提' })
    expect(within(dialog).getByText(/800 \/ 1,000 chars/)).toBeInTheDocument()
    expect(within(dialog).getByText('Digest + Relevant Canon')).toBeInTheDocument()
    expect(within(dialog).getByText('千早愛音')).toBeInTheDocument()
    expect(within(dialog).getByText(/舞台 = 無人島/)).toBeInTheDocument()
    expect(within(dialog).getByText('✓ fresh')).toBeInTheDocument()
    expect(within(dialog).getByRole('alert')).toHaveTextContent('一部の確定設定が省略')
  })

  it('provides Character and Thread Context entry points from the responsive workspace', async () => {
    const user = userEvent.setup()
    render(<WorkspaceProvider><App /></WorkspaceProvider>)
    expect(screen.getByRole('button', { name: 'Characters' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Characters' }))
    expect(await screen.findByRole('heading', { name: 'Characters' })).toBeInTheDocument()
  })
})
