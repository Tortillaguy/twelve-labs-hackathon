import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
import { Swords, Users, Video, Zap, Play } from 'lucide-react'
import Header from '../components/Header'
import { getHeroName } from '../utils/heroes'
import HeroPortrait from '../components/HeroPortrait'

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
  avatar_url?: string
}

interface LeaderboardData {
  competition: string
  total_matches: number
  total_teams: number
  total_highlights: number
  avg_kda_top10: number
  players: RankedPlayer[]
}

export default function Leaderboard() {
  const [data, setData] = useState<LeaderboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [demoMode, setDemoMode] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    setLoading(true)
    api.get('/api/leaderboard', { params: { demo: demoMode } })
      .then(res => setData(res.data))
      .catch(err => console.error('Failed to fetch leaderboard', err))
      .finally(() => setLoading(false))
  }, [demoMode])

  const filtered = data?.players.filter(p =>
    p.name?.toLowerCase().includes(search.toLowerCase()) ||
    p.team?.toLowerCase().includes(search.toLowerCase())
  ) ?? []

  return (
    <div className="min-h-screen bg-obsidian text-[#E8E8F0]">
      <Header 
        search={search} 
        onSearchChange={setSearch} 
        demoMode={demoMode} 
        onDemoToggle={() => setDemoMode(!demoMode)} 
      />

      <main className="max-w-[1360px] mx-auto px-10 py-7 space-y-5">
        {/* Page Header */}
        <div className="flex items-center justify-between">
          <div className="space-y-1.5">
            <h1 className="text-[22px] font-bold">
              {demoMode ? 'Demo Leaderboard' : 'Competition Leaderboard'}
            </h1>
            <p className="text-xs text-[#6B6B88]">
              {demoMode 
                ? 'Showing mock data for presentation purposes' 
                : 'Player rankings across all matches  ·  OpenDota stats × TwelveLabs AI'}
            </p>
          </div>
          <div className="flex gap-2">
            <FilterButton label="All Teams" />
            <FilterButton label="All Heroes" />
            <FilterButton label="▼  AI Impact" active />
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-4 gap-3.5">
          <StatCard
            icon={<Swords size={20} className="text-accent-dota" />}
            value={data?.total_matches.toString() ?? '—'}
            label="Total Matches"
          />
          <StatCard
            icon={<Users size={20} className="text-[#60A5FA]" />}
            value={data?.total_teams.toString() ?? '—'}
            label="Teams"
          />
          <StatCard
            icon={<Video size={20} className="text-accent-ai" />}
            value={data?.total_highlights.toLocaleString() ?? '—'}
            label="AI Highlights Indexed"
          />
          <StatCard
            icon={<Zap size={20} className="text-[#FFB800]" />}
            value={data?.avg_kda_top10.toFixed(2) ?? '—'}
            label="Avg KDA  ·  Top 10"
          />
        </div>

        {/* Leaderboard Table */}
        <div className="bg-obsidian-dark border border-obsidian-border rounded-lg overflow-hidden">
          {/* Table Header */}
          <div className="flex items-center h-10 bg-obsidian-light border-b border-obsidian-border px-5">
            <div className="w-[50px] text-center text-[11px] font-semibold text-[#555568]">#</div>
            <div className="flex-1 px-3 text-[11px] font-semibold text-[#555568]">PLAYER</div>
            <div className="w-[110px] text-center text-[11px] font-semibold text-[#555568]">K / D / A</div>
            <div className="w-[80px] text-center text-[11px] font-semibold text-[#555568]">GPM</div>
            <div className="w-[90px] text-center text-[11px] font-semibold text-[#555568]">WIN %</div>
            <div className="w-[130px] text-center text-[11px] font-semibold text-accent-ai">AI IMPACT ✦</div>
            <div className="w-[140px] text-center text-[11px] font-semibold text-[#555568]">HIGHLIGHTS</div>
          </div>

          {/* Table Body */}
          {loading ? (
            <div className="h-64 flex items-center justify-center text-sm text-[#555568]">
              Loading performance data...
            </div>
          ) : filtered.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-sm text-[#555568]">
              No players found.
            </div>
          ) : (
            filtered.map((player) => (
              <div
                key={player.account_id}
                onClick={() => navigate(demoMode ? `/players/${player.account_id}?demo=true` : `/players/${player.account_id}`)}
                className="flex items-center h-[54px] px-5 border-b border-[#1D1D28] last:border-0 hover:bg-obsidian-lighter/20 transition-colors cursor-pointer group"
              >
                <div className="w-[50px] text-center">
                  <span className={`text-[13px] font-bold ${rankColor(player.rank)}`}>
                    {player.rank}
                  </span>
                </div>
                <div className="flex-1 px-3 flex items-center gap-3">
                  {player.avatar_url ? (
                    <img 
                      src={player.avatar_url} 
                      alt="" 
                      className="w-8 h-8 rounded-full object-cover border border-obsidian-border"
                    />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-obsidian-lighter to-obsidian-border flex-shrink-0" />
                  )}
                  <div>
                    <div className="text-[13px] font-semibold group-hover:text-accent-dota transition-colors">
                      {player.name}
                    </div>
                    <div className="flex items-center gap-2 flex-wrap mt-0.5">
                      <span className="text-[11px] text-[#555568]">{player.team}</span>
                      <span className="text-[11px] text-[#333345]">·</span>
                      {player.top_heroes.slice(0, 3).map(id => (
                        <span key={id} className="flex items-center gap-1">
                          <HeroPortrait heroId={id} size="sm" />
                          <span className="text-[11px] text-[#555568]">{getHeroName(id)}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="w-[110px] text-center text-xs text-[#E8E8F0]">
                  {player.kda}
                </div>
                <div className="w-[80px] text-center text-xs font-semibold text-accent-win tabular-nums">
                  {player.avg_gpm.toFixed(0)}
                </div>
                <div className="w-[90px] text-center text-xs text-[#E8E8F0] tabular-nums">
                  {(player.win_rate * 100).toFixed(0)}%
                </div>
                <div className="w-[130px] flex items-center justify-center bg-[#1A0A33]/50">
                  <span className="text-sm font-bold text-accent-ai tabular-nums">
                    {player.ai_impact_score.toFixed(1)}
                  </span>
                </div>
                <div className="w-[140px] flex items-center justify-center">
                  <div className="flex items-center gap-1.5 bg-[#160D28] border border-[#3D2475] rounded-md py-1 px-3 group-hover:border-accent-ai transition-all">
                    <Play size={10} className="text-accent-ai" fill="currentColor" />
                    <span className="text-[11px] font-bold text-accent-ai">
                      {player.highlight_count} clip{player.highlight_count !== 1 ? 's' : ''}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  )
}

function StatCard({ icon, value, label }: { icon: React.ReactNode; value: string; label: string }) {
  return (
    <div className="bg-obsidian-dark border border-obsidian-border rounded-lg p-[18px] space-y-2 hover:border-accent-dota/30 transition-colors">
      {icon}
      <div className="text-2xl font-bold tabular-nums">{value}</div>
      <div className="text-[11px] text-[#6B6B88]">{label}</div>
    </div>
  )
}

function FilterButton({ label, active = false }: { label: string; active?: boolean }) {
  return (
    <button
      className={`h-[34px] px-3.5 rounded-[7px] text-xs font-medium border transition-all ${
        active
          ? 'bg-[#200D44] border-accent-ai text-accent-ai'
          : 'bg-obsidian-lighter border-obsidian-border text-[#9898B0] hover:border-[#3A3A55]'
      }`}
    >
      {label}
    </button>
  )
}

function rankColor(rank: number): string {
  switch (rank) {
    case 1: return 'text-[#FFB800]'
    case 2: return 'text-[#A0A8C0]'
    case 3: return 'text-[#CD7F32]'
    default: return 'text-[#6B6B88]'
  }
}
