import React, { createContext, useContext, useState, ReactNode } from 'react'

export interface ClipData {
  hlsUrl: string
  start: number
  end: number
  playerName?: string
  hero?: string
  matchId?: number
  opponent?: string
  aiScore?: number        // excitement_score from Highlight, score from SearchClip
  eventLabel?: string     // RAMPAGE | TEAMFIGHT | GODLIKE | OBJECTIVE | CLUTCH
  transcription?: string
}

interface ClipPlayerContextType {
  activeClip: ClipData | null
  openClip: (data: ClipData) => void
  closeClip: () => void
}

const ClipPlayerContext = createContext<ClipPlayerContextType | undefined>(undefined)

export function ClipPlayerProvider({ children }: { children: ReactNode }) {
  const [activeClip, setActiveClip] = useState<ClipData | null>(null)

  const openClip = (clip: ClipData) => {
    console.log('[clip-player] Opening clip:', clip)
    setActiveClip(clip)
  }

  const closeClip = () => {
    console.log('[clip-player] Closing clip')
    setActiveClip(null)
  }

  return (
    <ClipPlayerContext.Provider value={{ activeClip, openClip, closeClip }}>
      {children}
    </ClipPlayerContext.Provider>
  )
}

export function useClipPlayer() {
  const context = useContext(ClipPlayerContext)
  if (context === undefined) {
    throw new Error('useClipPlayer must be used within a ClipPlayerProvider')
  }
  return context
}
