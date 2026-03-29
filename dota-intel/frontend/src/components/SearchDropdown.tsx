import { Search, AlertTriangle, Play } from 'lucide-react'
import type { SearchClip } from '../types/search'

interface SearchDropdownProps {
  status: 'loading' | 'error' | 'done'
  clips: SearchClip[]
  query: string
  onSelect: (clip: SearchClip) => void
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function scoreColor(score: number): string {
  if (score >= 0.8) return 'bg-[#22C55E]'
  if (score >= 0.6) return 'bg-[#FFB800]'
  return 'bg-[#FF4444]'
}

function SearchResultRow({ clip, onSelect }: { clip: SearchClip; onSelect: (clip: SearchClip) => void }) {
  const thumb = clip.thumbnail_url || clip.video_thumbnail_url

  return (
    <div
      onClick={() => onSelect(clip)}
      className="flex items-center gap-3 h-[54px] px-3 cursor-pointer hover:bg-obsidian-lighter/30 transition-colors"
    >
      {/* Thumbnail */}
      <div className="w-[60px] h-[34px] flex-shrink-0 rounded overflow-hidden bg-obsidian-lighter">
        {thumb ? (
          <img
            src={thumb}
            loading="lazy"
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full bg-obsidian-lighter" />
        )}
      </div>

      {/* Center: timestamp + score + transcription */}
      <div className="flex-1 min-w-0 space-y-0.5">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold font-mono text-[#60A5FA]">
            {formatTime(clip.start)}
          </span>
          <div className={`w-1.5 h-1.5 rounded-full ${scoreColor(clip.score)}`} />
          <span className="text-[9px] text-[#555568]">{(clip.score * 100).toFixed(0)}% match</span>
        </div>
        {clip.transcription && (
          <p className="text-[11px] text-[#9898B0] leading-tight line-clamp-2 truncate">
            {clip.transcription}
          </p>
        )}
      </div>

      {/* Play button */}
      <div className="w-6 h-6 flex items-center justify-center rounded-full bg-obsidian-lighter text-[#555568] hover:text-white hover:bg-accent-dota/20 transition-colors flex-shrink-0">
        <Play size={10} fill="currentColor" />
      </div>
    </div>
  )
}

export default function SearchDropdown({ status, clips, query, onSelect }: SearchDropdownProps) {
  return (
    <div className="absolute top-full mt-1.5 right-0 w-[420px] bg-obsidian-dark border border-obsidian-border rounded-lg overflow-hidden z-[100] shadow-2xl">
      {/* Header row */}
      {status === 'done' && clips.length > 0 && (
        <div className="flex items-center justify-between px-3 py-2 border-b border-obsidian-border/50">
          <span className="text-[9px] font-bold tracking-widest text-accent-ai uppercase">
            Twelve Labs AI
          </span>
          <span className="text-[9px] text-[#555568]">
            {clips.length} moment{clips.length !== 1 ? 's' : ''} found
          </span>
        </div>
      )}

      {/* Loading: 3 skeleton rows */}
      {status === 'loading' && (
        <div className="divide-y divide-obsidian-border/30">
          {[0, 1, 2].map(i => (
            <div key={i} className="flex items-center gap-3 h-[54px] px-3">
              <div className="w-[60px] h-[34px] rounded bg-obsidian-lighter animate-pulse flex-shrink-0" />
              <div className="flex-1 space-y-1.5">
                <div className="h-2 w-16 rounded bg-obsidian-lighter animate-pulse" />
                <div className="h-2 w-40 rounded bg-obsidian-lighter animate-pulse" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {status === 'error' && (
        <div className="flex items-center gap-2.5 h-[54px] px-3 text-[#555568]">
          <AlertTriangle size={14} className="text-[#FF4444]" />
          <span className="text-[12px]">Search unavailable</span>
        </div>
      )}

      {/* Empty */}
      {status === 'done' && clips.length === 0 && (
        <div className="flex items-center gap-2.5 h-[54px] px-3 text-[#555568]">
          <Search size={14} />
          <span className="text-[12px]">No moments found for "{query}"</span>
        </div>
      )}

      {/* Results */}
      {status === 'done' && clips.length > 0 && (
        <div className="divide-y divide-obsidian-border/30">
          {clips.map((clip, i) => (
            <SearchResultRow key={`${clip.video_id}-${clip.start}-${i}`} clip={clip} onSelect={onSelect} />
          ))}
        </div>
      )}
    </div>
  )
}
