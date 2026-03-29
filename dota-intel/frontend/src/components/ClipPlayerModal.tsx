import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import Hls from 'hls.js'
import { X, Mic2 } from 'lucide-react'
import { useClipPlayer } from '../context/ClipPlayerContext'

export default function ClipPlayerModal() {
  const { activeClip, closeClip } = useClipPlayer()
  const closeButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (activeClip) {
      closeButtonRef.current?.focus()
      const handleEsc = (e: KeyboardEvent) => {
        if (e.key === 'Escape') closeClip()
      }
      window.addEventListener('keydown', handleEsc)
      return () => window.removeEventListener('keydown', handleEsc)
    }
  }, [activeClip, closeClip])

  if (!activeClip) return null

  return createPortal(
    <div 
      role="dialog" 
      aria-modal="true" 
      aria-label="Clip player"
      className="fixed inset-0 z-[100] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
      onClick={closeClip}
    >
      <div 
        className="relative w-full max-w-[900px] bg-[#0C0C0F] border border-[#252535] rounded-xl overflow-hidden shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* Close Button */}
        <button 
          ref={closeButtonRef}
          onClick={closeClip}
          className="absolute top-3 right-3 z-10 w-9 h-9 flex items-center justify-center rounded-full bg-black/70 hover:bg-black text-white transition-all border border-white/10"
        >
          <X size={18} />
        </button>

        {/* Video Player */}
        <div className="aspect-video bg-black flex items-center justify-center">
          <HlsPlayerInModal 
            hlsUrl={activeClip.hlsUrl} 
            startTime={activeClip.start} 
            endTime={activeClip.end} 
          />
        </div>

        {/* Metadata */}
        <div className="p-6 space-y-4">
          <div className="flex items-center gap-2">
            {activeClip.eventLabel && <EventBadge label={activeClip.eventLabel} />}
          </div>

          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold text-[#E8E8F0]">
              {activeClip.playerName} {activeClip.hero && `· ${activeClip.hero}`} {activeClip.opponent && `vs ${activeClip.opponent}`}
            </h2>
            {activeClip.aiScore !== undefined && <AiScorePill score={activeClip.aiScore} />}
          </div>

          <div className="flex items-center gap-3 text-sm text-[#555568]">
            <span>{formatTime(activeClip.start)} – {formatTime(activeClip.end)} in VOD</span>
            {activeClip.matchId && (
              <>
                <span className="w-1 h-1 rounded-full bg-[#3A3A55]" />
                <span>Match {activeClip.matchId}</span>
              </>
            )}
          </div>

          {activeClip.transcription && (
            <div className="pt-2 border-t border-white/5">
              <blockquote className="text-sm italic text-[#9898B0] leading-relaxed">
                "{activeClip.transcription}"
              </blockquote>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
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
        video.play().catch(e => console.error('[clip-player] Native play failed:', e))
      })
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = hlsUrl
      video.addEventListener('loadedmetadata', () => {
        video.currentTime = startTime
        video.play().catch(e => console.error('[clip-player] Safari play failed:', e))
      }, { once: true })
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
    <video
      ref={videoRef}
      controls
      autoPlay
      playsInline
      className="w-full h-full"
    />
  )
}

function EventBadge({ label }: { label: string }) {
  const typeColors: Record<string, { bg: string; text: string }> = {
    RAMPAGE: { bg: 'bg-[#2A0A0A]', text: 'text-accent-loss' },
    GODLIKE: { bg: 'bg-[#2A200A]', text: 'text-[#FFB800]' },
    TEAMFIGHT: { bg: 'bg-[#0A1A2A]', text: 'text-[#60A5FA]' },
    OBJECTIVE: { bg: 'bg-obsidian-darker', text: 'text-accent-win' },
    CLUTCH: { bg: 'bg-[#1A0A33]', text: 'text-accent-ai' },
  }
  const colors = typeColors[label] ?? typeColors.CLUTCH
  return (
    <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full ${colors.bg} ${colors.text} uppercase tracking-wider`}>
      {label}
    </span>
  )
}

function AiScorePill({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-1.5 h-6 px-3 rounded-full bg-[#1A120A] border border-[#3D2D10]">
      <Mic2 size={12} className="text-[#FFB800]" />
      <span className="text-xs font-bold text-[#FFB800]">
        {score.toFixed(1)}
      </span>
    </div>
  )
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
