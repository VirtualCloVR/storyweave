import { useEffect, useMemo, useRef, useState } from 'react'
import { useWorkspace } from './WorkspaceContext'
import { ArchiveIcon, ChevronIcon, CheckIcon, CloseIcon, MenuIcon, PinIcon, PlusIcon, SearchIcon, SendIcon, SparkleIcon, SunIcon } from './icons'
import { Markdown } from './Markdown'
import { ContextInspector } from './ContextInspector'
import { createApiClient } from './api'
import type { ContextInspectorData, Message, SearchResult, Session, SessionStatus, Source } from './types'
import { ThreadContextSettings } from './StructuredContext'
import { DeleteAction } from './DeleteAction'

const statusMeta: Record<SessionStatus, { icon: string; label: string; className: string }> = {
  adopted: { icon: '✓', label: '採用', className: 'status-adopted' },
  considering: { icon: '○', label: '検討中', className: 'status-considering' },
  rejected: { icon: '×', label: '没', className: 'status-rejected' },
  superseded: { icon: '↪', label: '差し替え済み', className: 'status-superseded' },
}
const searchApi = createApiClient()

export function StatusBadge({ status, compact = false }: { status: SessionStatus; compact?: boolean }) {
  const meta = statusMeta[status]
  return <span className={`status-badge ${meta.className} ${compact ? 'compact' : ''}`}><span>{meta.icon}</span>{meta.label}</span>
}

