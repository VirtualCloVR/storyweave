import { createApiClient } from '../api'

describe('chat API', () => {
  it('sends JSON and consumes SSE tokens', async () => {
    let requestInit: RequestInit | undefined
    const fetcher: typeof fetch = async (_input, init) => {
      requestInit = init
      return new Response('data: {"token":"接続OK"}\n\ndata: [DONE]\n\n', { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
    }
    const tokens: string[] = []
    const message = await createApiClient(fetcher).sendChat('session-1', 'テスト', (token) => tokens.push(token))
    expect((requestInit?.headers as Record<string, string>)['Content-Type']).toBe('application/json')
    expect(requestInit?.body).toBe(JSON.stringify({ content: 'テスト' }))
    expect(tokens).toEqual(['接続OK'])
    expect(message.content).toBe('接続OK')
  })

  it('prefers the final SSE message and keeps its source references', async () => {
    const fetcher: typeof fetch = async () => new Response([
      'event: token\n', 'data: {"token":"途中"}\n\n',
      'event: done\n', 'data: {"message":{"id":"assistant-1","role":"assistant","content":"## 確定回答","sources":[{"url":"https://example.com/answer","title":"参考ページ"}]}}\n\n',
    ].join(''), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
    const message = await createApiClient(fetcher).sendChat('session-1', 'テスト')
    expect(message.id).toBe('assistant-1')
    expect(message.content).toBe('## 確定回答')
    expect(message.sources?.[0].title).toBe('参考ページ')
  })

  it('accepts a separate source event and removes duplicates from the final message', async () => {
    const source = { url: 'https://example.com/answer', title: '参考ページ' }
    const fetcher: typeof fetch = async () => new Response([
      `event: sources\ndata: ${JSON.stringify([source])}\n\n`,
      `event: done\ndata: ${JSON.stringify({ message: { id: 'assistant-2', role: 'assistant', content: '回答', sources: [source] } })}\n\n`,
    ].join(''), { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
    const message = await createApiClient(fetcher).sendChat('session-1', 'テスト')
    expect(message.sources).toHaveLength(1)
  })
})
