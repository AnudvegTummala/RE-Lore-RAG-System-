import { useAppStore } from '../store/appStore'
import { useStreaming } from './useStreaming'

export function useChat() {
  const { messages, isStreaming, clearMessages } = useAppStore()
  const { sendQuery } = useStreaming()
  return { messages, isStreaming, sendQuery, clearMessages }
}
