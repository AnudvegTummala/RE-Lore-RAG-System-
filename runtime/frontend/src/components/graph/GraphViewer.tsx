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

  // Initialise Cytoscape once the container div is in the DOM.
  useEffect(() => {
    if (!containerRef.current) return

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements: [],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele) =>
              ENTITY_COLORS[ele.data('labels')?.[0]] ?? '#555',
            label: 'data(name)',
            color: '#d4d4d4',
            'font-size': 10,
            'text-valign': 'bottom',
            'text-margin-y': 4,
            width: 28,
            height: 28,
          },
        },
        {
          selector: 'edge',
          style: {
            'line-color': '#3a3a3a',
            'target-arrow-color': '#3a3a3a',
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
    })

    cyRef.current.on('tap', 'node', (evt) => {
      setSelectedNode(evt.target.id())
    })

    return () => {
      cyRef.current?.destroy()
      cyRef.current = null
    }
  }, [setSelectedNode])

  // Re-render whenever activeGraph changes.
  useEffect(() => {
    const cy = cyRef.current
    if (!cy || !activeGraph || activeGraph.nodes.length === 0) return

    // Force Cytoscape to recalculate container dimensions (flex-1 may have
    // resolved to 0px at init time if the parent flex layout wasn't settled).
    cy.resize()
    cy.elements().remove()

    cy.add([
      ...activeGraph.nodes.map((n) => ({ data: { id: n.id, ...n } })),
      ...activeGraph.edges.map((e, i) => ({
        data: { id: `e${i}`, source: e.source, target: e.target, type: e.type },
      })),
    ])

    // Run layout then fit the viewport to the new elements.
    const layout = cy.layout({
      name: 'cose',
      animate: false,       // skip animation so fit() sees final positions
      randomize: true,
      fit: true,            // cose will fit after completion
      padding: 24,
    })
    layout.on('layoutstop', () => {
      cy.fit(undefined, 24)
    })
    layout.run()
  }, [activeGraph])

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-re-border shrink-0">
        <p className="text-xs text-re-muted font-mono uppercase tracking-wider">Knowledge Graph</p>
      </div>
      <div ref={containerRef} className="flex-1 min-h-0 bg-re-dark" />
      <GraphLegend />
      {selectedNode && <NodeDetails nodeId={selectedNode} />}
    </div>
  )
}
