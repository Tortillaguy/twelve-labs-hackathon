import { useState, useEffect, useRef } from 'react'
import { Search, Trophy, Sparkles, Loader2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { SearchClip } from '../types/search'
import SearchDropdown from './SearchDropdown'
import ClipPreviewModal from './ClipPreviewModal'

interface HeaderProps {
  search: string
  onSearchChange: (value: string) => void
  demoMode?: boolean
  onDemoToggle?: () => void
}

type SearchStatus = 'idle' | 'loading' | 'error' | 'done'

export default function Header({ search, onSearchChange, demoMode, onDemoToggle }: HeaderProps) {
  const [results, setResults] = useState<SearchClip[]>([])
  const [status, setStatus] = useState<SearchStatus>('idle')
  const [selectedClip, setSelectedClip] = useState<SearchClip | null>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)

  // Debounced semantic search with AbortController
  useEffect(() => {
    if (search.length < 2) {
      setStatus('idle')
      setResults([])
      return
    }

    setStatus('loading')
    const controller = new AbortController()

    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/search?q=${encodeURIComponent(search)}&limit=6`, {
          signal: controller.signal,
        })
        if (!res.ok) throw new Error('Search failed')
        const data = await res.json()
        setResults(data.clips ?? [])
        setStatus('done')
      } catch (err) {
        if ((err as Error).name === 'AbortError') return
        setStatus('error')
      }
    }, 350)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [search])

  // Click-outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setStatus('idle')
        setResults([])
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Escape key to close dropdown
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setStatus('idle')
        setResults([])
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [])

  return (
    <>
      <header className="h-16 bg-obsidian-darker border-b border-obsidian-border px-10 flex items-center justify-between sticky top-0 z-50">
        <Link
          to={demoMode ? '/?demo=true' : '/'}
          className="flex items-center gap-3.5 hover:opacity-80 transition-opacity"
        >
          <div className="w-7 h-7 bg-accent-dota rounded-sm flex items-center justify-center">
            <Trophy size={16} className="text-white" />
          </div>
          <span className="font-bold text-sm tracking-[2px] text-[#E8E8F0]">DOTA INTEL</span>
        </Link>

        <div className="flex items-center gap-3.5">
          <div className="w-px h-5 bg-obsidian-border-muted mx-0.5" />
          <span className="text-[13px] text-[#6B6B88]">ESL One Birmingham 2026</span>
        </div>

        <div className="flex items-center gap-6">
          {/* Demo Mode Toggle */}
          <button
            onClick={onDemoToggle}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border transition-all ${
              demoMode
                ? 'bg-accent-ai/10 border-accent-ai/50 text-accent-ai shadow-[0_0_15px_rgba(167,139,250,0.2)]'
                : 'bg-obsidian-lighter border-obsidian-border text-[#555568] hover:border-[#3A3A55]'
            }`}
          >
            <Sparkles size={14} className={demoMode ? 'animate-pulse' : ''} />
            <span className="text-[11px] font-bold tracking-tight">DEMO MODE</span>
            <div className={`w-6 h-3 rounded-full relative transition-colors ${demoMode ? 'bg-accent-ai' : 'bg-[#333345]'}`}>
              <div className={`absolute top-0.5 w-2 h-2 rounded-full bg-white transition-all ${demoMode ? 'left-3.5' : 'left-0.5'}`} />
            </div>
          </button>

          {/* Search — semantic video search + player name filter */}
          <div ref={wrapperRef} className="relative">
            <div className="relative group">
              {status === 'loading' ? (
                <Loader2 className="absolute left-3.5 top-1/2 -translate-y-1/2 text-accent-dota animate-spin" size={14} />
              ) : (
                <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#555568] group-focus-within:text-accent-dota transition-colors" size={14} />
              )}
              <input
                type="text"
                placeholder="Search players or moments..."
                className="bg-obsidian-lighter border border-obsidian-border rounded-lg h-9 w-[240px] pl-9 pr-4 text-[13px] font-mono focus:outline-none focus:border-accent-dota/50 transition-all placeholder:text-[#3A3A55]"
                value={search}
                onChange={(e) => onSearchChange(e.target.value)}
              />
            </div>

            {/* Semantic search dropdown */}
            {status !== 'idle' && (
              <SearchDropdown
                status={status}
                clips={results}
                query={search}
                onSelect={(clip) => {
                  setSelectedClip(clip)
                  setStatus('idle')
                  setResults([])
                }}
              />
            )}
          </div>

          <div className="w-[34px] h-[34px] rounded-full bg-accent-dota" />
        </div>
      </header>

      {/* Clip preview modal */}
      {selectedClip && (
        <ClipPreviewModal
          clip={selectedClip}
          onClose={() => setSelectedClip(null)}
        />
      )}
    </>
  )
}
