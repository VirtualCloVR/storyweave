import { render, screen } from '@testing-library/react'
import { Markdown } from '../Markdown'
import { MessageSources } from '../components'
import type { Message } from '../types'

describe('assistant rich content', () => {
  it('renders GFM headings, tables, links, lists and fenced code', () => {
    render(<Markdown content={'## 見出し\n\n- 箇条書き\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\n[参照](https://example.com)\n\n```ts\nconst answer = true\n```'} />)
    expect(screen.getByRole('heading', { name: '見出し' })).toBeInTheDocument()
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '参照' })).toHaveAttribute('href', 'https://example.com')
    expect(screen.getByText('const answer = true')).toBeInTheDocument()
  })

  it('removes model-generated br tags without enabling raw HTML', () => {
    const { container } = render(<Markdown content={'1行目<br>2行目\n\n<script>alert(1)</script>'} />)
    expect(container).toHaveTextContent('1行目')
    expect(container).toHaveTextContent('2行目')
    expect(container.querySelector('script')).toBeNull()
  })

  it('keeps sources closed until the user opens the source list', async () => {
    const message: Message = { id: 'm1', sessionId: 's1', role: 'assistant', content: '答え', sources: [{ url: 'https://example.com', title: '参考ページ', excerpt: '要点' }] }
    render(<MessageSources message={message} />)
    const details = screen.getByText('参照ソース').closest('details')
    expect(details).not.toHaveAttribute('open')
    expect(screen.getByText('参考ページ')).toBeInTheDocument()
  })
})
