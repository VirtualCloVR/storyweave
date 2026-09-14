import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useWorkspace } from './WorkspaceContext'
import type { WorkspaceItemKind } from './types'

const labels = { project: 'Workspace', thread: 'Thread', session: 'Session' }
type Target = { id: string; title: string }

export function DeleteAction({ kind, item }: { kind: WorkspaceItemKind; item?: Target }) {
  const [target, setTarget] = useState<Target | null>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const close = () => { setTarget(null); trigger.current?.focus() }
  return <>
    <button ref={trigger} className="mini-button delete-item-button" disabled={!item} aria-label={'選択中の' + labels[kind] + 'を削除'} title={item ? labels[kind] + '「' + item.title + '」を削除' : '削除する項目を選択してください'} onClick={() => item && setTarget(item)}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7" /></svg>
    </button>
    {target && createPortal(<DeleteDialog kind={kind} target={target} onClose={close} />, document.body)}
  </>
}

function DeleteDialog({ kind, target, onClose }: { kind: WorkspaceItemKind; target: Target; onClose: () => void }) {
  const { threads, sessions, deleteItem, generatingSessionId } = useWorkspace()
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const inFlight = useRef(false)
  const cancel = useRef<HTMLButtonElement>(null)
  const headingId = useId()
  const descriptionId = useId()
  const threadIds = new Set(threads.filter((item) => kind === 'project' ? item.projectId === target.id : kind === 'thread' && item.id === target.id).map((item) => item.id))
  const affectedSessions = sessions.filter((item) => kind === 'session' ? item.id === target.id : threadIds.has(item.threadId))
  const generating = affectedSessions.some((item) => item.id === generatingSessionId)
  useEffect(() => { cancel.current?.focus() }, [])
  const submit = async () => {
    if (inFlight.current || generating) return
    inFlight.current = true
    setSaving(true); setError('')
    try { await deleteItem(kind, target.id); onClose() }
    catch (failure) { setError(failure instanceof Error ? failure.message : '削除できませんでした。') }
    finally { inFlight.current = false; setSaving(false) }
  }
  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !inFlight.current) onClose() }}>
    <section className="modal delete-dialog" role="alertdialog" aria-modal="true" aria-labelledby={headingId} aria-describedby={descriptionId} aria-busy={saving} onKeyDown={(event) => {
      if (event.key === 'Escape') { event.stopPropagation(); if (!inFlight.current) onClose() }
      if (event.key === 'Tab') {
        const controls = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)'))
        const first = controls[0]; const last = controls[controls.length - 1]
        if (!first) { event.preventDefault(); return }
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
      }
    }}>
      <h2 id={headingId}>{labels[kind]}を削除しますか？</h2>
      <div id={descriptionId}>
        <p className="delete-target">{target.title}</p>
        {kind === 'project' && <p>このWorkspaceと、中のThread {threadIds.size}件・Session {affectedSessions.length}件を削除します。</p>}
        {kind === 'thread' && <p>このThreadと、中のSession {affectedSessions.length}件を削除します。</p>}
        {kind === 'session' && <p>このSessionを削除します。</p>}
        <p>会話履歴・参照ソース・採用内容も削除されます。この操作は取り消せません。</p>
        {affectedSessions.some((item) => item.status === 'adopted') && <p>削除した採用内容は、以後のContextにも引き継がれなくなります。</p>}
      </div>
      {generating && <p role="status">回答の生成が終わってから削除してください。</p>}
      {error && <p className="error-note" role="alert">{error}</p>}
      <div className="delete-actions">
        <button ref={cancel} className="subtle-button" disabled={saving} onClick={onClose}>キャンセル</button>
        <button className="primary-button delete-confirm" disabled={saving || generating} onClick={() => void submit()}>{saving ? '削除中…' : '削除する'}</button>
      </div>
    </section>
  </div>
}
