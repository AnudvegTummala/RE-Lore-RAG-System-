import { useRef, useEffect } from 'react'
import { useChat } from '../../hooks/useChat'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'

const SUGGESTED = [
  'Who is Leon S. Kennedy?',
  'What is the T-virus?',
  'What enemies are related to Tyrant lineage?',
]

export default function ChatWindow() {
  const { messages, isStreaming, sendQuery } = useChat()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-6">
            <div className="text-center space-y-2">
              <p className="text-re-red-bright font-mono font-semibold tracking-widest uppercase text-lg">
                RE Lore Oracle
              </p>
              <p className="text-re-muted text-sm font-mono">
                Ask anything about Resident Evil lore.
              </p>
            </div>
            <div className="flex flex-col gap-2 w-full max-w-md">
              {SUGGESTED.map((q) => (
                <button
                  key={q}
                  onClick={() => sendQuery(q)}
                  disabled={isStreaming}
                  className="text-left text-xs text-re-text px-4 py-2.5 rounded border border-re-border bg-re-surface hover:border-re-red hover:text-white transition-colors font-mono disabled:opacity-40"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))
        )}
        <div ref={bottomRef} />
      </div>
      <ChatInput onSubmit={sendQuery} disabled={isStreaming} />
    </div>
  )
}