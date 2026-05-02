import { useAppStore } from '../../store/appStore'

export default function Header() {
  const { clearMessages, setActiveGraph, messages } = useAppStore()

  function handleClear() {
    clearMessages()
    setActiveGraph(null)
  }

  return (
    <header className="h-14 flex items-center justify-between px-6 border-b border-re-border bg-re-surface shrink-0">
      <span className="text-re-red-bright font-mono font-semibold tracking-widest uppercase text-sm">
        RE Lore Oracle
      </span>
      {messages.length > 0 && (
        <button
          onClick={handleClear}
          className="text-xs text-re-muted hover:text-re-text font-mono transition-colors"
        >
          Clear
        </button>
      )}
    </header>
  )
}