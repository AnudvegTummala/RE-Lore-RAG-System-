import { useAppStore } from '../store/appStore'
import { fetchEntitySubgraph } from '../api/client'

export function useGraph() {
  const { activeGraph, selectedNode, setActiveGraph, setSelectedNode } = useAppStore()

  async function loadEntityGraph(entityId: string) {
    try {
      const graph = await fetchEntitySubgraph(entityId)
      setActiveGraph(graph)
    } catch {
      // silently ignore — graph panel stays empty
    }
  }

  return { activeGraph, selectedNode, setSelectedNode, loadEntityGraph }
}
