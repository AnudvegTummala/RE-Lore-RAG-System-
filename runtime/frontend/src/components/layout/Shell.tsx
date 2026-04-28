import Header from './Header'
import Sidebar from './Sidebar'
import ChatWindow from '../chat/ChatWindow'
import GraphViewer from '../graph/GraphViewer'

export default function Shell() {
  return (
    <div className="flex flex-col h-full bg-re-dark text-re-text">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex flex-1 overflow-hidden">
          <ChatWindow />
          <aside className="w-96 border-l border-re-border flex flex-col overflow-hidden">
            <GraphViewer />
          </aside>
        </main>
      </div>
    </div>
  )
}
