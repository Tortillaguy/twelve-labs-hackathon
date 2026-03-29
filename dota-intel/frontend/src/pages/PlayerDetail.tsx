import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import api from '../utils/api'
import Hls from 'hls.js'
import { Sparkles, ArrowLeft, Mic2, Play, X, Video } from 'lucide-react'
import Header from '../components/Header'
import { getHeroName } from '../utils/heroes'

/**
 * Seeks an offscreen HLS video to `seekTo` seconds and captures a canvas frame.
 * Returns a data URL or null if capture fails / HLS is not available.
 * Now includes lazy-loading: only captures when `isVisible` is true.
 */
function useClipThumbnail(hlsUrl: string | null | undefined, seekTo: number, isVisible: boolean): string | null {
  const [dataUrl, setDataUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!hlsUrl || !isVisible || dataUrl) return
    let hls: Hls | null = null
    let cancelled = false

    const video = document.createElement('video')
    video.muted = true
    video.crossOrigin = 'anonymous'
    video.width = 480
    video.height = 270
    video.style.display = 'none'
    document.body.appendChild(video)

    const capture = () => {
      if (cancelled) return
      try {
        const canvas = document.createElement('canvas')
        canvas.width = video.videoWidth || 480
        canvas.height = video.videoHeight || 270
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
          const url = canvas.toDataURL('image/jpeg', 0.75)
          if (!cancelled) setDataUrl(url)
        }
      } catch {
      } finally {
        cleanup()
      }
    }

    const onSeeked = () => capture()

    const seekAndCapture = () => {
      if (cancelled) return
      video.addEventListener('seeked', onSeeked, { once: true })
      video.currentTime = seekTo
    }

    const cleanup = () => {
      if (hls) { hls.destroy(); hls = null }
      video.removeEventListener('seeked', onSeeked)
      if (video.parentNode) video.parentNode.removeChild(video)
    }

    if (Hls.isSupported()) {
      hls = new Hls({ startPosition: seekTo, maxBufferLength: 5 })
      hls.loadSource(hlsUrl)
      hls.attachMedia(video)
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        seekAndCapture()
      })
      hls.on(Hls.Events.ERROR, (_evt, data) => {
        if (data.fatal) cleanup()
      })
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = hlsUrl
      video.addEventListener('loadedmetadata', () => seekAndCapture(), { once: true })
    } else {
      cleanup()
    }

    return () => {
      cancelled = true
      cleanup()
    }
  }, [hlsUrl, seekTo, isVisible, dataUrl])

  return dataUrl
}

interface Highlight {
  video_id: string
  start: number
  end: number
  play_type: string
  excitement_score: number
  description: string
  player_name?: string
  match_id?: number
  opponent?: string
  thumbnail_url?: string
  hls_url?: string
  transcription?: string
}

interface SearchClip {
  video_id: string
  start: number
  end: number
  score: number | null
  transcription: string | null
  thumbnail_url: string | null
  hls_url: string | null
  video_thumbnail_url: string | null
}

interface MatchSummary {
  match_id: number
  opponent: string
  won: boolean
  duration_str: string
  kills: number
  deaths: number
  assists: number
  gpm: number
  hero_id: number
  clip_count: number
}

interface RankedPlayer {
  rank: number
  account_id: number
  name: string
  team: string
  kda: string
  avg_kda_ratio: number
  avg_gpm: number
  win_rate: number
  ai_impact_score: number
  highlight_count: number
  top_heroes: number[]
}

interface PlayerDetailData {
  player: RankedPlayer
  recent_matches: MatchSummary[]
  highlights: Highlight[]
}

