import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Leaderboard from './pages/Leaderboard'
import PlayerDetail from './pages/PlayerDetail'
import { ClipPlayerProvider } from './context/ClipPlayerContext'
import ClipPlayerModal from './components/ClipPlayerModal'

export default function App() {
  return (
    <ClipPlayerProvider>
      <ClipPlayerModal />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Leaderboard />} />
          <Route path="/players/:accountId" element={<PlayerDetail />} />
        </Routes>
      </BrowserRouter>
    </ClipPlayerProvider>
  )
}
