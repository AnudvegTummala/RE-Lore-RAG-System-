import { useCallback } from 'react'
import { streamQuery } from '../api/client'
import { useAppStore } from '../store/appStore'
import type { ChatMessage } from '../types'

export function useStreaming() {
  const { addMessage, updateLastMessage, setStreaming, setActiveGraph } = useAppStore()

  const sendQuery = useCallback(async (query: string) => {
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: query,
    }
    addMessage(userMsg)

    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      isStreaming: true,
    }
    addMessage(assistantMsg)
    setStreaming(true)

    try {
      for await (const event of streamQuery(query)) {
        if (event.token) {
          updateLastMessage({ content: assistantMsg.content + event.token })
          assistantMsg.content += event.token
        }
        if (event.done) {
          updateLastMessage({
            content: event.answer ?? assistantMsg.content,
            sources: event.sources ?? [],
            images: event.images ?? [],
            graph: event.graph,
            isStreaming: false,
          })
          if (event.graph) setActiveGraph(event.graph)
        }
      }
    } catch (err) {
      updateLastMessage({
        content: 'An error occurred. Please try again.',
        isStreaming: false,
      })
    } finally {
      setStreaming(false)
    }
  }, [addMessage, updateLastMessage, setStreaming, setActiveGraph])

  return { sendQuery }
}
