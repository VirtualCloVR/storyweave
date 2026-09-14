import { useEffect, useState } from 'react'
import { WorkspaceProvider } from './WorkspaceContext'
import { ChatPanel, CreateDialog, ProjectRail, SearchDialog, SessionRail, Topbar } from './components'
import { CharacterLibrary } from './StructuredContext'

function Workspace() {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [createKind, setCreateKind] = useState<'project' | 'thread' | 'session' | null>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [dark, setDark] = useState(true)
  const [charactersOpen, setCharactersOpen] = useState(false)
  useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light' }, [dark])
  useEffect(() => { const onKey = (event: KeyboardEvent) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setSearchOpen(true) } if (event.key === 'Escape') { setSearchOpen(false); setCreateKind(null); setDrawerOpen(false) } }; window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey) }, [])
  return <div className="app-shell"><Topbar onMenu={() => setDrawerOpen(true)} onSearch={() => setSearchOpen(true)} onTheme={() => setDark((value) => !value)} onCharacters={() => setCharactersOpen(true)} /><div className={`workspace-grid ${drawerOpen ? 'drawer-open' : ''}`}><div className="mobile-drawer-scrim" onClick={() => setDrawerOpen(false)} /><div className="drawer-pane" onClick={(event) => { if ((event.target as Element).closest('.session-item')) setDrawerOpen(false) }}><ProjectRail onCreateProject={() => setCreateKind('project')} onCreateThread={() => setCreateKind('thread')} /><SessionRail onCreateSession={() => setCreateKind('session')} /></div><div className="desktop-project"><ProjectRail onCreateProject={() => setCreateKind('project')} onCreateThread={() => setCreateKind('thread')} /></div><div className="desktop-session"><SessionRail onCreateSession={() => setCreateKind('session')} /></div><ChatPanel onMenu={() => setDrawerOpen(true)} /></div>{createKind && <CreateDialog kind={createKind} onClose={() => setCreateKind(null)} />}{searchOpen && <SearchDialog onClose={() => setSearchOpen(false)} />}{charactersOpen && <CharacterLibrary onClose={() => setCharactersOpen(false)} />}</div>
}

export default function App() { return <WorkspaceProvider><Workspace /></WorkspaceProvider> }
