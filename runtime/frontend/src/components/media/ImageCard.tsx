import type { ImageResult } from '../../types'

interface ImageCardProps {
  image: ImageResult
}

export default function ImageCard({ image }: ImageCardProps) {
  return (
    <div className="w-28 rounded overflow-hidden border border-re-border bg-re-surface-2">
      <img
        src={image.path}
        alt={image.caption}
        className="w-full h-20 object-cover"
        onError={(e) => {
          ;(e.currentTarget as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="112" height="80"><rect width="112" height="80" fill="%231a1a1a"/></svg>'
        }}
      />
      <p className="text-xs text-re-muted px-1.5 py-1 truncate font-mono">{image.caption}</p>
    </div>
  )
}
