import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export function Markdown({ content }: { content: string }) {
  return <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{
    a: ({ href, children, ...props }) => <a href={href} target="_blank" rel="noreferrer" {...props}>{children}</a>,
    code: ({ className, children, ...props }) => <code className={className ? `code-language ${className}` : 'inline-code'} {...props}>{children}</code>,
    pre: ({ children }) => <pre className="code-block">{children}</pre>,
  }}>{content.replace(/<br\s*\/?>/gi, ' / ')}</ReactMarkdown></div>
}
