import type { Message, Project, Session, Thread } from './types'

export const seedProjects: Project[] = [{ id: 'project-mygo', title: 'MyGO ワンライト', description: '愛音と燈をめぐる短編シリーズ' }]
export const seedThreads: Thread[] = [{ id: 'thread-accident', projectId: 'project-mygo', title: '愛音事故SS', description: '事故をきっかけに二人の距離が変わる話' }]
export const seedSessions: Session[] = [
  { id: 'session-accident', threadId: 'thread-accident', title: '事故要素を入れるとして現実的な事故と表現', status: 'adopted', archived: false, pinned: true, adoptionSummary: '・愛音は自転車で事故に遭う\n・信号のない交差点で右折車と接触する\n・右腕を骨折するが、意識は失わない' },
  { id: 'session-tomori', threadId: 'thread-accident', title: '燈が事故を知る流れ', status: 'adopted', archived: false, pinned: false, adoptionSummary: '・燈は事故現場にはいない\n・病院へ搬送されたあとに事故を知る' },
  { id: 'session-hospital', threadId: 'thread-accident', title: '病院での会話', status: 'considering', archived: false, pinned: false, adoptionSummary: null },
  { id: 'session-memory', threadId: 'thread-accident', title: '記憶喪失案', status: 'rejected', archived: false, pinned: false, adoptionSummary: null },
  { id: 'session-old', threadId: 'thread-accident', title: '事故後のSNS反応', status: 'superseded', archived: true, pinned: false, adoptionSummary: null },
]
export const seedMessages: Record<string, Message[]> = {
  'session-hospital': [
    { id: 'msg-1', sessionId: 'session-hospital', role: 'user', content: '病院で燈が事故を知る場面を、説明的になりすぎずに組み立てたい。', createdAt: '2026-09-05T08:00:00.000Z' },
    { id: 'msg-2', sessionId: 'session-hospital', role: 'assistant', content: '燈が「事故だった」と理解する瞬間を、情報ではなく身体の反応から始めると自然です。\n\nたとえば、看護師の言葉を聞いたあと、返事より先に手に持ったスマホを落とす。そこから病室の匂いや足音が急に大きくなる、という順序にすると、動揺を説明せずに見せられます。', model: 'local-qwen', createdAt: '2026-09-05T08:01:00.000Z', sources: [{ id: 'source-1', url: 'https://example.com/scene-notes', title: '場面設計メモ', excerpt: '身体反応から感情を見せるための参考メモ' }] },
  ],
}
