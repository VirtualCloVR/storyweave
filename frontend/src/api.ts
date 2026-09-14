import type { ApiClient, Character, CharacterFact, ContextInspectorData, HealthStatus, Message, Project, SceneFact, SearchResult, Session, Source, StructuredContextApiClient, Thread, ThreadCharacter } from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api'

async function request<T>(fetcher: typeof fetch, path: string, init?: RequestInit): Promise<T> {
  const response = await fetcher(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) throw new Error(`API ${response.status}: ${await response.text()}`)
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

const json = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) })

function sourceList(value: unknown): Source[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === 'object'))
    .map((item): Source => {
      const rawSourceType = item.sourceType ?? item.source_type
      const sourceType: Source['sourceType'] = rawSourceType === 'search' || rawSourceType === 'fetch' ? rawSourceType : undefined
      return { id: typeof item.id === 'string' ? item.id : undefined, url: String(item.url ?? ''), messageId: typeof item.messageId === 'string' ? item.messageId : typeof item.message_id === 'string' ? item.message_id : null, sourceType, provider: typeof item.provider === 'string' ? item.provider : null, query: typeof item.query === 'string' ? item.query : null, title: typeof item.title === 'string' ? item.title : null, excerpt: typeof item.excerpt === 'string' ? item.excerpt : null, fetchedAt: typeof item.fetched_at === 'string' ? item.fetched_at : typeof item.fetchedAt === 'string' ? item.fetchedAt : null }
    })
    .filter((item) => /^https?:\/\//i.test(item.url))
}

function messageFromPayload(payload: unknown, sessionId: string): Message {
  const root = (payload && typeof payload === 'object' ? payload : {}) as Record<string, unknown>
  const nested = root.message && typeof root.message === 'object' ? root.message as Record<string, unknown> : root
  const sources = sourceList(nested.sources ?? nested.references ?? root.sources ?? root.references)
  const rawMetadata = nested.metadata ?? nested.metadataJson ?? nested.metadata_json
  const metadata = rawMetadata && typeof rawMetadata === 'object' && !Array.isArray(rawMetadata) ? rawMetadata as Record<string, unknown> : null
  return { id: typeof nested.id === 'string' ? nested.id : `message-${Date.now()}`, sessionId, role: nested.role === 'user' ? 'user' : 'assistant', content: typeof nested.content === 'string' ? nested.content : typeof nested.text === 'string' ? nested.text : '', model: typeof nested.model === 'string' ? nested.model : null, createdAt: typeof nested.created_at === 'string' ? nested.created_at : typeof nested.createdAt === 'string' ? nested.createdAt : new Date().toISOString(), ...(metadata ? { metadata } : {}), ...(sources.length ? { sources } : {}) }
}

function uniqueSources(values: Source[]): Source[] {
  const seen = new Set<string>()
  return values.filter((source) => { const key = source.id ?? source.url; if (seen.has(key)) return false; seen.add(key); return true })
}

function characterFromPayload(value: unknown): Character {
  const item = (value && typeof value === 'object' ? value : {}) as Record<string, unknown>
  const factsValue = item.facts ?? item.characterFacts ?? []
  const facts = Array.isArray(factsValue) ? factsValue.map((fact): CharacterFact => { const raw = (fact && typeof fact === 'object' ? fact : {}) as Record<string, unknown>; return { id: typeof raw.id === 'string' ? raw.id : undefined, key: String(raw.key ?? ''), value: String(raw.value ?? ''), sortOrder: Number(raw.sortOrder ?? raw.sort_order ?? 0) } }).filter((fact) => fact.key || fact.value) : []
  const aliases = Array.isArray(item.aliases) ? item.aliases.map(String).filter(Boolean) : []
  return { id: String(item.id ?? ''), name: String(item.name ?? ''), sourceTitle: typeof item.sourceTitle === 'string' ? item.sourceTitle : typeof item.source_title === 'string' ? item.source_title : null, aliases, facts }
}

function sceneFactFromPayload(value: unknown): SceneFact { const item = (value && typeof value === 'object' ? value : {}) as Record<string, unknown>; return { id: typeof item.id === 'string' ? item.id : undefined, key: String(item.key ?? ''), value: String(item.value ?? ''), sortOrder: Number(item.sortOrder ?? item.sort_order ?? 0) } }
function characterListPayload(value: unknown): Character[] { const items = Array.isArray(value) ? value : ((value as { characters?: unknown[] } | null)?.characters ?? []); return items.map(characterFromPayload) }
function sceneListPayload(value: unknown): SceneFact[] { const items = Array.isArray(value) ? value : ((value as { facts?: unknown[]; sceneFacts?: unknown[] } | null)?.facts ?? (value as { sceneFacts?: unknown[] } | null)?.sceneFacts ?? []); return items.map(sceneFactFromPayload).filter((item) => item.key || item.value) }

