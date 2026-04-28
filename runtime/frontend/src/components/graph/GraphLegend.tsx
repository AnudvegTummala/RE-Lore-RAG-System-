const LEGEND = [
  { label: 'Character', color: '#8B0000' },
  { label: 'Enemy', color: '#CC4400' },
  { label: 'Game', color: '#1a4a8a' },
  { label: 'Location', color: '#2d6a4f' },
  { label: 'Organization', color: '#6a2d6a' },
  { label: 'Virus', color: '#6a6a00' },
]

export default function GraphLegend() {
  return (
    <div className="p-3 border-t border-re-border flex flex-wrap gap-2">
      {LEGEND.map(({ label, color }) => (
        <span key={label} className="flex items-center gap-1 text-xs text-re-muted">
          <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: color }} />
          {label}
        </span>
      ))}
    </div>
  )
}
