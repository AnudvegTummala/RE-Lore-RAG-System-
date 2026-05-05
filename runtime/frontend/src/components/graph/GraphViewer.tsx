import { useEffect, useRef, useCallback } from 'react'
import cytoscape from 'cytoscape'
import { useGraph } from '../../hooks/useGraph'
import NodeDetails from './NodeDetails'
import GraphLegend from './GraphLegend'

const ENTITY_COLORS: Record<string, string> = {
  Character: '#c0392b',
  Enemy: '#e67e22',
  Game: '#2980b9',
  Location: '#27ae60',
  Organization: '#8e44ad',
  Virus: '#f39c12',
}

export default function GraphViewer() {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const { activeGraph, selectedNode, setSelectedNode } = useGraph()

  // Stable callback so it never triggers Cytoscape re-init
  const handleNodeTap = useCallback(
    (evt: cytoscape.EventObject) => setSelectedNode(evt.target.id()),
    [setSelectedNode],
  )

  // Init Cytoscape once — no reactive deps
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
              ENTITY_COLORS[ele.data('labels')?.[0]] ?? '#7f8c8d',
            label: 'data(name)',
            color: '#1a1a1a',
            'font-size': 10,
            'font-weight': 600,
            'text-valign': 'bottom',
            'text-margin-y': 5,
            'text-background-color': '#2a2a2a',
            'text-background-opacity': 0.85,
            'text-background-padding': '2px',
            width: 32,
            height: 32,
            'border-width': 2,
            'border-color': '#ffffff',
          },
        },
        {
          selector: 'edge',
          style: {
            'line-color': '#95a5a6',
            'target-arrow-color': '#95a5a6',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            label: 'data(type)',
            color: '#555',
            'font-size': 8,
            width: 1.5,
          },
        },
        {
          selector: ':selected',
          style: {
            'border-color': '#e74c3c',
            'border-width': 3,
          },
        },
      ],
    })

    cyRef.current.on('tap', 'node', handleNodeTap)

    return () => {
      cyRef.current?.destroy()
      cyRef.current = null
    }
  }, [handleNodeTap]) // handleNodeTap is stable — this runs once

  // Update graph data whenever activeGraph changes
  useEffect(() => {
    const cy = cyRef.current
    if (!cy || !activeGraph || activeGraph.nodes.length === 0) return

    cy.resize()
    cy.elements().remove()

    cy.add([
      ...activeGraph.nodes.map((n) => ({ data: { ...n } })),
      ...activeGraph.edges.map((e, i) => ({
        data: { id: `e${i}`, source: e.source, target: e.target, type: e.type },
      })),
    ])

    cy.layout({ name: 'cose', animate: false, randomize: true }).run()
    cy.fit(undefined, 20)
  }, [activeGraph])

  const nodeCount = activeGraph?.nodes.length ?? 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '12px', borderBottom: '1px solid #2a2a2a', flexShrink: 0, background: 'rgba(17, 24, 39, 0.6)' }}>
        <p style={{ fontSize: '11px', color: '#d4d4d4', textTransform: 'uppercase', letterSpacing: '0.08em', margin: 0, fontWeight: 600 }}>
          Knowledge Graph{nodeCount > 0 ? ` · ${nodeCount} nodes` : ''}
        </p>
      </div>
      <div ref={containerRef} style={{ flex: 1, minHeight: 0, background: '#2a2a2a' }} />
      <GraphLegend />
      {selectedNode && <NodeDetails nodeId={selectedNode} />}
    </div>
  )
}