export class ChatStreamInterruptedError extends Error {
  constructor(message: string, readonly partialMessage: Message) {
    super(message)
    this.name = 'ChatStreamInterruptedError'
  }
}

export function createApiClient(fetcher = fetch): ApiClient & StructuredContextApiClient {
  const get = async <T>(path: string) => {
    const response = await fetcher(`${API_BASE}${path}`)
    if (!response.ok) throw new Error(`API ${response.status}`)
    return response.json() as Promise<T>
  }
  return {
    getHealth: () => get<HealthStatus>('/health'),
    deleteProject: (id) => request<void>(fetcher, `/projects/${id}`, { method: 'DELETE' }),
    deleteThread: (id) => request<void>(fetcher, `/threads/${id}`, { method: 'DELETE' }),
    deleteSession: (id) => request<void>(fetcher, `/sessions/${id}`, { method: 'DELETE' }),
    listProjects: () => get<Project[]>('/projects'),
    createProject: (input) => request<Project>(fetcher, '/projects', json(input)),
    listThreads: (projectId) => get<Thread[]>(`/projects/${projectId}/threads`),
    createThread: (projectId, input) => request<Thread>(fetcher, `/projects/${projectId}/threads`, json(input)),
    listSessions: (threadId) => get<Session[]>(`/threads/${threadId}/sessions`),
    createSession: (threadId, input) => request<Session>(fetcher, `/threads/${threadId}/sessions`, json(input)),
    updateSession: (id, patch) => request<Session>(fetcher, `/sessions/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
    listMessages: async (sessionId) => {
      const payload = await get<unknown>(`/sessions/${sessionId}/messages`)
      const items = Array.isArray(payload) ? payload : ((payload as { messages?: unknown[] } | null)?.messages ?? [])
      return items.map((item) => messageFromPayload(item, sessionId))
    },
    sendChat: async (sessionId, content, onToken) => {
      const response = await fetcher(`${API_BASE}/sessions/${sessionId}/chat`, { ...json({ content }), headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream, application/json' } })
      if (!response.ok) throw new Error(`API ${response.status}`)
      const contentType = response.headers.get('content-type') ?? ''
      if (!contentType.includes('text/event-stream') || !response.body) return response.json().then((payload) => messageFromPayload(payload, sessionId))
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let aggregate = ''
      let buffer = ''
      const sources: Source[] = []
      let finalMessage: Message | undefined
      let sawDone = false
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() ?? ''
        for (const event of events) {
          const eventName = event.split('\n').find((line) => line.startsWith('event:'))?.slice(6).trim()
          const data = event.split('\n').find((line) => line.startsWith('data:'))?.slice(5).trim()
          if (!data) continue
          if (data === '[DONE]') { sawDone = true; continue }
          if (event.split('\n').some((line) => line.trim() === 'event: error')) {
            const errorPayload = (() => { try { return JSON.parse(data) as Record<string, unknown> } catch { return {} } })()
            const partial = errorPayload.message
              ? messageFromPayload(errorPayload, sessionId)
              : { id: `interrupted-${Date.now()}`, sessionId, role: 'assistant' as const, content: aggregate, createdAt: new Date().toISOString(), metadata: { generation_status: 'interrupted' }, ...(sources.length ? { sources: uniqueSources(sources) } : {}) }
            throw new ChatStreamInterruptedError(typeof errorPayload.content === 'string' ? errorPayload.content : 'LLM streaming failed', partial)
          }
          const parsed = (() => { try { return JSON.parse(data) as unknown } catch { return null } })()
          const parsedRecord = parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null
          if (eventName === 'sources') {
            sources.push(...sourceList(Array.isArray(parsed) ? parsed : parsedRecord?.sources ?? parsedRecord?.references))
            continue
          }
          if (parsedRecord && (eventName === 'done' || eventName === 'complete' || eventName === 'completed' || eventName === 'message') && (parsedRecord.message || parsedRecord.role || parsedRecord.content)) {
            finalMessage = messageFromPayload(parsedRecord, sessionId)
            if (finalMessage.content) aggregate = finalMessage.content
            continue
          }
          const eventSources = parsedRecord?.sources ?? parsedRecord?.references
          if (eventSources) sources.push(...sourceList(eventSources))
          const token = parsedRecord ? (typeof parsedRecord.token === 'string' ? parsedRecord.token : typeof parsedRecord.content === 'string' ? parsedRecord.content : '') : parsed === null ? data : ''
          if (!token) continue
          aggregate += token
          onToken?.(token)
        }
      }
      if (finalMessage) return { ...finalMessage, ...((finalMessage.sources?.length || sources.length) ? { sources: uniqueSources([...(finalMessage.sources ?? []), ...sources]) } : {}) }
      if (!sawDone) {
        throw new ChatStreamInterruptedError('LLM streaming was interrupted', { id: `interrupted-${Date.now()}`, sessionId, role: 'assistant', content: aggregate, createdAt: new Date().toISOString(), metadata: { generation_status: 'interrupted' }, ...(sources.length ? { sources: uniqueSources(sources) } : {}) })
      }
      return { id: `stream-${Date.now()}`, sessionId, role: 'assistant', content: aggregate, createdAt: new Date().toISOString(), ...(sources.length ? { sources: uniqueSources(sources) } : {}) }
    },
    generateSummary: (sessionId) => request<{ summary: string }>(fetcher, `/sessions/${sessionId}/summary`, json({})),
    saveSummary: (sessionId, summary) => request<Session>(fetcher, `/sessions/${sessionId}/summary`, { method: 'PUT', body: JSON.stringify({ summary }) }),
    getContext: async (sessionId) => {
      const raw = await get<ContextInspectorData>(`/sessions/${sessionId}/context`)
      const item = raw as ContextInspectorData & Record<string, unknown>
      const normalizeContextCharacters = (value: unknown) => Array.isArray(value) ? value.map((entry) => { const row = (entry && typeof entry === 'object' ? entry : {}) as Record<string, unknown>; return { character: characterFromPayload(row.character ?? row), reason: typeof row.reason === 'string' ? row.reason : undefined, facts: Array.isArray(row.facts) ? row.facts.map((fact) => sceneFactFromPayload(fact)) : undefined } }) : undefined
      const planned = Array.isArray(item.characters) ? item.characters as Array<Record<string, unknown>> : []
      return { ...raw, budgetChars: Number(item.budgetChars ?? item.budget_chars ?? 0) || undefined, totalChars: Number(item.totalChars ?? item.total_chars ?? 0) || undefined, mode: typeof item.mode === 'string' ? item.mode : undefined, includedCharacters: normalizeContextCharacters(item.includedCharacters ?? item.included_characters ?? planned.filter((row) => row.included)), excludedCharacters: normalizeContextCharacters(item.excludedCharacters ?? item.excluded_characters ?? planned.filter((row) => !row.included)), sceneFacts: sceneListPayload(item.sceneFacts ?? item.scene_facts), canon: item.canon as ContextInspectorData['canon'], sizes: item.sizes as Record<string, number> | undefined, compressionDegraded: Boolean(item.compressionDegraded ?? item.compression_degraded) }
    },
    listCharacters: async () => characterListPayload(await get<unknown>('/characters')),
    createCharacter: async (input) => characterFromPayload(await request<unknown>(fetcher, '/characters', json({ name: input.name, sourceTitle: input.sourceTitle, aliases: input.aliases, facts: input.facts }))),
    updateCharacter: async (id, input) => characterFromPayload(await request<unknown>(fetcher, `/characters/${id}`, { method: 'PATCH', body: JSON.stringify(input) })),
    deleteCharacter: async (id) => { await request<unknown>(fetcher, `/characters/${id}`, { method: 'DELETE' }) },
    getThreadCharacters: async (threadId) => { const value = await get<unknown>(`/threads/${threadId}/characters`); const items = Array.isArray(value) ? value : ((value as { characters?: unknown[] } | null)?.characters ?? []); return items.map((entry) => { const row = (entry && typeof entry === 'object' ? entry : {}) as Record<string, unknown>; return { character: characterFromPayload(row.character ?? row), alwaysInclude: Boolean(row.alwaysInclude ?? row.always_include), sortOrder: Number(row.sortOrder ?? row.sort_order ?? 0) } }) },
    saveThreadCharacters: async (threadId, items) => { const value = await request<unknown>(fetcher, `/threads/${threadId}/characters`, { method: 'PUT', body: JSON.stringify(items.map((item) => ({ characterId: item.characterId, alwaysInclude: item.alwaysInclude, sortOrder: item.sortOrder }))) }); const list = Array.isArray(value) ? value : ((value as { characters?: unknown[] } | null)?.characters ?? []); return list.map((entry) => { const row = (entry && typeof entry === 'object' ? entry : {}) as Record<string, unknown>; return { character: characterFromPayload(row.character ?? row), alwaysInclude: Boolean(row.alwaysInclude ?? row.always_include), sortOrder: Number(row.sortOrder ?? row.sort_order ?? 0) } }) },
    getSceneFacts: async (threadId) => sceneListPayload(await get<unknown>(`/threads/${threadId}/scene-facts`)),
    saveSceneFacts: async (threadId, facts) => sceneListPayload(await request<unknown>(fetcher, `/threads/${threadId}/scene-facts`, { method: 'PUT', body: JSON.stringify(facts.map((fact, index) => ({ key: fact.key, value: fact.value, sortOrder: index }))) })),
    search: (query, filters = {}) => get<SearchResult[]>(`/search?q=${encodeURIComponent(query)}&${new URLSearchParams(filters)}`),
  }
}