function messageSources(message: Message): Source[] {
  const metadataSources = message.metadata && typeof message.metadata === 'object' ? message.metadata.sources ?? message.metadata.references : undefined
  const values = message.sources ?? message.references ?? (Array.isArray(metadataSources) ? metadataSources : [])
  return values.filter((source): source is Source => Boolean(source && typeof source.url === 'string' && /^https?:\/\//i.test(source.url)))
}

export function MessageSources({ message }: { message: Message }) {
  const sources = messageSources(message)
  if (!sources.length) return null
  return <details className="message-sources"><summary>参照ソース <span>{sources.length}</span></summary><div className="source-list">{sources.map((source, index) => <a className="source-item" href={source.url} target="_blank" rel="noreferrer" key={source.id ?? `${source.url}-${index}`}><span className="source-item-heading"><span className="source-item-title">{source.title || source.url}</span>{source.provider && <span className="source-provider">{source.provider}</span>}</span>{source.excerpt && <span className="source-item-excerpt">{source.excerpt.slice(0, 240)}</span>}<span className="source-item-url">{source.url}</span></a>)}</div></details>
}

export function Topbar({ onMenu, onSearch, onTheme, onCharacters }: { onMenu: () => void; onSearch: () => void; onTheme: () => void; onCharacters?: () => void }) {
  const { selectedProject, selectedThread, selectedSession } = useWorkspace()
  return <header className="topbar">
    <div className="topbar-mobile"><button className="icon-button" aria-label="メニュー" onClick={onMenu}><MenuIcon /></button></div>
    <div className="brand"><span className="brand-mark">✦</span><span>storyweave</span></div>
    <div className="breadcrumbs"><span>{selectedProject?.title}</span><span className="breadcrumb-slash">/</span><span>{selectedThread?.title}</span><span className="breadcrumb-slash">/</span><span className="breadcrumb-current">{selectedSession?.title}</span></div>
    <div className="topbar-actions"><button className="library-topbar-button" onClick={onCharacters}>Characters</button><button className="icon-button" aria-label="検索" onClick={onSearch}><SearchIcon /></button><button className="icon-button" aria-label="テーマ切替" onClick={onTheme}><SunIcon /></button><span className="avatar">創</span></div>
  </header>
}

function AddButton({ label, onClick }: { label: string; onClick: () => void }) { return <button className="text-button" onClick={onClick}><PlusIcon size={15} />{label}</button> }

export function ProjectRail({ onCreateProject, onCreateThread }: { onCreateProject: () => void; onCreateThread: () => void }) {
  const { projects, threads, selectedProject, selectedThread, selectProject, selectThread, health, connectionError } = useWorkspace()
  const projectThreads = threads.filter((item) => item.projectId === selectedProject?.id)
  return <aside className="project-rail panel-scroll">
    <div className="rail-heading"><span>WORKSPACE</span><div className="rail-heading-actions"><DeleteAction kind="project" item={selectedProject} /><button className="mini-button" aria-label="プロジェクトを追加" onClick={onCreateProject}><PlusIcon size={15} /></button></div></div>
    <div className="project-list">{projects.map((project) => <button key={project.id} className={`project-item ${project.id === selectedProject?.id ? 'selected' : ''}`} onClick={() => selectProject(project.id)}><span className="project-dot" />{project.title}</button>)}</div>
    <div className="rail-divider" />
    <div className="rail-heading"><span>THREADS</span><div className="rail-heading-actions"><DeleteAction kind="thread" item={selectedThread} /><button className="mini-button" aria-label="スレッドを追加" onClick={onCreateThread}><PlusIcon size={15} /></button></div></div>
    <div className="thread-list">{projectThreads.map((thread) => <button key={thread.id} className={`thread-item ${thread.id === selectedThread?.id ? 'selected' : ''}`} onClick={() => selectThread(thread.id)}><span className="thread-icon">◌</span><span>{thread.title}</span></button>)}</div>
    <div className={`rail-footer ${connectionError || health?.database === 'unavailable' ? 'connection-error' : ''}`} title={connectionError ?? `Database: ${health?.database ?? 'checking'} / LLM: ${health?.llm ?? 'checking'}`}><span className="connection-dot" /><span>{connectionError ? 'Backend再接続中' : health ? `${health.model || 'LLM未設定'} ${health.llm === 'ok' ? '●' : '○'}` : '状態を確認中'}</span></div>
  </aside>
}

function sortSessions(items: Session[]) { return [...items].sort((a, b) => Number(b.pinned) - Number(a.pinned) || Number(a.status !== 'adopted') - Number(b.status !== 'adopted') || (a.updatedAt ?? '').localeCompare(b.updatedAt ?? '')) }

export function SessionRail({ onCreateSession }: { onCreateSession: () => void }) {
  const { sessions, selectedThread, selectedSession, selectSession, updateSession } = useWorkspace()
  const [showOther, setShowOther] = useState(false)
  const [showArchived, setShowArchived] = useState(false)
  const active = sortSessions(sessions.filter((item) => item.threadId === selectedThread?.id && !item.archived))
  const archived = sessions.filter((item) => item.threadId === selectedThread?.id && item.archived)
  const grouped = { pinned: active.filter((item) => item.pinned), adopted: active.filter((item) => !item.pinned && item.status === 'adopted'), considering: active.filter((item) => !item.pinned && item.status === 'considering'), other: active.filter((item) => !item.pinned && (item.status === 'rejected' || item.status === 'superseded')) }
  const renderSession = (session: Session) => <button key={session.id} className={`session-item ${session.id === selectedSession?.id ? 'selected' : ''} ${session.status === 'rejected' || session.status === 'superseded' ? 'muted' : ''}`} onClick={() => selectSession(session.id)}><span className={`session-status-dot ${statusMeta[session.status].className}`} /> <span className="session-item-main"><span className="session-title">{session.title}</span><span className="session-meta"><StatusBadge status={session.status} compact />{session.pinned && <PinIcon size={12} />}</span></span></button>
  return <aside className="session-rail panel-scroll">
    <div className="rail-heading session-heading"><span>SESSIONS</span><div className="rail-heading-actions"><DeleteAction kind="session" item={selectedSession} /><button className="mini-button" aria-label="Sessionを追加" onClick={onCreateSession}><PlusIcon size={15} /></button></div></div>
    {grouped.pinned.length > 0 && <section className="session-group"><h3><span>Pin</span><span className="group-count">{grouped.pinned.length}</span></h3>{grouped.pinned.map(renderSession)}</section>}
    {grouped.adopted.length > 0 && <section className="session-group"><h3><span>採用</span><span className="group-count">{grouped.adopted.length}</span></h3>{grouped.adopted.map(renderSession)}</section>}
    {grouped.considering.length > 0 && <section className="session-group"><h3><span>検討中</span><span className="group-count">{grouped.considering.length}</span></h3>{grouped.considering.map(renderSession)}</section>}
    {grouped.other.length > 0 && <section className="session-group"><button className="collapsible-heading" onClick={() => setShowOther((value) => !value)}><ChevronIcon size={15} /><span>没・差し替え済み</span><span className="group-count">{grouped.other.length}</span></button>{showOther && grouped.other.map(renderSession)}</section>}
    {archived.length > 0 && <section className="session-group archive-group"><button className="collapsible-heading" onClick={() => setShowArchived((value) => !value)}><ArchiveIcon size={14} /><span>Archive</span><span className="group-count">{archived.length}</span></button>{showArchived && archived.map(renderSession)}</section>}
    {active.length === 0 && <div className="empty-state small">このThreadにはSessionがありません。<button className="inline-link" onClick={onCreateSession}>最初のSessionを作る</button></div>}
    <div className="session-rail-footer"><button className="text-button" onClick={onCreateSession}><PlusIcon size={15} />新しいSession</button><span>{active.length} active</span></div>
  </aside>
}

export function ChatPanel({ onMenu }: { onMenu: () => void }) {
  const { selectedSession, selectedThread, messages, updateSession, sendMessage, generateSummary, saveSummary, loadContext, connectionError } = useWorkspace()
  const [draft, setDraft] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [streamingText, setStreamingText] = useState('')
  const [summaryOpen, setSummaryOpen] = useState(false)
  const [summaryDraft, setSummaryDraft] = useState('')
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [contextData, setContextData] = useState<ContextInspectorData>()
  const [contextLoading, setContextLoading] = useState(false)
  const [contextError, setContextError] = useState('')
  const [threadSettingsOpen, setThreadSettingsOpen] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => { bottomRef.current?.scrollIntoView?.({ behavior: 'smooth' }) }, [messages, streamingText])
  useEffect(() => { setStreamingText(''); setDraft(''); setSummaryOpen(false); setContextData(undefined); setContextError('') }, [selectedSession?.id])
  if (!selectedSession) return <main className="chat-panel"><div className="empty-state">Sessionを選択してください</div></main>
  const submit = async () => {
    if (!draft.trim() || isSending) return
    const text = draft; setDraft(''); setIsSending(true); setStreamingText('')
    try { await sendMessage(text, (token) => setStreamingText((value) => value + token)) } finally { setIsSending(false); setStreamingText('') }
  }
  const openSummary = async () => {
    setSummaryOpen(true)
    setSummaryDraft(selectedSession.adoptionSummary ?? '')
    if (selectedSession.adoptionSummary?.trim()) return
    setSummaryLoading(true)
    try { setSummaryDraft(await generateSummary()) } finally { setSummaryLoading(false) }
  }
  const save = async () => { if (!summaryDraft.trim()) return; try { await saveSummary(summaryDraft.trim()); setSummaryOpen(false) } catch { /* error remains visible in the workspace */ } }
  const changeStatus = (status: SessionStatus) => {
    if (status === 'adopted' && !selectedSession.adoptionSummary?.trim()) void openSummary()
    else void updateSession({ status })
  }
  const openContext = async () => {
    setContextLoading(true); setContextError('')
    try { setContextData(await loadContext()) } catch { setContextError('Contextを取得できませんでした。') } finally { setContextLoading(false) }
  }
  return <main className="chat-panel">
    <div className="chat-header"><div className="chat-header-title"><button className="mobile-only icon-button" onClick={onMenu} aria-label="メニュー"><MenuIcon /></button><div><h1>{selectedSession.title}</h1><div className="chat-header-sub"><StatusBadge status={selectedSession.status} /><span>Session · このThreadの採用内容がContextに反映されます</span></div></div></div><div className="chat-header-actions"><button className="thread-settings-button" onClick={() => setThreadSettingsOpen(true)} disabled={!selectedThread} aria-label="Thread Context設定">Context</button><button className={`icon-button ${selectedSession.pinned ? 'active' : ''}`} aria-label="ピン留め" onClick={() => void updateSession({ pinned: !selectedSession.pinned })}><PinIcon /></button><button className={`icon-button ${selectedSession.archived ? 'active' : ''}`} aria-label="アーカイブ" onClick={() => void updateSession({ archived: !selectedSession.archived })}><ArchiveIcon /></button><select className="status-select" aria-label="Session status" value={selectedSession.status} onChange={(event) => changeStatus(event.target.value as SessionStatus)}>{Object.entries(statusMeta).map(([value, meta]) => <option key={value} value={value}>{meta.icon} {meta.label}</option>)}</select></div></div>
    <div className="chat-content panel-scroll">{connectionError && <div className="error-note" role="alert">{connectionError}</div>}{contextError && <div className="error-note" role="alert">{contextError}</div>}<button className="context-note" onClick={() => void openContext()} disabled={contextLoading}><span className="context-note-icon">✦</span><span>同じThreadの<strong>採用済みSession</strong>が、この相談の前提として自動で引き継がれています。{contextLoading ? '確認中…' : ' 内容を見る'}</span></button>{messages.map((message) => <article key={message.id} className={`message ${message.role}`}><div className="message-avatar">{message.role === 'user' ? '創' : '✦'}</div><div className="message-body"><div className="message-role">{message.role === 'user' ? 'あなた' : 'storyweave'}<span className="message-time">{message.createdAt ? new Date(message.createdAt).toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit' }) : ''}</span></div><div className="message-content"><Markdown content={message.content} />{message.metadata?.generation_status === 'interrupted' && <p className="interrupted-note">生成が途中で中断されました</p>}<MessageSources message={message} /></div></div></article>)}{streamingText && <article className="message assistant"><div className="message-avatar">✦</div><div className="message-body"><div className="message-role">storyweave<span className="typing-dot" /></div><div className="message-content"><Markdown content={streamingText} /></div></div></article>}{isSending && !streamingText && <div className="thinking"><span /><span /><span /> 考えています…</div>}<div ref={bottomRef} /></div>
    <div className="composer-wrap"><div className="composer"><textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) { event.preventDefault(); void submit() } }} placeholder="このSessionについて相談する…" rows={1} aria-label="メッセージ" /><button className="send-button" aria-label="送信" disabled={!draft.trim() || isSending} onClick={() => void submit()}><SendIcon size={17} /></button></div><div className="composer-hint"><span>⌘ Enter で送信</span><button className="summary-button" onClick={() => void openSummary()}><SparkleIcon size={14} />採用内容を整理</button></div></div>
    {summaryOpen && <div className="summary-sheet"><div className="summary-sheet-heading"><div><span className="eyebrow">ADOPTION SUMMARY</span><h2>採用内容を整理</h2></div><button className="icon-button" onClick={() => setSummaryOpen(false)} aria-label="閉じる"><CloseIcon /></button></div><p>この会話で採用する設定だけを残します。生成案は自動保存されません。</p><textarea value={summaryDraft} onChange={(event) => setSummaryDraft(event.target.value)} aria-label="採用内容" disabled={summaryLoading} placeholder={summaryLoading ? '要約案を生成しています…' : undefined} /><div className="summary-actions"><button className="subtle-button" onClick={() => setSummaryOpen(false)}>キャンセル</button><button className="primary-button" disabled={summaryLoading || !summaryDraft.trim()} onClick={() => void save()}><CheckIcon size={16} />保存して採用にする</button></div></div>}
    {contextData && <ContextInspector data={contextData} onClose={() => setContextData(undefined)} />}
    {threadSettingsOpen && selectedThread && <ThreadContextSettings threadId={selectedThread.id} onClose={() => setThreadSettingsOpen(false)} />}
  </main>
}

export function CreateDialog({ kind, onClose }: { kind: 'project' | 'thread' | 'session'; onClose: () => void }) {
  const { createProject, createThread, createSession, selectedProject, selectedThread } = useWorkspace()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const labels = { project: 'Project', thread: 'Thread', session: 'Session' }
  const submit = async () => { if (!title.trim()) return; try { if (kind === 'project') await createProject(title.trim(), description.trim()); if (kind === 'thread' && selectedProject) await createThread(title.trim(), description.trim()); if (kind === 'session' && selectedThread) await createSession(title.trim()); onClose() } catch { /* Workspace keeps the dialog open and exposes the save error. */ } }
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><div className="modal" role="dialog" aria-modal="true" aria-labelledby="create-title"><div className="modal-heading"><div><span className="eyebrow">NEW {labels[kind].toUpperCase()}</span><h2 id="create-title">{labels[kind]}を作成</h2></div><button className="icon-button" onClick={onClose} aria-label="閉じる"><CloseIcon /></button></div><label>タイトル<input autoFocus value={title} onChange={(event) => setTitle(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void submit() }} placeholder={`${labels[kind]}の名前`} /></label>{kind !== 'session' && <label>メモ <span className="optional">任意</span><textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={3} placeholder="この作品の方向性や、あとで思い出したいこと" /></label>}<button className="primary-button full-width" disabled={!title.trim()} onClick={() => void submit()}>{labels[kind]}を作成</button></div></div>
}

export function SearchDialog({ onClose }: { onClose: () => void }) {
  const { projects, threads, sessions, messages, selectedSession, selectProject, selectThread, selectSession } = useWorkspace()
  const [query, setQuery] = useState('')
  const [remoteResults, setRemoteResults] = useState<SearchResult[]>([])
  const [activeIndex, setActiveIndex] = useState(0)
  useEffect(() => { if (!query.trim() || import.meta.env.MODE === 'test') { setRemoteResults([]); return }; const timer = window.setTimeout(() => { void searchApi.search(query.trim()).then(setRemoteResults).catch(() => setRemoteResults([])) }, 200); return () => window.clearTimeout(timer) }, [query])
  const results = useMemo<SearchResult[]>(() => { const q = query.toLocaleLowerCase(); if (!q) return []; const local = [...projects.map((item): SearchResult => ({ type: 'project', title: item.title, id: item.id, projectId: item.id })), ...threads.map((item): SearchResult => ({ type: 'thread', title: item.title, id: item.id, projectId: item.projectId })), ...sessions.map((item): SearchResult => ({ type: 'session', title: item.title, id: item.id, threadId: item.threadId })), ...messages.map((item): SearchResult => ({ type: 'message', title: selectedSession?.title ?? 'Message', id: item.id, threadId: selectedSession?.threadId, sessionId: item.sessionId, excerpt: item.content }))].filter((item) => `${item.title} ${item.excerpt ?? ''}`.toLocaleLowerCase().includes(q)); return [...local, ...remoteResults].filter((item, index, all) => all.findIndex((other) => other.type === item.type && other.id === item.id) === index) }, [projects, threads, sessions, messages, selectedSession, query, remoteResults])
  useEffect(() => { setActiveIndex((index) => Math.min(index, Math.max(results.length - 1, 0))) }, [query, results.length])
  const pick = (item: SearchResult) => { if (item.type === 'project') selectProject(item.id); else if (item.type === 'thread') { if (item.projectId) selectProject(item.projectId); selectThread(item.id) } else { const sessionId = item.type === 'message' ? item.sessionId : item.id; const thread = threads.find((threadItem) => threadItem.id === item.threadId); if (thread) { selectProject(thread.projectId); selectThread(thread.id) }; if (sessionId) selectSession(sessionId) }; onClose() }
  const onSearchKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => { if (event.key === 'ArrowDown') { event.preventDefault(); setActiveIndex((index) => Math.min(index + 1, Math.max(results.length - 1, 0))) } else if (event.key === 'ArrowUp') { event.preventDefault(); setActiveIndex((index) => Math.max(index - 1, 0)) } else if (event.key === 'Enter' && results[activeIndex]) { event.preventDefault(); pick(results[activeIndex]) } }
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><div className="search-dialog" role="dialog" aria-modal="true"><div className="search-input-wrap"><SearchIcon size={19} /><input autoFocus value={query} onChange={(event) => { setQuery(event.target.value); setActiveIndex(0) }} onKeyDown={onSearchKeyDown} placeholder="Project、Thread、Sessionを検索…" /><button className="icon-button" onClick={onClose} aria-label="閉じる"><CloseIcon size={17} /></button></div><div className="search-results">{!query && <div className="search-empty"><SearchIcon size={25} /><p>作品やSessionを横断して探せます</p><span>タイトル、採用内容、メッセージを検索対象にできます</span></div>}{query && results.length === 0 && <div className="search-empty"><p>「{query}」に一致する結果はありません</p></div>}{results.map((item, index) => <button aria-selected={index === activeIndex} className={`search-result ${index === activeIndex ? 'active' : ''}`} key={`${item.type}-${item.id}`} onClick={() => pick(item)}><span className="result-type">{item.type}</span><span>{item.title}</span></button>)}</div><div className="search-footer"><span>↑↓移動 · Enterで選択</span><span>Escで閉じる</span></div></div></div>
}
