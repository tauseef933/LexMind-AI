import { BrowserRouter, Route, Routes } from 'react-router-dom'
import IndexPage from './pages/index'
import DashboardPage from './pages/dashboard'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<IndexPage />} />
        <Route path="/dashboard/:caseId" element={<DashboardPage />} />
      </Routes>
    </BrowserRouter>
  )
}
