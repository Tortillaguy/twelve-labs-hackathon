import { useEffect, useRef } from 'react'
import Hls from 'hls.js'
import { X } from 'lucide-react'
import type { SearchClip } from '../types/search'

interface ClipPreviewModalProps {
  clip: SearchClip
  onClose: () => void
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function scoreColor(score: number): string {
  if (score >= 0.8) return 'text-[#22C55E]'
  if (score >= 0.6) return 'text-[#FFB800]'
  return 'text-[#FF4444]'
}

function HlsPlayerInModal({ hlsUrl, startTime, endTime }: { hlsUrl: string; startTime: number; endTime: number }) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    let hls: Hls | null = null

    if (Hls.isSupported()) {
      hls = new Hls({
        startPosition: startTime,
        maxBufferLength: 30,
        maxMaxBufferLength: 60,
      })
      hls.loadSource(hlsUrl)
      hls.attachMedia(video)
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        video.play()
      })
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari native HLS
      video.src = hlsUrl
      video.addEventListener('loadedmetadata', () => {
        video.currentTime = startTime
        video.play()
      })
    }

    const handleTimeUpdate = () => {
      if (video.currentTime >= endTime) {
        video.pause()
      }
    }
    video.addEventListener('timeupdate', handleTimeUpdate)

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate)
      if (hls) hls.destroy()
    }
  }, [hlsUrl, startTime, endTime])

  return (
    <div className="relative aspect-video bg-black">
      <video
        ref={videoRef}
        controls
        muted
        autoPlay
        className="w-full h-full"
      />
    </div>
  )
}

export default function ClipPreviewModal({ clip, onClose }: ClipPreviewModalProps) {
  const panelRef = useRef<HTMLDivElement>(null)

  // Escape key to close
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-[200] bg-black/80 backdrop-blur-sm flex items-center justify-center"
      onClick={onClose}
    >
      <div
        ref={panelRef}
        className="relative bg-obsidian-dark border border-obsidian-border rounded-xl w-[760px] max-w-[90vw] overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-black/70 hover:bg-black flex items-center justify-center text-[#9898B0] hover:text-white transition-colors"
          autoFocus
        >
          <X size={16} />
        </button>

        {/* Video */}
        {clip.hls_url ? (
          <HlsPlayerInModal hlsUrl={clip.hls_url} startTime={clip.start} endTime={clip.end} />
        ) : (
          <div className="aspect-video bg-obsidian-darker flex items-center justify-center text-[#555568] text-sm">
            Video unavailable
          </div>
        )}

        {/* Metadata */}
        <div className="p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[12px] font-mono text-[#60A5FA] font-bold">
              {formatTime(clip.start)} – {formatTime(clip.end)}
            </span>
            <span className={`text-[12px] font-bold ${scoreColor(clip.score)}`}>
              {(clip.score * 100).toFixed(0)}% match
            </span>
          </div>
          {clip.transcription && (
            <p className="text-[12px] italic text-[#9898B0] leading-relaxed">
              "{clip.transcription}"
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
