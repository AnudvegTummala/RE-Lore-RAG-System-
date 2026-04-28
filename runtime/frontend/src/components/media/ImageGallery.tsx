import type { ImageResult } from '../../types'
import ImageCard from './ImageCard'

interface ImageGalleryProps {
  images: ImageResult[]
}

export default function ImageGallery({ images }: ImageGalleryProps) {
  if (images.length === 0) return null

  return (
    <div className="space-y-1">
      <p className="text-xs text-re-muted font-mono uppercase tracking-wider">Concept Art</p>
      <div className="flex gap-2 flex-wrap">
        {images.map((img) => (
          <ImageCard key={img.image_id} image={img} />
        ))}
      </div>
    </div>
  )
}
