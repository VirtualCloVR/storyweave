export type SessionStatus = 'considering' | 'adopted' | 'rejected' | 'superseded'
export type MessageRole = 'user' | 'assistant' | 'system' | 'tool'

export interface Source {
  id?: string
  url: string
  messageId?: string | null
  sourceType?: 'search' | 'fetch'
  provider?: string | null
  query?: string | null
  title?: string | null
  excerpt?: string | null
  fetchedAt?: string | null
}

export interface Project {
  id: string
  title: string
  description?: string
  createdAt?: string
  updatedAt?: string
}

export interface Thread {
  id: string
  projectId: string
  title: string
  description?: string
  createdAt?: string
  updatedAt?: string
}

export interface Session {
  id: string
  threadId: string
  title: string
  status: SessionStatus
  archived: boolean
  pinned: boolean
  adoptionSummary?: string | null
  updatedAt?: string
  messageCount?: number
}

export interface Message {
  id: string
  sessionId: string
  role: MessageRole
  content: string
  model?: string | null
  createdAt?: string
  streaming?: boolean
  sources?: Source[]
  references?: Source[]
  metadata?: Record<string, unknown> | null
}

export interface HealthStatus {
  status: 'ok' | 'degraded'
  database: 'ok' | 'unavailable'
  llm: 'ok' | 'unavailable'
  model: string
}

export interface ContextSession {
  id: string
  title: string
  summary: string
  archived: boolean
}

export interface ContextInspectorData {
  project: Project
  thread: Thread
  currentSession: Session
  adoptedSessions: ContextSession[]
  excludedCounts: Record<'considering' | 'rejected' | 'superseded', number>
  confirmedContextChars: number
  currentHistoryChars: number
}

export interface SearchResult {
  id: string
  type: 'project' | 'thread' | 'session' | 'message'
  title: string
  excerpt?: string
  projectId?: string
  threadId?: string
  sessionId?: string
  status?: SessionStatus
  archived?: boolean
}

export interface CreateInput {
  title: string
  description?: string
}

export interface ApiClient {
  getHealth(): Promise<HealthStatus>
  listProjects(): Promise<Project[]>
  createProject(input: CreateInput): Promise<Project>
  listThreads(projectId: string): Promise<Thread[]>
  createThread(projectId: string, input: CreateInput): Promise<Thread>
  listSessions(threadId: string): Promise<Session[]>
  createSession(threadId: string, input: CreateInput): Promise<Session>
  updateSession(id: string, patch: Partial<Pick<Session, 'title' | 'status' | 'archived' | 'pinned'>>): Promise<Session>
  listMessages(sessionId: string): Promise<Message[]>
  sendChat(sessionId: string, content: string, onToken?: (token: string) => void): Promise<Message>
  generateSummary(sessionId: string): Promise<{ summary: string }>
  saveSummary(sessionId: string, summary: string): Promise<Session>
  getContext(sessionId: string): Promise<ContextInspectorData>
  search(query: string, filters?: Record<string, string>): Promise<SearchResult[]>
}
