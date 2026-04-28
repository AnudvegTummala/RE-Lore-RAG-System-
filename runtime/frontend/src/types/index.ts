export interface Source {
  entity_id: string
  title: string
  section: string
  snippet: string
  source_url: string
}

export interface ImageResult {
  image_id: string
  path: string
  caption: string
}

export interface GraphNode {
  id: string
  labels: string[]
  name: string
  entity_type?: string
}

export interface GraphEdge {
  source: string
  type: string
  target: string
}

export interface GraphPayload {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface QueryResponse {
  answer: string
  sources: Source[]
  images: ImageResult[]
  graph: GraphPayload
}

export interface StreamToken {
  token?: string
  done?: boolean
  answer?: string
  sources?: Source[]
  images?: ImageResult[]
  graph?: GraphPayload
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  images?: ImageResult[]
  graph?: GraphPayload
  isStreaming?: boolean
}
