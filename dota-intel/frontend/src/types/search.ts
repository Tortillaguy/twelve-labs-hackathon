export interface SearchClip {
  video_id: string
  start: number
  end: number
  score: number
  transcription: string | null
  play_summary: string | null
  thumbnail_url: string | null
  hls_url: string | null
  video_thumbnail_url: string | null
}
