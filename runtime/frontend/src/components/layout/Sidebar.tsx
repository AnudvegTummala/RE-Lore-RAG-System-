import { useAppStore } from '../../store/appStore'

const DEMO_QUERIES = [
  "Who is connected to Umbrella through direct employment and outbreak events?",
  "Which games connect Leon S. Kennedy and Ada Wong?",
  "What enemies are related to Tyrant lineage?",
  "What does Jill Valentine look like across different games?",
  "Which concept art items relate to Nemesis?",
]

interface SidebarProps {
  onSelect?: (query: string) => void
}

export default function Sidebar({ onSelect }: SidebarProps) {
  const { messages, isStreaming } = useAppStore()
  const lastUserQuery = [...messages].reverse().find((m) => m.role === 'user')?.content

  return (
    <aside className="w-64 border-r border-re-border bg-re-surface flex flex-col shrink-0">
      <div className="p-4">
        <p className="text-xs text-re-muted uppercase tracking-wider mb-3 font-mono">Demo Queries</p>
        <ul className="space-y-1">
          {DEMO_QUERIES.map((q) => (
            <li key={q}>
              <button
                onClick={() => onSelect?.(q)}
                disabled={isStreaming}
                className={`w-full text-left text-xs px-3 py-2 rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                  lastUserQuery === q
                    ? 'bg-re-surface-2 border border-re-red text-white'
                    : 'text-re-text hover:bg-re-surface-2 hover:text-white border border-transparent'
                }`}
              >
                {q}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  )
}