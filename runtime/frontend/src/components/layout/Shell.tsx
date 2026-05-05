import Header from './Header'
import Sidebar from './Sidebar'
import ChatWindow from '../chat/ChatWindow'
import GraphViewer from '../graph/GraphViewer'
import { useAppStore } from '../../store/appStore'
import { useStreaming } from '../../hooks/useStreaming'

export default function Shell() {
  const activeGraph = useAppStore((s) => s.activeGraph)
  const { sendQuery } = useStreaming()

  return (
    <div className="flex flex-col h-full text-re-text">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar onSelect={sendQuery} />
        <main className="flex flex-1 overflow-hidden">
          <ChatWindow />
          {activeGraph && (
            <aside className="w-96 border-l border-re-border flex flex-col overflow-hidden">
              <GraphViewer />
            </aside>
          )}
        </main>
      </div>
    </div>
  )
}
