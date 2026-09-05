import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ChatStreamInterruptedError, createApiClient } from './api'
import { seedMessages, seedProjects, seedSessions, seedThreads } from './mockData'
import type { ApiClient, ContextInspectorData, HealthStatus, Message, Project, Session, SessionStatus, Thread } from './types'

interface WorkspaceContextValue {
  projects: Project[]
  threads: Thread[]
  sessions: Session[]
  messages: Message[]
  selectedProject?: Project
  selectedThread?: Thread
  selectedSession?: Session
  selectProject: (id: string) => void
  selectThread: (id: string) => void
  selectSession: (id: string) => void
  createProject: (title: string, description?: string) => Promise<void>
  createThread: (title: string, description?: string) => Promise<void>
  createSession: (title: string) => Promise<void>
  updateSession: (patch: Partial<Pick<Session, 'status' | 'archived' | 'pinned' | 'title'>>) => Promise<void>
  sendMessage: (content: string, onToken?: (token: string) => void) => Promise<void>
  generateSummary: () => Promise<string>
  saveSummary: (summary: string) => Promise<void>
  loadContext: () => Promise<ContextInspectorData | undefined>
  health?: HealthStatus
  connectionError?: string
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)
const api = createApiClient()
const shouldSync = import.meta.env.MODE !== 'test' && import.meta.env.VITE_DEMO_MODE !== 'true'
const statusRank: Record<SessionStatus, number> = { adopted: 0, considering: 1, rejected: 2, superseded: 3 }
function firstSession(items: Session[], parentThreadId: string | undefined) {
  return [...items].filter((item) => item.threadId === parentThreadId && !item.archived).sort((a, b) => Number(b.pinned) - Number(a.pinned) || statusRank[a.status] - statusRank[b.status] || (b.updatedAt ?? '').localeCompare(a.updatedAt ?? ''))[0]
}

