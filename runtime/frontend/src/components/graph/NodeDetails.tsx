import { useAppStore } from '../../store/appStore'

interface NodeDetailsProps {
  nodeId: string
}

export default function NodeDetails({ nodeId }: NodeDetailsProps) {
  const { activeGraph } = useAppStore()
  const node = activeGraph?.nodes.find((n) => n.id === nodeId)

  if (!node) return null

  return (
    <div className="border-t border-re-border p-3 bg-re-surface text-xs font-mono">
      <p className="text-re-muted uppercase tracking-wider mb-1">Selected</p>
      <p className="text-white font-semibold">{node.name || nodeId}</p>
      <p className="text-re-muted">{node.labels.join(', ')}</p>
    </div>
  )
}
