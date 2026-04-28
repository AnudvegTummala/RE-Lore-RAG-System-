import { create } from 'zustand'
import type { ChatMessage, GraphPayload } from '../types'

interface AppState {
  messages: ChatMessage[]
  isStreaming: boolean
  activeGraph: GraphPayload | null
  selectedNode: string | null

  addMessage: (msg: ChatMessage) => void
  updateLastMessage: (patch: Partial<ChatMessage>) => void
  setStreaming: (v: boolean) => void
  setActiveGraph: (g: GraphPayload | null) => void
  setSelectedNode: (id: string | null) => void
  clearMessages: () => void
}

export const useAppStore = create<AppState>((set) => ({
  messages: [],
  isStreaming: false,
  activeGraph: null,
  selectedNode: null,

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  updateLastMessage: (patch) =>
    set((s) => {
      const msgs = [...s.messages]
      if (msgs.length === 0) return s
      msgs[msgs.length - 1] = { ...msgs[msgs.length - 1], ...patch }
      return { messages: msgs }
    }),

  setStreaming: (v) => set({ isStreaming: v }),
  setActiveGraph: (g) => set({ activeGraph: g }),
  setSelectedNode: (id) => set({ selectedNode: id }),
  clearMessages: () => set({ messages: [] }),
}))
