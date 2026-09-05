import type { ApiClient, CreateInput, Message, Project, SearchResult, Session, Source, Thread } from './types'

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api'

async function request<T>(fetcher: typeof fetch, path: string, init?: RequestInit): Promise<T> {
  const response = await fetcher(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) throw new Error(`API ${response.status}: ${await response.text()}`)
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
  return { id: typeof nested.id === 'string' ? nested.id : `message-${Date.now()}`, sessionId, role: nested.role === 'user' ? 'user' : 'assistant', content: typeof nested.content === 'string' ? nested.content : typeof nested.text === 'string' ? nested.text : '', model: typeof nested.model === 'string' ? nested.model : null, createdAt: typeof nested.created_at === 'string' ? nested.created_at : typeof nested.createdAt === 'string' ? nested.createdAt : new Date().toISOString(), ...(sources.length ? { sources } : {}) }
}

function uniqueSources(values: Source[]): Source[] {
  const seen = new Set<string>()
  return values.filter((source) => { const key = source.id ?? source.url; if (seen.has(key)) return false; seen.add(key); return true })
}

export function createApiClient(fetcher = fetch): ApiClient {
  const get = async <T>(path: string) => {
    const response = await fetcher(`${API_BASE}${path}`)
    if (!response.ok) throw new Error(`API ${response.status}`)
    return response.json() as Promise<T>
  }
  return {
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
      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() ?? ''
        for (const event of events) {
          const eventName = event.split('\n').find((line) => line.startsWith('event:'))?.slice(6).trim()
          const data = event.split('\n').find((line) => line.startsWith('data:'))?.slice(5).trim()
          if (!data || data === '[DONE]') continue
          if (event.split('\n').some((line) => line.trim() === 'event: error')) {
            const detail = (() => { try { return (JSON.parse(data) as { content?: string }).content } catch { return undefined } })()
            throw new Error(detail ?? 'LLM streaming failed')
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
      return { id: `stream-${Date.now()}`, sessionId, role: 'assistant', content: aggregate, createdAt: new Date().toISOString(), ...(sources.length ? { sources: uniqueSources(sources) } : {}) }
    },
    generateSummary: (sessionId) => request<{ summary: string }>(fetcher, `/sessions/${sessionId}/summary`, json({})),
    saveSummary: (sessionId, summary) => request<Session>(fetcher, `/sessions/${sessionId}/summary`, { method: 'PUT', body: JSON.stringify({ summary }) }),
    search: (query, filters = {}) => get<SearchResult[]>(`/search?q=${encodeURIComponent(query)}&${new URLSearchParams(filters)}`),
  }
}
