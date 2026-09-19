import type { Message, Project, Session, Thread } from './types'

// Offline preview / test fallback. Mirrors the backend sample seed:
// Project "MyGO ワンライト" / Thread "愛音事故SS" / Session "交通事故描写の検討".
export const seedProjects: Project[] = [{ id: 'project-sample', title: 'MyGO ワンライト', description: 'Sample workspace' }]
export const seedThreads: Thread[] = [{ id: 'thread-sample', projectId: 'project-sample', title: '愛音事故SS', description: 'Sample thread' }]
export const seedSessions: Session[] = [
  { id: 'session-sample', threadId: 'thread-sample', title: '交通事故描写の検討', status: 'considering', archived: false, pinned: false, adoptionSummary: null },
]
export const seedMessages: Record<string, Message[]> = {
  'session-sample': [
    { id: 'msg-1', sessionId: 'session-sample', role: 'user', content: '交通事故を知る場面を、説明的になりすぎずに組み立てたい。', createdAt: '2026-09-05T08:00:00.000Z' },
    { id: 'msg-2', sessionId: 'session-sample', role: 'assistant', content: '出来事の説明からではなく、人物の身体反応から始めると自然です。', model: 'offline-preview', createdAt: '2026-09-05T08:01:00.000Z', sources: [{ id: 'source-1', url: 'https://example.com/scene-notes', title: '場面設計メモ', excerpt: '身体反応から感情を見せるための参考メモ' }] },
  ],
}
