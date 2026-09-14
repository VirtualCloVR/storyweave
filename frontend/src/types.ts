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
  budgetChars?: number
  totalChars?: number
  mode?: string
  includedCharacters?: ContextCharacter[]
  excludedCharacters?: ContextCharacter[]
  sceneFacts?: SceneFact[]
  canon?: { digestStatus?: string; relevantSessions?: ContextSession[]; content?: string }
  sizes?: Record<string, number>
  compressionDegraded?: boolean
}

export interface CharacterFact { id?: string; key: string; value: string; sortOrder?: number }
export interface Character { id: string; name: string; sourceTitle?: string | null; aliases: string[]; facts: CharacterFact[] }
export interface ThreadCharacter { character: Character; alwaysInclude: boolean; sortOrder?: number }
export interface SceneFact { id?: string; key: string; value: string; sortOrder?: number }
export interface ContextCharacter { character: Character; reason?: string; facts?: CharacterFact[] }

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

export type WorkspaceItemKind = 'project' | 'thread' | 'session'

export interface ApiClient {
  deleteProject(id: string): Promise<void>
  deleteThread(id: string): Promise<void>
  deleteSession(id: string): Promise<void>
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

export interface StructuredContextApiClient {
  listCharacters(): Promise<Character[]>
  createCharacter(input: Pick<Character, 'name' | 'sourceTitle' | 'aliases' | 'facts'>): Promise<Character>
  updateCharacter(id: string, input: Partial<Pick<Character, 'name' | 'sourceTitle' | 'aliases' | 'facts'>>): Promise<Character>
  deleteCharacter(id: string): Promise<void>
  getThreadCharacters(threadId: string): Promise<ThreadCharacter[]>
  saveThreadCharacters(threadId: string, items: Array<{ characterId: string; alwaysInclude: boolean; sortOrder?: number }>): Promise<ThreadCharacter[]>
  getSceneFacts(threadId: string): Promise<SceneFact[]>
  saveSceneFacts(threadId: string, facts: SceneFact[]): Promise<SceneFact[]>
}
