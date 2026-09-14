import { CloseIcon } from './icons'
import type { ContextInspectorData } from './types'

export function ContextInspector({ data, onClose }: { data: ContextInspectorData; onClose: () => void }) {
  const sizes = data.sizes ?? { confirmedContext: data.confirmedContextChars, history: data.currentHistoryChars }
  const total = data.totalChars ?? Object.values(sizes).reduce((sum, value) => sum + (Number(value) || 0), 0)
  const budget = data.budgetChars
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
    <section className="context-inspector" role="dialog" aria-modal="true" aria-labelledby="context-inspector-title">
      <div className="modal-heading">
        <div><span className="eyebrow">CONFIRMED CONTEXT</span><h2 id="context-inspector-title">引き継がれる前提</h2></div>
        <button className="icon-button" onClick={onClose} aria-label="閉じる"><CloseIcon /></button>
      </div>
      <p className="context-current">現在のSession: <strong>{data.currentSession.title}</strong></p>
      {(budget || data.mode || data.compressionDegraded) && <div className="context-v02-summary"><span>Budget <strong>{total.toLocaleString()} / {(budget ?? 0).toLocaleString()} chars</strong></span><span>Mode <strong>{data.mode === 'digest' ? 'Digest + Relevant Canon' : data.mode === 'full' ? 'Full Canon' : data.mode ?? 'Planner'}</strong></span></div>}
      {data.compressionDegraded && <div className="compression-warning" role="alert">Context Budgetのため、一部の確定設定が省略されている可能性があります。未提示の設定を断定しないでください。</div>}
      {data.includedCharacters && <section className="context-section"><h3>Characters</h3>{data.includedCharacters.map((item) => <article className="context-structured-item" key={item.character.id}><strong><span aria-hidden="true">✓ </span><span>{item.character.name}</span></strong><span>{item.reason ?? 'included'}</span>{(item.facts ?? item.character.facts).map((fact) => <div key={`${fact.key}-${fact.value}`}>{fact.key} = {fact.value}</div>)}</article>)}{data.excludedCharacters?.map((item) => <article className="context-structured-item muted" key={item.character.id}><strong><span aria-hidden="true">○ </span><span>{item.character.name}</span></strong><span>Cast but not included</span></article>)}</section>}
      {data.sceneFacts && <section className="context-section"><h3>Scene <small>Thread Local</small></h3><div className="context-facts">{data.sceneFacts.map((fact) => <span key={`${fact.key}-${fact.value}`}>✓ {fact.key} = {fact.value}</span>)}</div></section>}
      {data.canon && <section className="context-section"><h3>Canon</h3><p className="context-canon-status">✓ {data.canon.digestStatus ?? (data.mode === 'digest' ? 'Digest' : 'Full Canon')}</p>{data.canon.relevantSessions?.map((session) => <div className="context-canon-session" key={session.id}>✓ Relevant Session: {session.title}</div>)}</section>}
      {data.sizes && <section className="context-section"><h3>Sizes</h3><div className="context-size-grid">{Object.entries(sizes).map(([key, value]) => <span key={key}>{key}: <strong>{Number(value).toLocaleString()}</strong></span>)}<span>total: <strong>{total.toLocaleString()}</strong></span></div></section>}
      <div className="context-size"><span>確定Context {data.confirmedContextChars.toLocaleString()}文字</span><span>現在の履歴 {data.currentHistoryChars.toLocaleString()}文字</span></div>
      <div className="context-adopted-list">
        {data.adoptedSessions.length === 0 && <p className="empty-state small">引き継がれる採用済みSessionはありません。</p>}
        {data.adoptedSessions.map((session) => <article key={session.id} className="context-adopted-item">
          <h3>{session.title}{session.archived && <span className="context-archived">Archive</span>}</h3>
          <pre>{session.summary}</pre>
        </article>)}
      </div>
      <p className="context-excluded">自動Contextから除外: 検討中 {data.excludedCounts.considering} / 没 {data.excludedCounts.rejected} / 差し替え済み {data.excludedCounts.superseded}</p>
    </section>
  </div>
}
