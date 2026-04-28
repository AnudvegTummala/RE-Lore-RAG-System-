import { useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'
import { useGraph } from '../../hooks/useGraph'
import NodeDetails from './NodeDetails'
import GraphLegend from './GraphLegend'

const ENTITY_COLORS: Record<string, string> = {
  Character: '#8B0000',
  Enemy: '#CC4400',
  Game: '#1a4a8a',
  Location: '#2d6a4f',
  Organization: '#6a2d6a',
  Virus: '#6a6a00',
}

export default function GraphViewer() {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const { activeGraph, selectedNode, setSelectedNode } = useGraph()

  useEffect(() => {
    if (!containerRef.current) return

    cyRef.current = cytoscape({
      container: containerRef.current,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele) =>
              ENTITY_COLORS[ele.data('labels')?.[0]] ?? '#444',
            label: 'data(name)',
            color: '#d4d4d4',
            'font-size': 10,
            'text-valign': 'bottom',
            'text-margin-y': 4,
          },
        },
        {
          selector: 'edge',
          style: {
            'line-color': '#2a2a2a',
            'target-arrow-color': '#2a2a2a',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: 'data(type)',
            color: '#6b6b6b',
            'font-size': 8,
          },
        },
        {
          selector: ':selected',
          style: { 'border-color': '#CC0000', 'border-width': 2 },
        },
      ],
      layout: { name: 'cose' },
    })

    cyRef.current.on('tap', 'node', (evt) => {
      setSelectedNode(evt.target.id())
    })

    return () => {
      cyRef.current?.destroy()
    }
  }, [setSelectedNode])

  useEffect(() => {
    if (!cyRef.current || !activeGraph) return
    cyRef.current.elements().remove()
    cyRef.current.add([
      ...activeGraph.nodes.map((n) => ({ data: { id: n.id, ...n } })),
      ...activeGraph.edges.map((e, i) => ({
        data: { id: `e${i}`, source: e.source, target: e.target, type: e.type },
      })),
    ])
    cyRef.current.layout({ name: 'cose' }).run()
  }, [activeGraph])

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-re-border">
        <p className="text-xs text-re-muted font-mono uppercase tracking-wider">Knowledge Graph</p>
      </div>
      <div ref={containerRef} className="flex-1 bg-re-dark" />
      <GraphLegend />
      {selectedNode && <NodeDetails nodeId={selectedNode} />}
    </div>
  )
}