export function WorkspaceProvider({ children, client = api, sync = shouldSync }: { children: ReactNode; client?: ApiClient; sync?: boolean }) {
  const [projects, setProjects] = useState<Project[]>(sync ? [] : seedProjects)
  const [threads, setThreads] = useState<Thread[]>(sync ? [] : seedThreads)
  const [sessions, setSessions] = useState<Session[]>(sync ? [] : seedSessions)
  const [messageMap, setMessageMap] = useState<Record<string, Message[]>>(sync ? {} : seedMessages)
  const [projectId, setProjectId] = useState(sync ? '' : seedProjects[0].id)
  const [threadId, setThreadId] = useState(sync ? '' : seedThreads[0].id)
  const [sessionId, setSessionId] = useState(sync ? '' : seedSessions[2].id)
  const [connectionError, setConnectionError] = useState<string>()
  const [health, setHealth] = useState<HealthStatus | undefined>(sync ? undefined : { status: 'ok', database: 'ok', llm: 'unavailable', model: 'offline-preview' })

  useEffect(() => {
    if (!sync) return
    let active = true
    let retry: number | undefined
    const loadWorkspace = async () => {
      try {
        const loadedProjects = await client.listProjects()
        const loadedThreads = (await Promise.all(loadedProjects.map((project) => client.listThreads(project.id)))).flat()
        const loadedSessions = (await Promise.all(loadedThreads.map((thread) => client.listSessions(thread.id)))).flat()
        if (!active) return
        setProjects(loadedProjects); setThreads(loadedThreads); setSessions(loadedSessions)
        const project = loadedProjects[0]; const thread = loadedThreads.find((item) => item.projectId === project?.id); const session = firstSession(loadedSessions, thread?.id)
        setProjectId(project?.id ?? ''); setThreadId(thread?.id ?? ''); setSessionId(session?.id ?? '')
        if (session) setMessageMap({ [session.id]: await client.listMessages(session.id) })
        setConnectionError(undefined)
      } catch {
        if (active) {
          setConnectionError('Backendに接続できません。自動で再接続しています。')
          retry = window.setTimeout(() => void loadWorkspace(), 1500)
        }
      }
    }
    void loadWorkspace()
    return () => { active = false; if (retry) window.clearTimeout(retry) }
  }, [client, sync])

  useEffect(() => {
    if (!sync) return
    let active = true
    const refresh = () => void client.getHealth().then((value) => { if (active) setHealth(value) }).catch(() => { if (active) setHealth({ status: 'degraded', database: 'unavailable', llm: 'unavailable', model: '' }) })
    refresh()
    const timer = window.setInterval(refresh, 30_000)
    return () => { active = false; window.clearInterval(timer) }
  }, [client, sync])

  const selectedProject = projects.find((item) => item.id === projectId)
  const selectedThread = threads.find((item) => item.id === threadId)
  const selectedSession = sessions.find((item) => item.id === sessionId)
  const selectProject = useCallback((id: string) => { setProjectId(id); const next = threads.find((item) => item.projectId === id); setThreadId(next?.id ?? ''); const first = firstSession(sessions, next?.id); setSessionId(first?.id ?? '') }, [sessions, threads])
  const selectThread = useCallback((id: string) => { setThreadId(id); const first = firstSession(sessions, id); setSessionId(first?.id ?? '') }, [sessions])
  const selectSession = useCallback((id: string) => { setSessionId(id); if (sync) void client.listMessages(id).then((items) => { setMessageMap((current) => ({ ...current, [id]: items })); setConnectionError(undefined) }).catch(() => setConnectionError('Message履歴を取得できませんでした。')) }, [client, sync])

  const createProject = async (title: string, description?: string) => {
    const before = { projectId, threadId, sessionId }
    const local: Project = { id: `project-${Date.now()}`, title, description }
    setProjects((items) => [...items, local]); setProjectId(local.id); setThreadId(''); setSessionId('')
    if (sync) try { const remote = await client.createProject({ title, description }); setProjects((items) => items.map((item) => item.id === local.id ? remote : item)); setProjectId(remote.id); setConnectionError(undefined) } catch { setProjects((items) => items.filter((item) => item.id !== local.id)); setProjectId(before.projectId); setThreadId(before.threadId); setSessionId(before.sessionId); setConnectionError('Projectを保存できませんでした。'); throw new Error('Project create failed') }
  }
  const createThread = async (title: string, description?: string) => {
    if (!selectedProject) return
    const before = { threadId, sessionId }
    const local: Thread = { id: `thread-${Date.now()}`, projectId: selectedProject.id, title, description }
    setThreads((items) => [...items, local]); setThreadId(local.id); setSessionId('')
    if (sync) try { const remote = await client.createThread(selectedProject.id, { title, description }); setThreads((items) => items.map((item) => item.id === local.id ? remote : item)); setThreadId(remote.id); setConnectionError(undefined) } catch { setThreads((items) => items.filter((item) => item.id !== local.id)); setThreadId(before.threadId); setSessionId(before.sessionId); setConnectionError('Threadを保存できませんでした。'); throw new Error('Thread create failed') }
  }
  const createSession = async (title: string) => {
    if (!selectedThread) return
    const beforeSessionId = sessionId
    const local: Session = { id: `session-${Date.now()}`, threadId: selectedThread.id, title, status: 'considering', archived: false, pinned: false, adoptionSummary: null }
    setSessions((items) => [...items, local]); setSessionId(local.id)
    if (sync) try { const remote = await client.createSession(selectedThread.id, { title }); setSessions((items) => items.map((item) => item.id === local.id ? remote : item)); setSessionId(remote.id); setConnectionError(undefined) } catch { setSessions((items) => items.filter((item) => item.id !== local.id)); setSessionId(beforeSessionId); setConnectionError('Sessionを保存できませんでした。'); throw new Error('Session create failed') }
  }
  const updateSession = async (patch: Partial<Pick<Session, 'status' | 'archived' | 'pinned' | 'title'>>) => {
    if (!selectedSession) return
    const before = selectedSession
    setSessions((items) => items.map((item) => item.id === selectedSession.id ? { ...item, ...patch, updatedAt: new Date().toISOString() } : item))
    if (sync) try { const remote = await client.updateSession(selectedSession.id, patch); setSessions((items) => items.map((item) => item.id === selectedSession.id ? remote : item)); setConnectionError(undefined) } catch { setSessions((items) => items.map((item) => item.id === before.id ? before : item)); setConnectionError('Sessionの更新を保存できませんでした。') }
  }
  const sendMessage = async (content: string, onToken?: (token: string) => void) => {
    if (!selectedSession || !content.trim()) return
    const user: Message = { id: `message-${Date.now()}`, sessionId: selectedSession.id, role: 'user', content: content.trim(), createdAt: new Date().toISOString() }
    setMessageMap((items) => ({ ...items, [selectedSession.id]: [...(items[selectedSession.id] ?? []), user] }))
    const offlineReply = () => {
      const assistant: Message = { id: `message-${Date.now()}-reply`, sessionId: selectedSession.id, role: 'assistant', content: 'ローカルLLMへの接続を待っています。APIを起動すると、この相談に続けて回答が表示されます。', model: 'offline-preview', createdAt: new Date().toISOString() }
      let index = 0; const phrase = assistant.content; const interval = window.setInterval(() => { const token = phrase[index]; if (token) onToken?.(token); index += 1; if (index >= phrase.length) window.clearInterval(interval) }, 14)
      setMessageMap((items) => ({ ...items, [selectedSession.id]: [...(items[selectedSession.id] ?? []), assistant] }))
    }
    if (sync) try {
      const assistant = await client.sendChat(selectedSession.id, content, onToken)
      setMessageMap((items) => ({ ...items, [selectedSession.id]: [...(items[selectedSession.id] ?? []), assistant] }))
    } catch (error) {
      if (error instanceof ChatStreamInterruptedError) {
        try {
          const saved = await client.listMessages(selectedSession.id)
          const hasPartial = saved.some((item) => item.id === error.partialMessage.id && Boolean(item.content))
          const visible = hasPartial || !error.partialMessage.content ? saved : [...saved.filter((item) => item.content || item.metadata?.generation_status !== 'streaming'), error.partialMessage]
          setMessageMap((items) => ({ ...items, [selectedSession.id]: visible }))
        } catch { setMessageMap((items) => ({ ...items, [selectedSession.id]: [...(items[selectedSession.id] ?? []), error.partialMessage] })) }
        setConnectionError('生成が途中で中断されました。部分回答を履歴に保存しました。')
      } else {
        setConnectionError('LLM応答を取得できませんでした。BackendログとLLM設定を確認してください。')
      }
    } else offlineReply()
  }
  const generateSummary = async () => {
    if (!selectedSession) return ''
    const fallback = () => { const conversation = (messageMap[selectedSession.id] ?? []).filter((message) => message.role === 'user').map((message) => `・${message.content}`).join('\n'); return conversation || '・このSessionで採用する設定をここに整理してください' }
    if (sync) try { return (await client.generateSummary(selectedSession.id)).summary } catch { return fallback() }
    return fallback()
  }
  const saveSummary = async (summary: string) => {
    if (!selectedSession) return
    const before = selectedSession
    setSessions((items) => items.map((item) => item.id === selectedSession.id ? { ...item, adoptionSummary: summary, status: 'adopted' } : item))
    if (sync) try { const remote = await client.saveSummary(selectedSession.id, summary); setSessions((items) => items.map((item) => item.id === selectedSession.id ? remote : item)); setConnectionError(undefined) } catch { setSessions((items) => items.map((item) => item.id === before.id ? before : item)); setConnectionError('採用内容を保存できませんでした。'); throw new Error('Summary save failed') }
  }
  const loadContext = useCallback(async (): Promise<ContextInspectorData | undefined> => {
    if (!selectedProject || !selectedThread || !selectedSession) return undefined
    if (sync) return client.getContext(selectedSession.id)
    const siblings = sessions.filter((item) => item.threadId === selectedThread.id && item.id !== selectedSession.id)
    const adoptedSessions = siblings.filter((item) => item.status === 'adopted' && Boolean(item.adoptionSummary?.trim())).map((item) => ({ id: item.id, title: item.title, summary: item.adoptionSummary!.trim(), archived: item.archived }))
    const confirmed = adoptedSessions.map((item) => `[${item.title}]\n${item.summary}`).join('\n\n')
    return { project: selectedProject, thread: selectedThread, currentSession: selectedSession, adoptedSessions, excludedCounts: { considering: siblings.filter((item) => item.status === 'considering').length, rejected: siblings.filter((item) => item.status === 'rejected').length, superseded: siblings.filter((item) => item.status === 'superseded').length }, confirmedContextChars: confirmed.length, currentHistoryChars: (messageMap[selectedSession.id] ?? []).reduce((sum, item) => sum + item.content.length, 0) }
  }, [client, messageMap, selectedProject, selectedSession, selectedThread, sessions, sync])
  const value = useMemo(() => ({ projects, threads, sessions, messages: messageMap[sessionId] ?? [], selectedProject, selectedThread, selectedSession, selectProject, selectThread, selectSession, createProject, createThread, createSession, updateSession, sendMessage, generateSummary, saveSummary, loadContext, health, connectionError }), [projects, threads, sessions, messageMap, sessionId, selectedProject, selectedThread, selectedSession, selectProject, selectThread, selectSession, loadContext, health, connectionError])
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() { const context = useContext(WorkspaceContext); if (!context) throw new Error('useWorkspace must be used inside WorkspaceProvider'); return context }
export const statusValues: SessionStatus[] = ['considering', 'adopted', 'rejected', 'superseded']
