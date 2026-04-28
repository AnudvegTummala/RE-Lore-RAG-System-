import { useState, type KeyboardEvent } from 'react'

interface ChatInputProps {
  onSubmit: (query: string) => void
  disabled?: boolean
}

export default function ChatInput({ onSubmit, disabled }: ChatInputProps) {
  const [value, setValue] = useState('')

  function submit() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
    setValue('')
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="border-t border-re-border p-4 bg-re-surface">
      <div className="flex gap-3 items-end">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={2}
          placeholder="Ask about characters, enemies, viruses, locations..."
          className="flex-1 resize-none rounded bg-re-surface-2 border border-re-border px-3 py-2 text-sm text-re-text placeholder-re-muted focus:outline-none focus:border-re-red font-mono"
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          className="px-4 py-2 rounded bg-re-red text-white text-sm font-semibold hover:bg-re-red-bright disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  )
}
