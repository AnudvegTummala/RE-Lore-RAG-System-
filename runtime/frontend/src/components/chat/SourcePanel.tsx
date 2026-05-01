import type { Source } from '../../types'

interface SourcePanelProps {
  sources: Source[]
}

export default function SourcePanel({ sources }: SourcePanelProps) {
  return (
    <div className="space-y-1">
      <p className="text-xs text-re-muted font-mono uppercase tracking-wider">Sources</p>
      <div className="flex flex-wrap gap-2">
        {sources.map((s) => (
          <a
            key={s.entity_id}
            href={s.source_url || '#'}
            target="_blank"
            rel="noopener noreferrer"
            title={s.snippet ?? ''}
            className="inline-flex items-center gap-1 text-xs bg-re-surface-2 border border-re-border px-2 py-1 rounded hover:border-re-red transition-colors"
          >
            <span className="text-re-red font-mono">§</span>
            <span>{s.title}</span>
            {s.section && <span className="text-re-muted">— {s.section}</span>}
          </a>
        ))}
      </div>
    </div>
  )
}