export default function PlayerDetail() {
  const { accountId } = useParams()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const demoMode = searchParams.get('demo') === 'true'
  
  console.log(`[debug] Rendering PlayerDetail for ${accountId} (demo=${demoMode})`)

  const [data, setData] = useState<PlayerDetailData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [searchClips, setSearchClips] = useState<SearchClip[]>([])
  const [clipsLoading, setClipsLoading] = useState(false)
  const [activeClip, setActiveClip] = useState<{ hlsUrl: string; start: number; end: number } | null>(null)

  useEffect(() => {
    console.log(`[debug] Effect trigger: fetching /api/players/${accountId}`)
    setLoading(true)
    setError(null)
    api.get(`/api/players/${accountId}`, { params: { demo: demoMode } })
      .then(res => {
        console.log('[debug] Player data received:', res.data)
        setData(res.data)
      })
      .catch(err => {
        console.error('[debug] API Error:', err)
        setError(err.response?.data?.detail || err.message || 'Failed to load player data')
      })
      .finally(() => setLoading(false))
  }, [accountId, demoMode])

  // Fetch AI-discovered clips for this player from TwelveLabs search
  useEffect(() => {
    if (!data?.player.name) return
    setClipsLoading(true)
    api.get('/api/search', { params: { q: `${data.player.name} Dota 2 exciting play kill`, limit: 8 } })
      .then(res => setSearchClips(res.data.clips ?? []))
      .catch(err => console.error('Failed to search clips', err))
      .finally(() => setClipsLoading(false))
  }, [data?.player.name])

  if (loading) {
    return (
      <div className="min-h-screen bg-obsidian text-[#E8E8F0]">
        <Header 
          search={search} 
          onSearchChange={setSearch} 
          demoMode={demoMode}
          onDemoToggle={() => setSearchParams({ demo: (!demoMode).toString() })}
        />
        <div className="flex flex-col items-center justify-center h-[calc(100vh-64px)] gap-4">
          <div className="w-10 h-10 border-4 border-accent-ai/20 border-t-accent-ai rounded-full animate-spin" />
          <span className="text-[#555568] animate-pulse">Analyzing player archives...</span>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-obsidian text-[#E8E8F0]">
        <Header 
          search={search} 
          onSearchChange={setSearch} 
          demoMode={demoMode}
          onDemoToggle={() => setSearchParams({ demo: (!demoMode).toString() })}
        />
        <div className="flex flex-col items-center justify-center h-[calc(100vh-64px)] gap-4 px-10 text-center">
          <div className="w-16 h-16 rounded-full bg-accent-loss/10 flex items-center justify-center text-accent-loss">
            <X size={32} />
          </div>
          <h2 className="text-xl font-bold">Failed to Load Profile</h2>
          <p className="text-[#555568] max-w-md">
            {error || "We couldn't find this player in our indexed archives. Try enabling Demo Mode or running the ingestion pipeline."}
          </p>
          <button
            onClick={() => navigate(demoMode ? '/?demo=true' : '/')}
            className="mt-4 px-6 py-2 bg-obsidian-light border border-obsidian-border rounded-lg hover:border-accent-dota transition-all text-sm font-semibold"
          >
            Return to Leaderboard
          </button>
        </div>
      </div>
    )
  }

  const { player, recent_matches = [], highlights = [] } = data
  const kdaParts = (player?.kda || '0 / 0 / 0').split(' / ')
  const topHeroes = player?.top_heroes || []

  return (
    <div className="min-h-screen bg-obsidian text-[#E8E8F0]">
      <Header 
        search={search} 
        onSearchChange={setSearch} 
        demoMode={demoMode}
        onDemoToggle={() => setSearchParams({ demo: (!demoMode).toString() })}
      />

      <main className="max-w-[1360px] mx-auto px-10 py-7 space-y-5">
        {/* Back Button */}
        <button
          onClick={() => navigate(demoMode ? '/?demo=true' : '/')}
          className="flex items-center gap-2 text-[#555568] hover:text-accent-dota transition-colors text-sm mb-2"
        >
          <ArrowLeft size={14} />
          <span>Back to Leaderboard</span>
        </button>

        {/* Player Profile Card */}
        <div className="bg-obsidian-dark border border-obsidian-border rounded-xl p-[22px_28px] flex items-center gap-7">
          <div className="w-[60px] h-[60px] rounded-full bg-accent-dota flex-shrink-0" />
          <div className="space-y-1.5">
            <h1 className="text-[22px] font-bold">{player?.name || 'Unknown Player'}</h1>
            <div className="flex items-center gap-2.5">
              <span className="text-[13px] text-[#6B6B88]">{player?.team || 'No Team'}</span>
              <RoleBadge label="Carry" />
              {topHeroes.slice(0, 3).map(id => (
                <HeroBadge key={id} label={getHeroName(id)} />
              ))}
            </div>
          </div>
          <div className="flex-1" />
          <div className="flex flex-col items-end gap-2">
            <div className="flex items-center h-[30px] px-3.5 rounded-sm bg-[#0D1620] border border-[#1E4080]">
              <span className="text-xs font-semibold text-[#60A5FA]">
                Rank #{player?.rank || '?'}  ·  ESL One Birmingham 2026
              </span>
            </div>
            <span className="text-xs text-[#555568]">
              {recent_matches.length} matches played  ·  {recent_matches.filter(m => m.won).length}W  {recent_matches.filter(m => !m.won).length}L
            </span>
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-4 gap-3.5">
          <MiniStat label="KDA RATIO" value={(player?.avg_kda_ratio || 0).toFixed(2)} subtitle={`${kdaParts[0]} / ${kdaParts[1]} / ${kdaParts[2]} avg`} />
          <MiniStat label="GOLD PER MIN" value={(player?.avg_gpm || 0).toFixed(0)} subtitle="Top 3% of all carries" valueColor="text-accent-win" />
          <MiniStat label="WIN RATE" value={`${((player?.win_rate || 0) * 100).toFixed(0)}%`} subtitle={`${recent_matches.filter(m => m.won).length} wins from ${recent_matches.length} matches`} />
          <MiniStat
            label="AI IMPACT SCORE ✦"
            value={(player?.ai_impact_score || 0).toFixed(1)}
            subtitle={`Ranked #${player?.rank || '?'} in competition`}
            labelColor="text-accent-ai"
            valueColor="text-accent-ai"
            borderColor="border-accent-ai"
          />
        </div>

        {/* Responsive Two-Column Layout */}
        <div className="flex flex-col xl:flex-row gap-5">
          {/* Left: Match History */}
          <div className="w-full xl:w-[420px] flex-shrink-0 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-bold uppercase tracking-wider text-[#555568]">Verified Match History</span>
              <span className="text-xs text-[#555568]">{recent_matches.length} matches</span>
            </div>
            {recent_matches.length === 0 ? (
              <div className="bg-obsidian-dark border border-obsidian-border rounded-lg p-6 text-center text-sm text-[#555568]">
                No match data available yet.
              </div>
            ) : (
              recent_matches.map(match => (
                <MatchCard key={match.match_id} match={match} />
              ))
            )}
          </div>

          {/* Right: AI Highlights */}
          <div className="flex-1 space-y-6">
            {/* Verified Highlights Section */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles size={16} className="text-accent-ai" />
                  <span className="text-sm font-bold uppercase tracking-wider text-accent-ai">Verified AI Highlights</span>
                </div>
                <div className="flex items-center h-[22px] px-2.5 rounded-full bg-[#1A0A33] border border-[#3D2475]">
                  <span className="text-[9px] font-semibold text-accent-ai">MATCH CORRELATED</span>
                </div>
              </div>

              {/* Video Player */}
              {activeClip && (
                <div className="relative mb-4">
                  <button
                    onClick={() => setActiveClip(null)}
                    className="absolute top-2 right-2 z-10 w-7 h-7 flex items-center justify-center rounded-full bg-black/70 hover:bg-black text-white transition-colors"
                  >
                    <X size={14} />
                  </button>
                  <HlsPlayer hlsUrl={activeClip.hlsUrl} startTime={activeClip.start} endTime={activeClip.end} />
                </div>
              )}

              {highlights.length === 0 ? (
                <div className="bg-obsidian-dark border border-obsidian-border rounded-lg p-10 text-center text-sm text-[#555568]">
                  No verified highlights found for these matches.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {highlights.map((hl, i) => (
                    <HighlightCard
                      key={i}
                      highlight={hl}
                      onPlay={() => hl.hls_url && setActiveClip({ hlsUrl: hl.hls_url, start: hl.start, end: hl.end })}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Global Discovery Section */}
            <div className="space-y-3 pt-4 border-t border-obsidian-border/50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Video size={16} className="text-[#60A5FA]" />
                  <span className="text-sm font-bold uppercase tracking-wider text-[#60A5FA]">Global AI Discovery</span>
                </div>
                <div className="text-[10px] text-[#555568] italic">Semantic search across full archive</div>
              </div>

              {clipsLoading ? (
                <div className="bg-obsidian-dark border border-obsidian-border rounded-lg p-10 text-center text-sm text-[#555568]">
                  <div className="w-6 h-6 border-2 border-[#60A5FA]/20 border-t-[#60A5FA] rounded-full animate-spin mx-auto mb-2" />
                  Searching archive for related plays...
                </div>
              ) : searchClips.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {searchClips.map((clip, i) => (
                    <SearchClipCard
                      key={i}
                      clip={clip}
                      onPlay={() => clip.hls_url && setActiveClip({ hlsUrl: clip.hls_url, start: clip.start, end: clip.end })}
                    />
                  ))}
                </div>
              ) : (
                <div className="text-center py-6 text-xs text-[#3A3A55]">
                  No additional clips found in global archive.
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

function MiniStat({
  label, value, subtitle,
  labelColor = 'text-[#555568]',
  valueColor = 'text-[#E8E8F0]',
  borderColor = 'border-obsidian-border',
}: {
  label: string; value: string; subtitle: string
  labelColor?: string; valueColor?: string; borderColor?: string
}) {
  return (
    <div className={`bg-obsidian-dark border ${borderColor} rounded-lg p-4 space-y-1.5`}>
      <div className={`text-[10px] font-semibold ${labelColor}`}>{label}</div>
      <div className={`text-[22px] font-bold tabular-nums ${valueColor}`}>{value}</div>
      <div className="text-[11px] text-[#6B6B88]">{subtitle}</div>
    </div>
  )
}

function MatchCard({ match }: { match: MatchSummary }) {
  return (
    <div className="bg-obsidian-dark border border-obsidian-border rounded-lg p-[14px_16px] flex items-center gap-3.5">
      <div className={`w-1 h-9 rounded-sm flex-shrink-0 ${match.won ? 'bg-accent-win' : 'bg-accent-loss'}`} />
      <div className="flex-1 space-y-0.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-[#E8E8F0]">vs {match.opponent}</span>
          <span className="text-[11px] text-[#555568]">{match.duration_str}</span>
        </div>
        <div className="flex items-center gap-2.5">
          <span className={`text-[11px] ${match.won ? 'text-accent-win' : 'text-accent-loss'}`}>
            {match.kills} / {match.deaths} / {match.assists}
          </span>
          <span className="text-[11px] text-[#6B6B88]">{match.gpm} GPM</span>
          <span className="text-[11px] text-accent-ai">{getHeroName(match.hero_id)}</span>
        </div>
      </div>
      {match.clip_count > 0 && (
        <div className="flex items-center h-5 px-2 rounded-full bg-[#160D28]">
          <span className="text-[9px] font-bold text-accent-ai">{match.clip_count} clips</span>
        </div>
      )}
    </div>
  )
}

function HlsPlayer({ hlsUrl, startTime, endTime }: { hlsUrl: string; startTime: number; endTime: number }) {
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

    // Auto-pause at end time
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
      className="w-full rounded-lg border border-obsidian-border"
    />
  )
}

function SearchClipCard({ clip, onPlay }: { clip: SearchClip; onPlay: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setIsVisible(true)
        observer.disconnect()
      }
    }, { threshold: 0.1 })
    if (containerRef.current) observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  const thumbnail = useClipThumbnail(clip.hls_url, clip.start, isVisible)
  // Fall back to static video thumbnail while the frame is being captured
  const displayThumb = thumbnail ?? clip.video_thumbnail_url

  return (
    <div
      ref={containerRef}
      onClick={onPlay}
      className="bg-obsidian-dark border border-obsidian-border rounded-lg overflow-hidden cursor-pointer hover:border-accent-ai/50 transition-all group"
    >
      <div className="h-[120px] bg-[#1A1A26] relative flex items-center justify-center">
        {displayThumb ? (
          <img
            src={displayThumb}
            alt=""
            className={`w-full h-full object-cover transition-opacity duration-500 ${thumbnail ? 'opacity-100' : 'opacity-60'}`}
          />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-[#1A1A26] to-[#0A0A14] animate-pulse" />
        )}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-10 h-10 rounded-full bg-accent-ai/80 flex items-center justify-center group-hover:bg-accent-ai transition-colors">
            <Play size={18} className="text-white ml-0.5" fill="currentColor" />
          </div>
        </div>
        <div className="absolute bottom-1.5 right-1.5 bg-black/70 rounded px-1.5 py-0.5">
          <span className="text-[10px] text-white tabular-nums">
            {formatTime(clip.start)} – {formatTime(clip.end)}
          </span>
        </div>
      </div>
      <div className="p-[10px_12px] space-y-1.5">
        <div className="flex items-center gap-1.5">
          <span className="text-[8px] font-bold px-2 py-0.5 rounded-full bg-[#0A1A2A] text-[#60A5FA]">
            AI MATCH
          </span>
        </div>
        {clip.transcription && (
          <div className="text-xs text-[#E8E8F0] leading-tight line-clamp-2">
            "{clip.transcription}"
          </div>
        )}
        <span className="text-[10px] text-[#555568] block">
          {formatTime(clip.start)} in VOD
        </span>
      </div>
    </div>
  )
}

function HighlightCard({ highlight, onPlay }: { highlight: Highlight; onPlay?: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setIsVisible(true)
        observer.disconnect()
      }
    }, { threshold: 0.1 })
    if (containerRef.current) observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  const typeColors: Record<string, { bg: string; text: string }> = {
    RAMPAGE: { bg: 'bg-[#2A0A0A]', text: 'text-accent-loss' },
    GODLIKE: { bg: 'bg-[#2A200A]', text: 'text-[#FFB800]' },
    TEAMFIGHT: { bg: 'bg-[#0A1A2A]', text: 'text-[#60A5FA]' },
    OBJECTIVE: { bg: 'bg-obsidian-darker', text: 'text-accent-win' },
    CLUTCH: { bg: 'bg-[#1A0A33]', text: 'text-accent-ai' },
  }
  const colors = typeColors[highlight.play_type] ?? typeColors.CLUTCH

  const thumbBg: Record<string, string> = {
    RAMPAGE: 'bg-[#1A1A26]',
    GODLIKE: 'bg-[#26201A]',
    TEAMFIGHT: 'bg-[#1A1A26]',
    OBJECTIVE: 'bg-[#1A261A]',
    CLUTCH: 'bg-[#1A1520]',
  }

  // Capture a frame from the highlight's exact start position in the HLS stream
  const thumbnail = useClipThumbnail(highlight.hls_url, highlight.start, isVisible)
  const displayThumb = thumbnail ?? highlight.thumbnail_url

  return (
    <div
      ref={containerRef}
      onClick={onPlay}
      className={`bg-obsidian-dark border border-obsidian-border rounded-lg overflow-hidden ${onPlay ? 'cursor-pointer hover:border-accent-ai/50' : ''} transition-all group`}
    >
      <div className={`h-[120px] ${thumbBg[highlight.play_type] ?? 'bg-obsidian-lighter'} relative flex items-center justify-center`}>
        {displayThumb ? (
          <img
            src={displayThumb}
            alt=""
            className={`w-full h-full object-cover transition-opacity duration-500 ${thumbnail ? 'opacity-100' : 'opacity-70'}`}
          />
        ) : (
          <div className="w-full h-full animate-pulse opacity-30 bg-gradient-to-br from-current to-transparent" />
        )}
        {onPlay && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-10 h-10 rounded-full bg-accent-ai/80 flex items-center justify-center group-hover:bg-accent-ai transition-colors">
              <Play size={18} className="text-white ml-0.5" fill="currentColor" />
            </div>
          </div>
        )}
        <div className="absolute bottom-1.5 right-1.5 bg-black/70 rounded px-1.5 py-0.5">
          <span className="text-[10px] text-white tabular-nums">
            {formatTime(highlight.start)} – {formatTime(highlight.end)}
          </span>
        </div>
      </div>
      <div className="p-[10px_12px] space-y-1.5">
        <div className="flex items-center gap-1.5">
          <span className={`text-[8px] font-bold px-2 py-0.5 rounded-full ${colors.bg} ${colors.text}`}>
            {highlight.play_type}
          </span>
        </div>
        <div className="text-xs font-semibold text-[#E8E8F0] leading-tight">
          {highlight.description}
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-[#555568]">
            {formatTime(highlight.start)}  ·  vs {highlight.opponent ?? 'Unknown'}
          </span>
          {highlight.excitement_score > 0 && (
            <div className="flex items-center gap-1">
              <Mic2 size={10} className="text-[#FFB800]" />
              <span className="text-[10px] font-bold text-[#FFB800]">
                {highlight.excitement_score.toFixed(1)}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function RoleBadge({ label }: { label: string }) {
  return (
    <div className="flex items-center h-[22px] px-2.5 rounded-full bg-[#0D2E0D] border border-[#1A5C1A]">
      <span className="text-[11px] font-semibold text-[#22C55E]">{label}</span>
    </div>
  )
}

function HeroBadge({ label }: { label: string }) {
  return (
    <div className="flex items-center h-[22px] px-2.5 rounded-full bg-[#1A1520] border border-[#3D2060]">
      <span className="text-[11px] font-semibold text-accent-ai">{label}</span>
    </div>
  )
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}
