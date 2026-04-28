import type { ChatMessage as ChatMessageType } from '../../types'
import SourcePanel from './SourcePanel'
import ImageGallery from '../media/ImageGallery'

interface ChatMessageProps {
  message: ChatMessageType
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-2xl ${isUser ? 'ml-12' : 'mr-12'}`}>
        {isUser ? (
          <div className="bg-re-red px-4 py-2 rounded text-white text-sm font-mono">
            {message.content}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="bg-re-surface-2 border border-re-border px-4 py-3 rounded text-sm leading-relaxed whitespace-pre-wrap">
              {message.content}
              {message.isStreaming && (
                <span className="inline-block w-1.5 h-4 bg-re-red ml-0.5 animate-pulse" />
              )}
            </div>
            {message.sources && message.sources.length > 0 && (
              <SourcePanel sources={message.sources} />
            )}
            {message.images && message.images.length > 0 && (
              <ImageGallery images={message.images} />
            )}
          </div>
        )}
      </div>
    </div>
  )
}
