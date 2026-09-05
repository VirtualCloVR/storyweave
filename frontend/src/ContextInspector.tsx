import { CloseIcon } from './icons'
import type { ContextInspectorData } from './types'

export function ContextInspector({ data, onClose }: { data: ContextInspectorData; onClose: () => void }) {
  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
    <section className="context-inspector" role="dialog" aria-modal="true" aria-labelledby="context-inspector-title">
      <div className="modal-heading">
        <div><span className="eyebrow">CONFIRMED CONTEXT</span><h2 id="context-inspector-title">引き継がれる前提</h2></div>
        <button className="icon-button" onClick={onClose} aria-label="閉じる"><CloseIcon /></button>
      </div>
      <p className="context-current">現在のSession: <strong>{data.currentSession.title}</strong></p>
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
