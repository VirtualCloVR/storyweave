import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { createApiClient } from './api'
import { seedMessages, seedProjects, seedSessions, seedThreads } from './mockData'
import type { Message, Project, Session, SessionStatus, Thread } from './types'

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
  connectionError?: string
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)
const api = createApiClient()
const shouldSync = import.meta.env.MODE !== 'test' && import.meta.env.VITE_DEMO_MODE !== 'true'
const statusRank: Record<SessionStatus, number> = { adopted: 0, considering: 1, rejected: 2, superseded: 3 }
function firstSession(items: Session[], parentThreadId: string | undefined) {
  return [...items].filter((item) => item.threadId === parentThreadId && !item.archived).sort((a, b) => Number(b.pinned) - Number(a.pinned) || statusRank[a.status] - statusRank[b.status] || (b.updatedAt ?? '').localeCompare(a.updatedAt ?? ''))[0]
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>(shouldSync ? [] : seedProjects)
  const [threads, setThreads] = useState<Thread[]>(shouldSync ? [] : seedThreads)
  const [sessions, setSessions] = useState<Session[]>(shouldSync ? [] : seedSessions)
  const [messageMap, setMessageMap] = useState<Record<string, Message[]>>(shouldSync ? {} : seedMessages)
  const [projectId, setProjectId] = useState(shouldSync ? '' : seedProjects[0].id)
  const [threadId, setThreadId] = useState(shouldSync ? '' : seedThreads[0].id)
  const [sessionId, setSessionId] = useState(shouldSync ? '' : seedSessions[2].id)
  const [connectionError, setConnectionError] = useState<string>()

  useEffect(() => {
    if (!shouldSync) return
    let active = true
    let retry: number | undefined
    const loadWorkspace = async () => {
      try {
        const loadedProjects = await api.listProjects()
        const loadedThreads = (await Promise.all(loadedProjects.map((project) => api.listThreads(project.id)))).flat()
        const loadedSessions = (await Promise.all(loadedThreads.map((thread) => api.listSessions(thread.id)))).flat()
        if (!active) return
        setProjects(loadedProjects); setThreads(loadedThreads); setSessions(loadedSessions)
        const project = loadedProjects[0]; const thread = loadedThreads.find((item) => item.projectId === project?.id); const session = firstSession(loadedSessions, thread?.id)
        setProjectId(project?.id ?? ''); setThreadId(thread?.id ?? ''); setSessionId(session?.id ?? '')
        if (session) setMessageMap({ [session.id]: await api.listMessages(session.id) })
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
  }, [])

  const selectedProject = projects.find((item) => item.id === projectId)
  const selectedThread = threads.find((item) => item.id === threadId)
  const selectedSession = sessions.find((item) => item.id === sessionId)
  const selectProject = useCallback((id: string) => { setProjectId(id); const next = threads.find((item) => item.projectId === id); if (next) { setThreadId(next.id); const first = firstSession(sessions, next.id); if (first) setSessionId(first.id) } }, [sessions, threads])
  const selectThread = useCallback((id: string) => { setThreadId(id); const first = firstSession(sessions, id); if (first) setSessionId(first.id) }, [sessions])
  const selectSession = useCallback((id: string) => { setSessionId(id); if (shouldSync) void api.listMessages(id).then((items) => { setMessageMap((current) => ({ ...current, [id]: items })); setConnectionError(undefined) }).catch(() => setConnectionError('Message履歴を取得できませんでした。')) }, [])

  const createProject = async (title: string, description?: string) => {
    const local: Project = { id: `project-${Date.now()}`, title, description }
    setProjects((items) => [...items, local]); setProjectId(local.id)
    if (shouldSync) try { const remote = await api.createProject({ title, description }); setProjects((items) => items.map((item) => item.id === local.id ? remote : item)); setProjectId(remote.id); setConnectionError(undefined) } catch { setConnectionError('Projectを保存できませんでした。') }
  }
  const createThread = async (title: string, description?: string) => {
    if (!selectedProject) return
    const local: Thread = { id: `thread-${Date.now()}`, projectId: selectedProject.id, title, description }
    setThreads((items) => [...items, local]); setThreadId(local.id)
    if (shouldSync) try { const remote = await api.createThread(selectedProject.id, { title, description }); setThreads((items) => items.map((item) => item.id === local.id ? remote : item)); setThreadId(remote.id); setConnectionError(undefined) } catch { setConnectionError('Threadを保存できませんでした。') }
  }
  const createSession = async (title: string) => {
    if (!selectedThread) return
    const local: Session = { id: `session-${Date.now()}`, threadId: selectedThread.id, title, status: 'considering', archived: false, pinned: false, adoptionSummary: null }
    setSessions((items) => [...items, local]); setSessionId(local.id)
    if (shouldSync) try { const remote = await api.createSession(selectedThread.id, { title }); setSessions((items) => items.map((item) => item.id === local.id ? remote : item)); setSessionId(remote.id); setConnectionError(undefined) } catch { setConnectionError('Sessionを保存できませんでした。') }
  }
  const updateSession = async (patch: Partial<Pick<Session, 'status' | 'archived' | 'pinned' | 'title'>>) => {
    if (!selectedSession) return
    setSessions((items) => items.map((item) => item.id === selectedSession.id ? { ...item, ...patch, updatedAt: new Date().toISOString() } : item))
    if (shouldSync) try { const remote = await api.updateSession(selectedSession.id, patch); setSessions((items) => items.map((item) => item.id === selectedSession.id ? remote : item)); setConnectionError(undefined) } catch { setConnectionError('Sessionの更新を保存できませんでした。') }
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
    if (shouldSync) try {
      const assistant = await api.sendChat(selectedSession.id, content, onToken)
      setMessageMap((items) => ({ ...items, [selectedSession.id]: [...(items[selectedSession.id] ?? []), assistant] }))
    } catch { setConnectionError('LLM応答を取得できませんでした。BackendログとLLM設定を確認してください。') } else offlineReply()
  }
  const generateSummary = async () => {
    if (!selectedSession) return ''
    const fallback = () => { const conversation = (messageMap[selectedSession.id] ?? []).filter((message) => message.role === 'user').map((message) => `・${message.content}`).join('\n'); return conversation || '・このSessionで採用する設定をここに整理してください' }
    if (shouldSync) try { return (await api.generateSummary(selectedSession.id)).summary } catch { return fallback() }
    return fallback()
  }
  const saveSummary = async (summary: string) => {
    if (!selectedSession) return
    setSessions((items) => items.map((item) => item.id === selectedSession.id ? { ...item, adoptionSummary: summary, status: 'adopted' } : item))
    if (shouldSync) try { const remote = await api.saveSummary(selectedSession.id, summary); setSessions((items) => items.map((item) => item.id === selectedSession.id ? remote : item)); setConnectionError(undefined) } catch { setConnectionError('採用内容を保存できませんでした。') }
  }
  const value = useMemo(() => ({ projects, threads, sessions, messages: messageMap[sessionId] ?? [], selectedProject, selectedThread, selectedSession, selectProject, selectThread, selectSession, createProject, createThread, createSession, updateSession, sendMessage, generateSummary, saveSummary, connectionError }), [projects, threads, sessions, messageMap, sessionId, selectedProject, selectedThread, selectedSession, selectProject, selectThread, selectSession, connectionError])
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() { const context = useContext(WorkspaceContext); if (!context) throw new Error('useWorkspace must be used inside WorkspaceProvider'); return context }
export const statusValues: SessionStatus[] = ['considering', 'adopted', 'rejected', 'superseded']
