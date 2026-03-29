import { useState } from 'react'
import { getHeroImageUrl, getHeroName } from '../utils/heroes'

const FALLBACK_COLORS = ['#E84545', '#60A5FA', '#22C55E', '#FFB800', '#A78BFA', '#FB923C']

const SIZE_MAP = {
  sm: 20,
  md: 28,
  lg: 60,
}

interface HeroPortraitProps {
  heroId: number
  size: 'sm' | 'md' | 'lg'
  className?: string
}

export default function HeroPortrait({ heroId, size, className = '' }: HeroPortraitProps) {
  const [imgError, setImgError] = useState(false)
  const px = SIZE_MAP[size]
  const url = getHeroImageUrl(heroId)
  const name = getHeroName(heroId)
  const fallbackColor = FALLBACK_COLORS[heroId % FALLBACK_COLORS.length]

  if (!url || imgError) {
    return (
      <div
        className={`flex-shrink-0 rounded-sm flex items-center justify-center text-white font-bold ${className}`}
        style={{ width: px, height: px, backgroundColor: fallbackColor, fontSize: px * 0.45 }}
      >
        {name[0]}
      </div>
    )
  }

  return (
    <img
      src={url}
      alt={name}
      loading="lazy"
      decoding="async"
      width={px}
      height={px}
      className={`object-cover rounded-sm flex-shrink-0 ${className}`}
      style={{ width: px, height: px }}
      onError={() => setImgError(true)}
    />
  )
}
