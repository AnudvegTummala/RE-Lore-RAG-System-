import type { StreamToken, GraphNode, GraphEdge } from '../types'

const BASE = '/api'

export async function* streamQuery(query: string): AsyncGenerator<StreamToken> {
  const response = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query }),
  })

  if (!response.ok) throw new Error(`Query failed: ${response.statusText}`)
  if (!response.body) throw new Error('No response body')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          yield JSON.parse(line.slice(6)) as StreamToken
        } catch {
          // skip malformed events
        }
      }
    }
  }
}

export async function fetchEntitySubgraph(entityId: string): Promise<{ nodes: GraphNode[]; edges: GraphEdge[] }> {
  const res = await fetch(`${BASE}/graph/${entityId}`)
  if (!res.ok) throw new Error(`Graph fetch failed: ${res.statusText}`)
  return res.json()
}

export async function searchEntities(q: string): Promise<{ results: unknown[] }> {
  const res = await fetch(`${BASE}/search?q=${encodeURIComponent(q)}`)
  if (!res.ok) throw new Error(`Search failed: ${res.statusText}`)
  return res.json()
}

export async function healthCheck(): Promise<{ status: string; services: Record<string, string> }> {
  const res = await fetch(`${BASE}/health`)
  return res.json()
}
