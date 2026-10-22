import { useEffect } from 'react'
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom'
import { Landing } from './pages/Landing'
import { Results } from './pages/Results'
import { Upload } from './pages/Upload'
import { SessionProvider } from './session'

const TITLES: Record<string, string> = { '/upload': 'Upload reports · RadLabel', '/results': 'Results · RadLabel' }

export function AppRoutes() {
  const { pathname, hash } = useLocation()
  useEffect(() => {
    document.title = TITLES[pathname] ?? 'RadLabel: radiology reports, explained with evidence'
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView()
    else window.scrollTo(0, 0)
  }, [pathname, hash])
  return (
    <Routes>
      <Route path="/upload" element={<Upload />} />
      <Route path="/results" element={<Results />} />
      <Route path="*" element={<Landing />} />
    </Routes>
  )
}

export const App = () => (
  <SessionProvider>
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  </SessionProvider>
)
