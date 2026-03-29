import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Leaderboard from './pages/Leaderboard'
import PlayerDetail from './pages/PlayerDetail'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Leaderboard />} />
        <Route path="/players/:accountId" element={<PlayerDetail />} />
      </Routes>
    </BrowserRouter>
  )
}
